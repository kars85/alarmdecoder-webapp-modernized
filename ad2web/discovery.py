# -*- coding: utf-8 -*-

import os
import socket
import struct
import threading
import uuid
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


def get_ip_address():
    """
    Tries to get the primary local IPv4 address using multiple methods.
    Returns the IP address string or None if all methods fail.
    """
    ip_address = None

    # Try socket method first
    s = None
    targets = [('1.1.1.1', 53), ('8.8.8.8', 53), ('1.0.0.1', 53)]

    for target_ip, target_port in targets:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(0.5)
            s.connect((target_ip, target_port))
            ip_address = s.getsockname()[0]
            if ip_address and not ip_address.startswith('127.'):
                logger.debug(f"Socket method succeeded using target {target_ip}:{target_port}. IP: {ip_address}")
                s.close()
                return ip_address
        except socket.error as e:
            logger.debug(f"Socket connection to {target_ip}:{target_port} failed: {e}")
            if s:
                s.close()
            continue
        except Exception as e:
            logger.warning(f"Unexpected error getting IP via socket with target {target_ip}:{target_port}: {e}")
            if s:
                s.close()
            continue
        finally:
            if s:
                s.close()
                s = None

    # Fall back to netifaces method
    if not ip_address:
        ip_address = _get_primary_ip_netifaces()

    # Log error if we couldn't find an IP
    if not ip_address:
        logger.error("Could not determine a suitable IP address using available methods.")

    return ip_address

