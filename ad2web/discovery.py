# -*- coding: utf-8 -*-

import os
import socket
import struct
import threading
import uuid
# import fcntl # No longer needed after replacing _get_ip_address
import time
import logging

# Python 3 imports
from http.server import BaseHTTPRequestHandler
# from http.client import HTTPResponse # No longer needed as DiscoveryResponse is removed
from io import BytesIO # Use BytesIO for network data

# Optional netifaces import
try:
    import netifaces
    has_netifaces = True
except ImportError:
    import netifaces
    has_netifaces = False

from select import select

# App-specific imports (ensure these paths are correct)
from .extensions import db
from .settings.models import Setting

# Setup logger for this module
logger = logging.getLogger(__name__)


# --- IP Address Helper Functions (Combined Method) ---

def _get_primary_ip_socket():
    """
    Helper: Gets the preferred outbound IP address by connecting a UDP socket.
    Returns the IP address as a string, or None if unable to determine.
    """
    s = None
    ip_address = None
    targets = [('1.1.1.1', 53), ('8.8.8.8', 53), ('1.0.0.1', 53)]

    for target_ip, target_port in targets:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(0.5)
            s.connect((target_ip, target_port))
            ip_address = s.getsockname()[0]
            if ip_address and not ip_address.startswith('127.'):
                 logger.debug(f"Socket method succeeded using target {target_ip}:{target_port}. IP: {ip_address}")
                 return ip_address
            else:
                 ip_address = None
                 if s:
                     s.close()
                 s = None
        except socket.error as e:
            logger.debug(f"Socket connection to {target_ip}:{target_port} failed: {e}")
            if s:
                s.close()
            s = None
            continue
        except Exception as e:
             logger.warning(f"Unexpected error getting IP via socket with target {target_ip}:{target_port}: {e}")
             if s:
                 s.close()
             s = None
             continue
        finally:
            if s:
                s.close()

    logger.warning("Socket method failed to determine a non-loopback outbound IP.")
    return None


def _get_primary_ip_netifaces():
    """
    Helper: Gets a primary non-loopback IPv4 address using netifaces.
    Prioritizes the interface associated with the default IPv4 gateway.
    Returns the IP address string or None if not found/netifaces unavailable.
    """
    if not has_netifaces:
        logger.info("Netifaces library not available for IP discovery fallback.")
        return None

    default_gw_iface = None
    preferred_ip = None
    first_ip = None

    try:
        gws = netifaces.gateways()
        default_ipv4_gw = gws.get('default', {}).get(netifaces.AF_INET)
        if default_ipv4_gw:
            default_gw_iface = default_ipv4_gw[1]
            logger.debug(f"Default gateway interface identified as: {default_gw_iface}")
        else:
            logger.debug("No default IPv4 gateway found.")

        for iface in netifaces.interfaces():
            if iface.startswith('lo'):
                continue

            ifaddresses = netifaces.ifaddresses(iface)
            ipv4_addrs = ifaddresses.get(netifaces.AF_INET)

            if ipv4_addrs:
                logger.debug(f"Checking interface {iface} for IPv4 addresses...")
                for addr_info in ipv4_addrs:
                    ip_addr = addr_info.get('addr')
                    if ip_addr and not ip_addr.startswith('127.') and not ip_addr.startswith('169.254.'):
                        current_iface_ip = ip_addr
                        logger.debug(f"  Found valid IP: {current_iface_ip}")
                        if first_ip is None:
                            first_ip = current_iface_ip
                        if iface == default_gw_iface:
                            preferred_ip = current_iface_ip
                            logger.debug(f"  IP {preferred_ip} matches gateway interface {iface}. Using this.")
                            break
                if preferred_ip:
                    break

        final_ip = preferred_ip if preferred_ip is not None else first_ip
        if final_ip is None:
             logger.warning("Could not find a suitable non-loopback IPv4 address via netifaces.")
        else:
             logger.debug(f"Netifaces method determined IP: {final_ip}")
        return final_ip

    except Exception as e:
        logger.error(f"Error getting IP via netifaces: {e}", exc_info=True)
        return None

# --- Main function to be called externally ---
def get_ip_address():
    """
    Tries to get the primary local IPv4 address using multiple methods.
    Returns the IP address string or None if all methods fail.
    """
    ip_address = _get_primary_ip_socket()
    if not ip_address:
        ip_address = _get_primary_ip_netifaces()
    if not ip_address:
        logger.error("Could not determine a suitable IP address using available methods.")
    return ip_address