# --- Request Parser Class (using Python 3 http.server) ---
class DiscoveryRequest(BaseHTTPRequestHandler):
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
# --- Discovery Server Thread ---
class DiscoveryServer(threading.Thread):
    MCAST_PORT = 1900
    MCAST_ADDRESS = '239.255.255.250'
    ENABLE_PERIODIC_ANNOUNCEMENTS = False  # Toggle for periodic ssdp:alive announcements

    RESPONSE_MESSAGE = ('HTTP/1.1 200 OK\r\n' +
                        'CACHE-CONTROL: max-age = %(CACHE_CONTROL)i\r\n' +
                        'EXT:\r\n' +
                        'LOCATION: %(LOCATION)s\r\n' +
                        'SERVER: Linux/UPnP/1.1 AlarmDecoder/1.0\r\n' +
                        'ST: %(ST)s\r\n' +
                        'USN: %(USN)s\r\n' +
                        '\r\n')

    NOTIFY_MESSAGE = ('NOTIFY * HTTP/1.1\r\n' +
                      'HOST: 239.255.255.250:1900\r\n' +
                      'CACHE-CONTROL: max-age = %(CACHE_CONTROL)i\r\n' +
                      'LOCATION: %(LOCATION)s\r\n' +
                      'NT: %(NT)s\r\n' +
                      'NTS: %(NTS)s\r\n' +
                      'SERVER: Linux/UPnP/1.1 AlarmDecoder/1.0\r\n' +
                      'USN: %(USN)s\r\n' +
                      '\r\n')

    def __init__(self, decoder_service):
        super().__init__()  # Call to super class's __init__
        self.daemon = True
        self._decoder = decoder_service
        self._running = False
        self._socket = None
        self._expiration_time = 600
        self._current_port = int(os.getenv('AD_LISTENER_PORT', '5000'))
        self._current_ip_address = None
        self._device_uuid = None
        self._announcement_timestamp = 0
        self.logger = self._decoder.app.logger

    def setup_socket(self):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(('', self.MCAST_PORT))

            # Multicast group and interface (INADDR_ANY = 0.0.0.0)
            group = socket.inet_aton(self.MCAST_ADDRESS)
            iface = socket.inet_aton('0.0.0.0')  # Explicitly pack as IP bytes

            mreq = struct.pack('=4s4s', group, iface)
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

            sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)

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
        self.logger.info("Stopping DiscoveryServer thread.")
        self._running = False

    def run(self):
        self.logger.info("DiscoveryServer thread started.")
        if not self.setup_socket():
            self.logger.error("DiscoveryServer could not setup socket. Thread exiting.")
            return

        with self._decoder.app.app_context():
            self._current_ip_address = get_ip_address()
            self._device_uuid = self._get_device_uuid()
            if not self._current_ip_address:
                self.logger.error("DiscoveryServer could not determine local IP address. SSDP responses may be incorrect.")
            else:
                self.logger.info(f"Discovery running: loc=http://{self._current_ip_address}:{self._current_port}/..., uuid={self._device_uuid}")

        self._running = True
        while self._running:
            try:
                rl, _, _ = select([self._socket], [], [], 1.0)
                if rl:
                    s = rl[0]
                    data, addr = s.recvfrom(4096)
                    self.logger.debug(f"Received {len(data)} bytes from {addr}")
                    request = DiscoveryRequest(data)
                    self._handle_request(request, addr)
                self._update()
            except socket.timeout:
                continue
            except Exception as err:
                self.logger.error(f'Error in DiscoveryServer run loop: {err}', exc_info=True)
                time.sleep(1)

        if self._socket:
            self.logger.info("Closing discovery socket.")
            self._socket.close()
            self._socket = None
        self.logger.info("DiscoveryServer thread finished.")

    def _handle_request(self, request, addr):
        if request.error_code:
            self.logger.warning(f'Discovery Parse Error from {addr}: {request.error_code} - {request.error_message}')
            return

        if request.command != 'M-SEARCH':
            self.logger.debug(f"Ignoring non M-SEARCH command '{request.command}' from {addr}")
            return

        if self._match_search_request(request):
            self.logger.info(f"Received matching M-SEARCH from {addr} for ST: {request.headers.get('ST', 'N/A')}")
            response_message = self._create_discovery_response(request)
            if response_message:
                self._send_message(response_message.encode('utf-8'), addr)
        else:
            self.logger.debug(f"Ignoring non-matching M-SEARCH from {addr} for ST: {request.headers.get('ST', 'N/A')}")

    def _update(self):
        if self._current_ip_address:
            current_ip = get_ip_address()
            if current_ip and current_ip != self._current_ip_address:
                self.logger.info(f"IP address changed from {self._current_ip_address} to {current_ip}. Updating configuration.")
                self._current_ip_address = current_ip

        if self.ENABLE_PERIODIC_ANNOUNCEMENTS:
            now = time.time()
            if self._announcement_timestamp + (self._expiration_time / 2.0) < now:
                if self._current_ip_address and self._device_uuid:
                    self.logger.info('Sending periodic ssdp:alive announcements.')
                    notify_messages = self._create_notify_message("ssdp:alive")
                    for msg in notify_messages:
                        self._send_message(msg.encode('utf-8'), (self.MCAST_ADDRESS, self.MCAST_PORT))
                    self._announcement_timestamp = now
                else:
                    self.logger.warning("Cannot send announcements: Missing IP or UUID.")

    def _create_discovery_response(self, request):
        if not self._current_ip_address or not self._device_uuid:
            self.logger.warning("Cannot create discovery response: IP or UUID not set.")
            return None

        loc = f'http://{self._current_ip_address}:{self._current_port}/static/device_description.xml'
        st = request.headers.get('ST', 'N/A').strip()
        usn_base = f'uuid:{self._device_uuid}'
        usn = usn_base
        if st != 'ssdp: all' and st != 'upnp:rootdevice':
            usn += f'::{st}'
        elif st == 'upnp:rootdevice':
            usn += '::upnp:rootdevice'

        response_data = {
            'ST': st,
            'LOCATION': loc,
            'USN': usn,
            'CACHE_CONTROL': self._expiration_time
        }
        return self.RESPONSE_MESSAGE % response_data

    def _create_notify_message(self, nts_type="ssdp:alive"):
        if not self._current_ip_address or not self._device_uuid:
            self.logger.warning("Cannot create NOTIFY message: IP or UUID not set.")
            return []

        loc = f'http://{self._current_ip_address}:{self._current_port}/static/device_description.xml'
        usn_base = f'uuid:{self._device_uuid}'
        messages = [
            self.NOTIFY_MESSAGE % {
                'NT': "upnp:rootdevice",
                'LOCATION': loc,
                'USN': usn_base + "::upnp:rootdevice",
                'NTS': nts_type,
                'CACHE_CONTROL': self._expiration_time
            },
            self.NOTIFY_MESSAGE % {
                'NT': usn_base,
                'LOCATION': loc,
                'USN': usn_base,
                'NTS': nts_type,
                'CACHE_CONTROL': self._expiration_time
            },
            self.NOTIFY_MESSAGE % {
                'NT': "urn:schemas-upnp-org:device:AlarmDecoder:1",
                'LOCATION': loc,
                'USN': usn_base + "::urn:schemas-upnp-org:device:AlarmDecoder:1",
                'NTS': nts_type,
                'CACHE_CONTROL': self._expiration_time
            }
        ]
        return messages

    def _send_message(self, message_bytes, addr):
        if not self._socket:
            self.logger.error(f"Cannot send message to {addr}: Socket is not open.")
            return

        self.logger.debug(f'Sending {len(message_bytes)} bytes to {addr}')
        for i in range(2):
            try:
                self._socket.sendto(message_bytes, addr)
                time.sleep(0.05)
            except socket.error as e:
                self.logger.error(f"Socket error sending to {addr} (attempt {i+1}/2): {e}")
                break
            except Exception as e:
                self.logger.error(f"Unexpected error sending to {addr} (attempt {i+1}/2): {e}", exc_info=True)
                break

    def _match_search_request(self, request):
        st = request.headers.get('ST', '').strip()
        man = request.headers.get('MAN', '').strip()
        if request.command == 'M-SEARCH' and request.path == '*' and man == '"ssdp: discover"':
            if st in {'ssdp: all', 'upnp:rootdevice', f'uuid:{self._device_uuid}', 'urn:schemas-upnp-org:device:AlarmDecoder:1'}:
                return True
        return False

    def _get_device_uuid(self):
        device_uuid = None
        try:
            device_uuid = db.session.query(Setting.value).filter_by(name='device_uuid').scalar()
            if not device_uuid:
                self.logger.info('Generating new device UUID.')
                device_uuid = str(uuid.uuid1())
                uuid_setting = db.session.merge(Setting(name='device_uuid', value=device_uuid))
                db.session.commit()
                self.logger.info(f'New device UUID generated and saved: {device_uuid}')
        except Exception as e:
            self.logger.error(f"Failed to get or generate device UUID from database: {e}", exc_info=True)
            device_uuid = None
        return device_uuid