# --- Request Parser Class (using Python 3 http.server) ---
class DiscoveryRequest(BaseHTTPRequestHandler):
    # Set protocol version for base class
    protocol_version = "HTTP/1.1"

    def __init__(self, request_bytes):
        # BaseHTTPRequestHandler expects a file-like object for reading bytes
        self.rfile = BytesIO(request_bytes)
        self.raw_requestline = self.rfile.readline()
        self.error_code = self.error_message = None
        self.parse_request() # This method is part of BaseHTTPRequestHandler

    def send_error(self, code, message=None, explain=None):
         # Override to just store the error, not send a response
        self.error_code = code
        self.error_message = message or explain # Use explain if message is None


# --- Discovery Server Thread ---
class DiscoveryServer(threading.Thread):
    MCAST_PORT = 1900
    MCAST_ADDRESS = '239.255.255.250'
    # Message templates remain the same
    RESPONSE_MESSAGE = ('HTTP/1.1 200 OK\r\n' +
                        'CACHE-CONTROL: max-age = %(CACHE_CONTROL)i\r\n' +
                        'EXT:\r\n' +
                        'LOCATION: %(LOCATION)s\r\n' +
                        'SERVER: Linux/UPnP/1.1 AlarmDecoder/1.0\r\n' + # Simplified server string
                        'ST: %(ST)s\r\n' +
                        'USN: %(USN)s\r\n' +
                        '\r\n')

    NOTIFY_MESSAGE = ('NOTIFY * HTTP/1.1\r\n' +
                      'HOST: 239.255.255.250:1900\r\n' +
                      'CACHE-CONTROL: max-age = %(CACHE_CONTROL)i\r\n' +
                      'LOCATION: %(LOCATION)s\r\n' +
                      'NT: %(NT)s\r\n' +
                      'NTS: %(NTS)s\r\n' +
                      'SERVER: Linux/UPnP/1.1 AlarmDecoder/1.0\r\n' + # Simplified server string
                      'USN: %(USN)s\r\n' +
                      '\r\n')

    def __init__(self, decoder_service): # Renamed arg for clarity
        threading.Thread.__init__(self)
        self.daemon = True # Set thread as daemon so it exits with main app

        self._decoder = decoder_service # The main Decoder service instance
        self._running = False
        self._socket = None # Initialize socket later in run() for cleaner error handling

        self._expiration_time = 600 # Cache control time in seconds
        self._current_port = int(os.getenv('AD_LISTENER_PORT', '5000')) # Get port from env or default
        self._current_ip_address = None # Determined later
        self._device_uuid = None # Determined later
        self._announcement_timestamp = 0

        # Use the logger from the passed-in decoder service's app instance
        self.logger = self._decoder.app.logger

    def setup_socket(self):
         """Sets up the multicast socket."""
         try:
              sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
              sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
              # Some OS might require binding to 0.0.0.0 for multicast receive
              sock.bind(('', self.MCAST_PORT))
              # Set multicast options
              mreq = struct.pack('4sl', socket.inet_aton(self.MCAST_ADDRESS), socket.INADDR_ANY)
              sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
              # TTL for outgoing multicasts if needed (NOTIFYs are multicast)
              sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2) # Small TTL for local network
              self._socket = sock
              self.logger.info("Multicast socket setup complete on port 1900.")
              return True
         except socket.error as e:
              self.logger.error(f"Failed to setup multicast socket: {e}", exc_info=True)
              self._socket = None
              return False
         except Exception as e:
              self.logger.error(f"Unexpected error setting up socket: {e}", exc_info=True)
              self._socket = None
              return False

    def stop(self):
        """Signals the discovery thread to stop."""
        self.logger.info("Stopping DiscoveryServer thread.")
        self._running = False
        # Optionally close socket here to interrupt select, though select might timeout anyway
        # if self._socket:
        #     self._socket.close()

    def run(self):
        """Main thread loop for listening and responding to discovery requests."""
        self.logger.info("DiscoveryServer thread started.")
        if not self.setup_socket():
             self.logger.error("DiscoveryServer could not setup socket. Thread exiting.")
             return # Cannot run without socket

        # Initial setup requiring app context
        with self._decoder.app.app_context():
             self._current_ip_address = get_ip_address() # Use the new combined function
             self._device_uuid = self._get_device_uuid()
             if not self._current_ip_address:
                  self.logger.error("DiscoveryServer could not determine local IP address. SSDP responses may be incorrect.")
                  # Decide if this is fatal - maybe fallback to 127.0.0.1 for LOCATION?
                  # self._current_ip_address = '127.0.0.1'
             else:
                  self.logger.info(f"Discovery running: loc=http://{self._current_ip_address}:{self._current_port}/..., uuid={self._device_uuid}")

        self._running = True
        while self._running:
            try:
                # Use select with a timeout so the loop can check self._running periodically
                # and potentially run timed tasks like _update()
                rl, wl, xl = select([self._socket], [], [], 1.0) # 1 second timeout

                if rl: # Socket is readable
                    s = rl[0]
                    data, addr = s.recvfrom(4096) # Buffer size
                    self.logger.debug(f"Received {len(data)} bytes from {addr}")

                    request = DiscoveryRequest(data) # Parse using the updated class
                    self._handle_request(request, addr)

                # Check for periodic tasks (like _update) outside the readable check
                # This part was previously only called when data arrived
                self._update()

            except socket.timeout:
                 # Select timed out, just loop again to check self._running
                 continue
            except Exception as err:
                self.logger.error(f'Error in DiscoveryServer run loop: {err}', exc_info=True)
                # Avoid continuous tight loop errors if socket error persists
                time.sleep(1)

        # Cleanup socket when thread stops
        if self._socket:
            self.logger.info("Closing discovery socket.")
            # Unregister multicast? Maybe not necessary on close.
            # mreq = struct.pack('4sl', socket.inet_aton(self.MCAST_ADDRESS), socket.INADDR_ANY)
            # try:
            #     self._socket.setsockopt(socket.IPPROTO_IP, socket.IP_DROP_MEMBERSHIP, mreq)
            # except socket.error as e:
            #     self.logger.warning(f"Could not drop multicast membership: {e}")
            self._socket.close()
            self._socket = None
        self.logger.info("DiscoveryServer thread finished.")


    def _handle_request(self, request, addr):
        """Handles a parsed discovery request."""
        if request.error_code:
            self.logger.warning(f'Discovery Parse Error from {addr}: {request.error_code} - {request.error_message}')
            return

        # Ensure request method is M-SEARCH (already checked partially by parser)
        if request.command != 'M-SEARCH':
             self.logger.debug(f"Ignoring non M-SEARCH command '{request.command}' from {addr}")
             return

        if self._match_search_request(request):
            self.logger.info(f"Received matching M-SEARCH from {addr} for ST: {request.headers.get('ST', 'N/A')}")
            response_message = self._create_discovery_response(request)
            if response_message:
                self._send_message(response_message.encode('utf-8'), addr) # Encode message to bytes
        else:
             self.logger.debug(f"Ignoring non-matching M-SEARCH from {addr} for ST: {request.headers.get('ST', 'N/A')}")


    def _update(self):
        """Periodic checks/updates (e.g., IP address changes, announcements)."""
        # Check if IP changed (only if an IP was determined initially)
        if self._current_ip_address:
            current_ip = get_ip_address()
            if current_ip and current_ip != self._current_ip_address:
                self.logger.info(f"IP address changed from {self._current_ip_address} to {current_ip}. Updating configuration.")
                # TODO: Implement logic needed on IP change (e.g., update LOCATION in future announcements)
                # Maybe force an ssdp:alive announcement?
                self._current_ip_address = current_ip
                # Reset announcement timestamp to send new NOTIFYs soon?
                # self._announcement_timestamp = 0

        # Handle periodic ssdp:alive announcements (currently disabled in original code)
        # If enabling, this should run based on time elapsed, not just when requests come in
        if False: # Keep disabled for now based on original code comment
             now = time.time()
             if self._announcement_timestamp + (self._expiration_time / 2.0) < now: # Announce more frequently than expiry
                 if self._current_ip_address and self._device_uuid: # Need info to announce
                      self.logger.info('Sending periodic ssdp:alive announcements.')
                      notify_messages = self._create_notify_message("ssdp:alive")
                      for msg in notify_messages:
                           self._send_message(msg.encode('utf-8'), (self.MCAST_ADDRESS, self.MCAST_PORT)) # Multicast
                      self._announcement_timestamp = now
                 else:
                      self.logger.warning("Cannot send announcements: Missing IP or UUID.")

    def _create_discovery_response(self, request):
        """Creates the HTTP response message for an M-SEARCH request."""
        if not self._current_ip_address or not self._device_uuid:
             self.logger.warning("Cannot create discovery response: IP or UUID not set.")
             return None

        loc = f'http://{self._current_ip_address}:{self._current_port}/static/device_description.xml'
        st = request.headers.get('ST', 'N/A').strip()
        # USN structure: uuid:device-UUID[::upnp-service-type]
        usn_base = f'uuid:{self._device_uuid}'
        usn = usn_base
        if st != 'ssdp: all' and st != 'upnp:rootdevice':
             # If ST is specific, append it to USN
             usn += f'::{st}'
        elif st == 'upnp:rootdevice':
             usn += '::upnp:rootdevice'
        # If ssdp:all, USN is just the base UUID for the root device response part

        response_data = dict(
             ST=st,
             LOCATION=loc,
             USN=usn,
             CACHE_CONTROL=self._expiration_time
        )
        return self.RESPONSE_MESSAGE % response_data

    def _create_notify_message(self, nts_type="ssdp:alive"):
        """Creates the NOTIFY messages (e.g., for ssdp:alive)."""
        if not self._current_ip_address or not self._device_uuid:
             self.logger.warning("Cannot create NOTIFY message: IP or UUID not set.")
             return []

        loc = f'http://{self._current_ip_address}:{self._current_port}/static/device_description.xml'
        usn_base = f'uuid:{self._device_uuid}'
        messages = []

        # Notify for root device
        messages.append(self.NOTIFY_MESSAGE % dict(
             NT="upnp:rootdevice",
             LOCATION=loc,
             USN=usn_base + "::upnp:rootdevice",
             NTS=nts_type,
             CACHE_CONTROL=self._expiration_time
        ))
        # Notify for UUID itself
        messages.append(self.NOTIFY_MESSAGE % dict(
             NT=usn_base,
             LOCATION=loc,
             USN=usn_base,
             NTS=nts_type,
             CACHE_CONTROL=self._expiration_time
        ))
        # Notify for specific device type
        messages.append(self.NOTIFY_MESSAGE % dict(
             NT="urn:schemas-upnp-org:device:AlarmDecoder:1",
             LOCATION=loc,
             USN=usn_base + "::urn:schemas-upnp-org:device:AlarmDecoder:1",
             NTS=nts_type,
             CACHE_CONTROL=self._expiration_time
        ))

        return messages

    def _send_message(self, message_bytes, addr):
        """Sends a message (bytes) via the UDP socket, possibly multiple times."""
        if not self._socket:
             self.logger.error(f"Cannot send message to {addr}: Socket is not open.")
             return

        self.logger.debug(f'Sending {len(message_bytes)} bytes to {addr}')
        # self.logger.debug(f'Message content:\n{message_bytes.decode("utf-8", errors="ignore")}') # Careful logging potentially large/binary data

        # Send multiple times for UDP reliability (as in original code)
        for i in range(2): # Use Python 3 range()
            try:
                self._socket.sendto(message_bytes, addr)
                # Short delay between sends can sometimes help routers/switches
                time.sleep(0.05) # Reduced sleep from 0.1
            except socket.error as e:
                 self.logger.error(f"Socket error sending to {addr} (attempt {i+1}/2): {e}")
                 break # Don't retry if send fails
            except Exception as e:
                 self.logger.error(f"Unexpected error sending to {addr} (attempt {i+1}/2): {e}", exc_info=True)
                 break


    def _match_search_request(self, request):
        """Checks if a parsed DiscoveryRequest is a valid M-SEARCH we should respond to."""
        # Header lookups are case-insensitive in http.server's SimpleHTTPRequestHandler message object
        st = request.headers.get('ST', '').strip()
        man = request.headers.get('MAN', '').strip()

        if request.command == 'M-SEARCH' and request.path == '*' and man == '"ssdp: discover"':
            # Check if the Search Target (ST) matches what we provide
            if st == 'ssdp: all' or \
               st == 'upnp:rootdevice' or \
               st == f'uuid:{self._device_uuid}' or \
               st == 'urn:schemas-upnp-org:device:AlarmDecoder:1':
                return True

        return False

    def _get_device_uuid(self):
        """Gets or generates the device UUID, storing it in settings."""
        # Note: This requires app context, called from run() which establishes it.
        device_uuid = None
        try:
             # Use scalar() to get value directly or None
             device_uuid = db.session.query(Setting.value).filter_by(name='device_uuid').scalar()

             if not device_uuid:
                  self.logger.info('Generating new device UUID.')
                  device_uuid = str(uuid.uuid1())
                  # Use merge to insert or update if somehow deleted between query and add
                  uuid_setting = db.session.merge(Setting(name='device_uuid', value=device_uuid))
                  # db.session.add(uuid_setting) # merge handles add
                  db.session.commit()
                  self.logger.info(f'New device UUID generated and saved: {device_uuid}')

        except Exception as e:
             self.logger.error(f"Failed to get or generate device UUID from database: {e}", exc_info=True)
             # Fallback: generate a UUID but don't save it? Or return None?
             # Returning None might prevent discovery from working fully.
             # Using a random one per session might be confusing for clients.
             # Best to ensure DB is working or handle failure gracefully.
             # For now, return None if DB fails.
             device_uuid = None

        return device_uuid

    # Remove the old _get_ip_address method entirely
    # It's replaced by the global get_ip_address() function


# --- Remove this class, it was unused and used Python 2 imports ---
# class DiscoveryResponse(HTTPResponse):
#     def __init__(self, response_text):
#         self.fp = StringIO(response_text)
#         # ... rest of old class ...
