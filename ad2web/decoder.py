# -*- coding: utf-8 -*-

import os
import sys
import time
import datetime
import threading
import binascii
import logging  # Use standard logging

# --- miniupnpc (Optional) ---
try:
    import miniupnpc

    has_upnp = True
except ImportError:
    has_upnp = False

# --- Flask & SocketIO Imports ---
from flask import request, current_app, Blueprint, session  # Added flash
from flask_socketio import Namespace, emit, SocketIO  # emit is useful here

# Import the single socketio instance from extensions
from .extensions import db, socketio  # ADDED socketio

# --- Other Necessary Imports ---
import jsonpickle
from OpenSSL import SSL
from alarmdecoder import AlarmDecoder
from alarmdecoder.devices import SocketDevice, SerialDevice
from alarmdecoder.util.exceptions import NoDeviceError, CommError
from sqlalchemy.orm.exc import NoResultFound  # Import for exception handling

# --- App Specific Imports ---
from .notifications import NotificationSystem, NotificationThread
from .settings.models import Setting
from .certificate.models import Certificate
from .updater import Updater
from .updater.models import FirmwareUpdater
from .notifications.models import NotificationMessage
from .notifications.constants import (
    ARM,
    DISARM,
    POWER_CHANGED,
    ALARM,
    ALARM_RESTORED,
    FIRE,
    BYPASS,
    BOOT,
    LRR,
    CONFIG_RECEIVED,
    ZONE_FAULT,
    ZONE_RESTORE,
    LOW_BATTERY,
    PANIC,
    READY,
    CHIME,
    DEFAULT_EVENT_MESSAGES,
    EVMSG_VERSION,
    RFX,
    EXP,
    AUI,
)
from .cameras.types import CameraSystem

# from .cameras.models import Camera # Import only if used directly in this file
from .discovery import DiscoveryServer
from .upnp import UPNPThread
from .setup.constants import SETUP_COMPLETE
from .utils import user_is_authenticated, INSTANCE_FOLDER_PATH
from .mailer import Mailer
from .exporter import Exporter

logger = logging.getLogger(__name__)  # Setup logger for this module

# Mapping from AlarmDecoder events to internal event types (used in old code, might still be useful)
EVENT_MAP = {
    ARM: "on_arm",
    DISARM: "on_disarm",
    POWER_CHANGED: "on_power_changed",
    ALARM: "on_alarm",
    ALARM_RESTORED: "on_alarm_restored",
    FIRE: "on_fire",
    BYPASS: "on_bypass",
    BOOT: "on_boot",
    LRR: "on_lrr_message",
    READY: "on_ready_changed",
    CHIME: "on_chime_changed",
    CONFIG_RECEIVED: "on_config_received",
    ZONE_FAULT: "on_zone_fault",
    ZONE_RESTORE: "on_zone_restore",
    LOW_BATTERY: "on_low_battery",
    PANIC: "on_panic",
    RFX: "on_rfx_message",
    EXP: "on_expander_message",
    AUI: "on_aui_message",
}

decodersocket = Blueprint("sock", __name__, url_prefix="/socket.io")


def create_decoder_socket(app):
    """Create and return a Flask-SocketIO instance to handle WebSockets."""
    socketio = SocketIO(app, async_mode="gevent", cors_allowed_origins="*")
    # Register the decoder namespace
    socketio.on_namespace(DecoderNamespace("/alarmdecoder"))

    return socketio


class Decoder(object):
    """
    Primary application state for the AlarmDecoder device and related services.
    """

    # Removed websocket from __init__ as Flask-SocketIO handles the server
    def __init__(self, app):
        """
        Constructor

        :param app: The flask application object
        :type app: Flask
        """
        self.app = app
        self.logger = app.logger  # Use app's logger
        # self.websocket = websocket # REMOVED
        self.device = None  # The underlying alarmdecoder.AlarmDecoder instance
        self.updater = None
        self.updates = {}
        self.version = ""
        self.firmware_file = None
        self.firmware_length = -1

        self.trigger_reopen_device = False
        self.trigger_restart = False

        self._last_message_timestamp = None  # Renamed for clarity
        self._device_baudrate = 115200
        self._device_type = None
        self._device_location = None
        self._event_thread = DecoderThread(self)
        self._discovery_thread = None
        self._notification_thread = None
        self._notifier_system = None
        self._upnp_thread = None
        self._internal_address_mask = 0xFFFFFFFF
        self.last_message_received = None  # Raw message string

        # Initialize background threads later in init() after config loaded
        self._version_thread = None
        self._camera_thread = None
        self._exporter_thread = None

    @property
    def internal_address_mask(self):
        return self._internal_address_mask

    @internal_address_mask.setter
    def internal_address_mask(self, mask):
        try:
            self._internal_address_mask = int(mask, 16)
            if self.device is not None:
                self.device.internal_address_mask = self._internal_address_mask
        except (ValueError, TypeError):
            self.logger.error(f"Invalid address mask format: {mask}. Should be hex.")

    def start(self):
        """Starts the internal threads."""
        if self._event_thread and not self._event_thread.is_alive():
            self._event_thread.start()
        if self._discovery_thread and not self._discovery_thread.is_alive():
            self._discovery_thread.start()

    def stop(self, restart=False):
        """
        Closes the device, stops the internal threads, and shuts down. Optionally
        triggers a restart of the application.

        :param restart: Indicates whether or not the application should be restarted.
        :type restart: bool
        """
        self.logger.info("Stopping service components...")

        # Stop threads first
        if self._event_thread:
            self._event_thread.stop()
        if self._version_thread:
            self._version_thread.stop()
        if self._camera_thread:
            self._camera_thread.stop()
        if self._discovery_thread:
            self._discovery_thread.stop()
        if self._notification_thread:
            self._notification_thread.stop()
        if self._exporter_thread:
            self._exporter_thread.stop()
        if has_upnp and self._upnp_thread:
            self._upnp_thread.stop()

        # Close the device connection
        self.close()

        # Wait for threads to finish (with timeout)
        threads = [
            self._event_thread,
            self._version_thread,
            self._camera_thread,
            self._discovery_thread,
            self._notification_thread,
            self._exporter_thread,
            self._upnp_thread if has_upnp else None,
        ]
        for t in filter(None, threads):
            try:
                t.join(2)  # Short join timeout
            except RuntimeError:
                pass  # Ignore if thread not started

        # self.websocket.stop() # REMOVED - No separate websocket server instance to stop

        if restart:
            self.logger.info("Restarting service process...")
            # This is a hard restart, might not be ideal in all contexts
            os.execv(sys.executable, [sys.executable] + sys.argv)

    def init(self):
        """
        Initializes the application state, loads config, starts threads,
        and triggers a device open if configured. Should be called after
        Flask app is configured.
        """

        with self.app.app_context():

            # Ensure essential folders exist (moved from factory)
            try:
                # Ensure these keys exist in config or provide defaults
                log_folder = self.app.config.get(
                    "LOG_FOLDER", os.path.join(INSTANCE_FOLDER_PATH, "logs")
                )
                upload_folder = self.app.config.get(
                    "UPLOAD_FOLDER", os.path.join(INSTANCE_FOLDER_PATH, "uploads")
                )
                openid_folder = self.app.config.get(
                    "OPENID_FS_STORE_PATH", os.path.join(INSTANCE_FOLDER_PATH, "openid_store")
                )
                os.makedirs(log_folder, exist_ok=True)
                os.makedirs(upload_folder, exist_ok=True)
                os.makedirs(openid_folder, exist_ok=True)
                if self.updater is None:
                    self.updater = Updater()
            except OSError as e:
                self.logger.error(f"Error creating essential folders: {e}")

            # Load Mail config (check if needed - mail.init_app in factory should handle this)
            # This might override dynamically, but is it necessary? Consider removing.
            # self.app.config['MAIL_SERVER'] = Setting.get_by_name('system_email_server',default='localhost').value
            # ... (load other MAIL_ settings) ...
            # mail.init_app(self.app) # REMOVE: Should be called only once in factory

            # Ensure secret key is set
            secret_key = Setting.get_by_name("secret_key").value
            if not secret_key:
                self.logger.info("Generating new Flask secret key.")
                secret_key = binascii.hexlify(os.urandom(24)).decode("utf-8")  # type: ignore[arg-type]
                sk_setting = db.session.merge(Setting(name="secret_key", value=secret_key))
                # db.session.add(sk_setting) # merge handles add
                db.session.commit()
            self.app.secret_key = secret_key  # Set it on the app instance

            # Update/Seed default notification messages if needed
            try:
                db_version = (
                    db.session.query(NotificationMessage.text).filter_by(id=EVMSG_VERSION).scalar()
                )
                if db_version != DEFAULT_EVENT_MESSAGES.get(EVMSG_VERSION):
                    self.logger.info(
                        "New notification message formats detected or version mismatch. Updating defaults."
                    )
                    for event, message in DEFAULT_EVENT_MESSAGES.items():  # Use items()
                        # Use merge to insert or update
                        db.session.merge(NotificationMessage(id=event, text=message))
                    db.session.commit()
            except Exception as e:
                self.logger.error(
                    f"Error checking/updating notification messages: {e}", exc_info=True
                )
                db.session.rollback()

            # Get app version and expose to templates
            try:
                self.version = self.updater._components["AlarmDecoderWebapp"].version
                self.app.jinja_env.globals["version"] = self.version
                self.logger.info(f"AlarmDecoder Webapp booting up - v{self.version}")
            except KeyError:
                self.logger.warning("Could not determine Webapp version from updater.")
                self.app.jinja_env.globals["version"] = "Unknown"

            # Expose auth check function to templates
            self.app.jinja_env.globals["user_is_authenticated"] = user_is_authenticated

            # Initialize systems and threads
            self._notifier_system = NotificationSystem()
            self._camera_thread = CameraChecker(self)
            self._discovery_thread = DiscoveryServer(self)
            self._notification_thread = NotificationThread(self)
            self._exporter_thread = ExportChecker(self)
            self._version_thread = VersionChecker(self)
            if has_upnp:
                self._upnp_thread = UPNPThread(self)
            else:
                self._upnp_thread = None

            # Check if device is configured and trigger open
            device_type = Setting.get_by_name("device_type").value
            if device_type:
                self.trigger_reopen_device = True
            else:
                self.logger.info("No AlarmDecoder device configured yet.")

    def open(self, no_reader_thread=False):
        """
        Opens the AlarmDecoder device based on settings.
        """
        # Ensure previous device is closed
        self.close()

        with self.app.app_context():
            self._device_type = Setting.get_by_name("device_type").value
            self._device_location = Setting.get_by_name("device_location").value
            address_mask_str = Setting.get_by_name("address_mask", "FFFFFFFF").value
            try:
                self._internal_address_mask = int(address_mask_str, 16)
            except (ValueError, TypeError):
                self.logger.error(
                    f"Invalid address mask '{address_mask_str}', using default FFFFFFFF."
                )
                self._internal_address_mask = 0xFFFFFFFF

            if not self._device_type or not self._device_location:
                self.logger.warning("Cannot open device: Type or Location not configured.")
                return

            interface = None
            devicetype = None
            use_ssl = False
            self._device_baudrate = 115200  # Default

            # Determine device type and interface based on settings
            if self._device_location == "local":
                devicetype = SerialDevice
                interface = Setting.get_by_name("device_path").value
                baud_val = Setting.get_by_name("device_baudrate").value
                if baud_val:
                    self._device_baudrate = int(baud_val)
                if not interface:
                    self.logger.error("Cannot open local device: Path not set.")
                    return

            elif self._device_location == "network":
                devicetype = SocketDevice
                addr = Setting.get_by_name("device_address").value
                port = Setting.get_by_name("device_port").value
                if not addr or not port:
                    self.logger.error("Cannot open network device: Address or Port not set.")
                    return
                interface = (addr, int(port))
                use_ssl = Setting.get_by_name("use_ssl", False).value

            else:  # Includes ser2sock type or others
                devicetype = SocketDevice  # Assume socket for others like ser2sock
                addr = Setting.get_by_name("device_address").value or "localhost"
                port = Setting.get_by_name("device_port").value or 10000
                interface = (addr, int(port))
                use_ssl = Setting.get_by_name("use_ssl", False).value

            # Create and open the device.
            self.logger.info(f"Attempting to open {self._device_location} device: {interface}")
            try:
                device_instance = devicetype(interface=interface)

                if use_ssl:
                    self.logger.info("Attempting SSL connection.")
                    try:
                        # Use session.get for primary key lookup if possible, else filter
                        ca_cert = (
                            db.session.query(Certificate).filter_by(name="AlarmDecoder CA").one()
                        )
                        internal_cert = (
                            db.session.query(Certificate)
                            .filter_by(name="AlarmDecoder Internal")
                            .one()
                        )

                        # Ensure cert objects are loaded (they should be by reconstructor)
                        if (
                            not ca_cert.certificate_obj
                            or not internal_cert.certificate_obj
                            or not internal_cert.key_obj
                        ):
                            raise ValueError("Required certificate objects not loaded.")

                        device_instance.ssl = True
                        device_instance.ssl_ca = ca_cert.certificate_obj
                        device_instance.ssl_certificate = internal_cert.certificate_obj
                        device_instance.ssl_key = internal_cert.key_obj
                        self.logger.info("SSL parameters configured.")

                    except NoResultFound:
                        self.logger.error(
                            "Required SSL certificates (AlarmDecoder CA, AlarmDecoder Internal) not found in database.",
                            exc_info=True,
                        )
                        raise  # Re-raise to prevent opening without SSL when configured
                    except ValueError as verr:
                        self.logger.error(
                            f"Error loading SSL certificate objects: {verr}", exc_info=True
                        )
                        raise  # Re-raise

                # Create the top-level AlarmDecoder object
                self.device = AlarmDecoder(device_instance)
                self.device.internal_address_mask = self._internal_address_mask

                # Bind events before opening
                self.bind_events()

                # Finally, open the connection
                self.device.open(baudrate=self._device_baudrate, no_reader_thread=no_reader_thread)
                # on_open event will set trigger_reopen_device to False

            except NoDeviceError as nde:
                self.logger.error(f"Device open failed: {nde}", exc_info=True)
                self.device = None  # Ensure device is None on failure
                # Don't re-raise, allow thread to retry later
            except SSL.Error as ssl_err:
                self.logger.error(f"SSL connection failed: {ssl_err}", exc_info=True)
                self.device = None
                # Don't re-raise
            except Exception as err:  # Catch other potential errors (permissions, config issues)
                self.logger.error(
                    f"Unexpected error opening device {interface}: {err}", exc_info=True
                )
                self.device = None
                # Don't re-raise

    def close(self):
        """Closes the AlarmDecoder device if open."""
        if self.device:
            self.logger.info("Closing AlarmDecoder device connection.")
            try:
                self.remove_events()
                self.device.close()
            except Exception as e:
                self.logger.error(f"Error during device close: {e}", exc_info=True)
            finally:
                self.device = None  # Ensure device is cleared

    def bind_events(self):
        """Binds the internal event handlers to the AlarmDecoder instance."""
        if not self.device:
            return

        self.logger.debug("Binding AlarmDecoder events.")
        # Use lambdas to ensure 'self' context is passed correctly
        build_event_handler = lambda event_type: lambda sender, **kwargs: self._handle_event(
            event_type, sender, **kwargs
        )
        build_message_handler = lambda msg_type: lambda sender, **kwargs: self._on_message(
            msg_type, sender, **kwargs
        )

        # Basic message handlers
        self.device.on_message += build_message_handler("panel")
        self.device.on_lrr_message += build_message_handler("lrr")
        self.device.on_ready_changed += build_message_handler("ready")
        self.device.on_chime_changed += build_message_handler("chime")
        self.device.on_rfx_message += build_message_handler("rfx")
        self.device.on_expander_message += build_message_handler("exp")
        try:  # AUI might not be in older alarmdecoder versions
            self.device.on_aui_message += build_message_handler("aui")
        except AttributeError:
            self.logger.warning(
                'Could not bind event "on_aui_message": alarmdecoder library might be out of date.'
            )

        # Open/Close handlers
        self.device.on_open += self._on_device_open
        self.device.on_close += self._on_device_close

        # Mapped event handlers
        for event, device_event_name in EVENT_MAP.items():  # Use items()
            try:
                device_handler = getattr(self.device, device_event_name)
                device_handler += build_event_handler(event)
            except AttributeError:
                self.logger.warning(
                    f'Could not bind event "{device_event_name}": alarmdecoder library might be out of date.'
                )

    def remove_events(self):
        """Clears internal event handlers from the AlarmDecoder instance."""
        if not self.device:
            return

        self.logger.debug("Removing AlarmDecoder event bindings.")
        try:
            # Use try-except for each clear in case device state is unusual
            try:
                self.device.on_message.clear()
            except AttributeError:
                pass
            try:
                self.device.on_lrr_message.clear()
            except AttributeError:
                pass
            try:
                self.device.on_expander_message.clear()
            except AttributeError:
                pass
            try:
                self.device.on_aui_message.clear()
            except AttributeError:
                pass  # Ignore if AUI doesn't exist
            try:
                self.device.on_open.clear()
            except AttributeError:
                pass
            try:
                self.device.on_close.clear()
            except AttributeError:
                pass

            # Clear mapped events
            for event, device_event_name in EVENT_MAP.items():  # Use items()
                try:
                    device_handler = getattr(self.device, device_event_name)
                    device_handler.clear()
                except AttributeError:
                    # Warning was already given in bind_events, no need to repeat
                    pass

        except Exception as ex:  # Catch unexpected errors during cleanup
            self.logger.error(f"Unexpected error clearing events: {ex}", exc_info=True)

    def refresh_notifier(self, notifier_id):
        """Refreshes a specific notifier configuration."""
        if self._notifier_system:
            self._notifier_system.refresh_notifier(notifier_id)

    def test_notifier(self, notifier_id):
        """Sends a test message to a specific notifier."""
        if self._notifier_system:
            return self._notifier_system.test_notifier(notifier_id)
        return False  # Or raise error

    def _on_device_open(self, sender):
        """Internal handler for device open events."""
        self.logger.info("AlarmDecoder device connection opened.")
        self.trigger_reopen_device = False
        # Use the new broadcast method
        self.emit_event("device_open")

    def _on_device_close(self, sender):
        """Internal handler for device close events."""
        self.logger.info("AlarmDecoder device connection closed.")
        self.trigger_reopen_device = True
        # Use the new broadcast method
        self.emit_event("device_close")

    def _on_message(self, ftype, sender, **kwargs):
        """Internal handler for raw messages from the device."""
        message = kwargs.get("message", None)
        if message is None:
            return  # Ignore if no message content

        self.last_message_received = str(message)  # Store raw message
        self._last_message_timestamp = time.time()  # Update timestamp

        # Use the new broadcast method
        # Send raw message details
        self.emit_event("message", {"message": str(message), "message_type": ftype})

    def _handle_event(self, ftype, sender, **kwargs):
        """Internal handler for specific AlarmDecoder events (arm, disarm, etc.)."""
        self._last_message_timestamp = time.time()
        event_data = kwargs  # The event arguments are passed as kwargs

        # Send notification via NotificationSystem (within app context)
        with self.app.app_context():
            try:
                if self._notifier_system:
                    errors = self._notifier_system.send(ftype, **event_data)
                    for e in errors:
                        self.logger.error(f"Notifier error: {e}")
            except Exception as e:
                self.logger.error(f"Error during notification processing: {e}", exc_info=True)

        # Use the new broadcast method to send structured event data
        self.emit_event("event", event_data)

    # --- NEW: Flask-SocketIO broadcast method ---
    def emit_event(self, event_name, data=None, namespace="/alarmdecoder"):
        """
        Emits an event to all connected Socket.IO clients in a namespace.

        :param event_name: Name of the Socket.IO event.
        :type event_name: str
        :param data: Dictionary data payload for the event.
        :type data: dict, optional
        :param namespace: The Socket.IO namespace to emit to.
        :type namespace: str, optional
        """
        if data is None:
            data = {}

        try:
            # Use jsonpickle to handle complex types like datetime, then let emit handle final encoding
            # NOTE: Consider if jsonpickle is truly needed or if simpler dicts suffice.
            # If using complex objects directly, ensure they are JSON serializable.
            pickled_data = jsonpickle.encode(data, unpicklable=False)

            # Emit using the imported socketio instance
            # The 'broadcast=True' flag sends to all clients in the namespace
            socketio.emit(event_name, pickled_data, namespace=namespace, broadcast=True)
            logger.debug(
                f"Emitted event '{event_name}' to namespace '{namespace}'"
            )  # Data not logged by default

        except Exception as e:
            self.logger.error(f"Error emitting socket event '{event_name}': {e}", exc_info=True)

    def configure_version_thread(self, timeout: int, disable: bool):
        if self._version_thread:
            self._version_thread.setTimeout(timeout)
            self._version_thread.setDisable(disable)
        else:
            self.logger.warning("Version thread not initialized. Cannot configure.")

    # --- REMOVED OLD BROADCAST METHODS ---
    # def broadcast(self, channel, data={}): ... REMOVED ...
    # def _broadcast_packet(self, packet): ... REMOVED ...
    # def _make_packet(self, channel, data): ... REMOVED ...


# --- Background Threads ---
# (DecoderThread, VersionChecker, CameraChecker, ExportChecker)
# These classes need updates where they call self._decoder.broadcast
# They should call self._decoder.emit_event instead.


class DecoderThread(threading.Thread):
    TIMEOUT = 5

    def __init__(self, decoder):
        threading.Thread.__init__(self)
        self.daemon = True  # Ensure thread exits with main app
        self._decoder = decoder
        self._running = False

    def stop(self):
        self._running = False

    def run(self):
        self._running = True
        self.logger = self._decoder.app.logger  # Get logger instance
        self.logger.info("DecoderThread started.")

        while self._running:
            reopened = False
            try:
                with self._decoder.app.app_context():  # Ensure context for DB access
                    # Handle reopen events
                    if self._decoder.trigger_reopen_device:
                        self.logger.info("Attempting to reconnect to the AlarmDecoder")
                        try:
                            # Pass no_reader_thread=False unless specifically needed
                            self._decoder.open(no_reader_thread=False)
                            # If open succeeds, the on_open handler sets trigger_reopen_device to False
                            if self._decoder.device:  # Check if open actually succeeded
                                reopened = True
                                self.logger.info("Successfully reconnected to AlarmDecoder.")
                            else:
                                self.logger.warning("Reconnect attempt failed, will retry.")

                        except NoDeviceError as err:
                            self.logger.error(f"Device not found during reconnect: {err}")
                        except Exception as err:  # Catch broader errors during open
                            self.logger.error(
                                f"Error during reconnect attempt: {err}", exc_info=True
                            )

                    # Handle service restart events
                    if self._decoder.trigger_restart:
                        self.logger.info("Restart triggered.")
                        self._running = False  # Signal thread to stop
                        self._decoder.stop(restart=True)  # Call decoder stop with restart
                        return  # Exit thread run loop immediately

            except Exception as err:
                # Catch errors in the main loop logic itself
                self.logger.error(f"Error in DecoderThread run loop: {err}", exc_info=True)

            # Wait before next check, sleep longer if just tried to reopen
            sleep_time = (
                self.TIMEOUT * 2
                if self._decoder.trigger_reopen_device and not reopened
                else self.TIMEOUT
            )
            time.sleep(sleep_time)

        self.logger.info("DecoderThread stopped.")


class VersionChecker(threading.Thread):
    TIMEOUT = 60  # Default internal loop sleep

    def __init__(self, decoder):
        threading.Thread.__init__(self)
        self.daemon = True
        self._decoder = decoder
        self._updater = decoder.updater
        self._running = False
        self.logger = decoder.app.logger  # Use app logger

        # Load initial settings within app context if possible, or handle potential errors
        try:
            with decoder.app.app_context():
                self.last_check_time = float(
                    Setting.get_by_name("version_checker_last_check_time", default=0).value
                )
                self.version_checker_timeout = int(
                    Setting.get_by_name("version_checker_timeout", default=600).value
                )
                self.disable_version_checker = Setting.get_by_name(
                    "version_checker_disable", default=False
                ).value
        except Exception as e:
            self.logger.error(f"Failed to load initial VersionChecker settings from DB: {e}")
            # Set safe defaults
            self.last_check_time = 0
            self.version_checker_timeout = 600
            self.disable_version_checker = False

    def stop(self):
        self._running = False

    def setTimeout(self, timeout):
        self.logger.info(f"Updating version check thread timeout to: {timeout} seconds")
        self.version_checker_timeout = int(timeout)

    def setDisable(self, disable):
        status = "Disabled" if disable else "Enabled"
        self.logger.info(f"Updating version check enable/disable to: {status}")
        self.disable_version_checker = disable

    def run(self):
        self._running = True
        self.logger.info("VersionChecker thread started.")
        while self._running:
            if not self.disable_version_checker:
                try:
                    check_time = time.time()
                    # Check if it's time to look for updates
                    if check_time > self.last_check_time + self.version_checker_timeout:
                        self.logger.info(
                            f'Checking for version updates - last check at: {datetime.datetime.fromtimestamp(self.last_check_time).strftime("%Y-%m-%d %H:%M:%S") if self.last_check_time > 0 else "Never"}'
                        )
                        with (
                            self._decoder.app.app_context()
                        ):  # Need context for DB and potentially updater
                            try:
                                self._decoder.updates = self._updater.check_updates()
                                # Use items() for Python 3, handle potential None in value tuple
                                update_available = any(
                                    comp_info and comp_info[0]
                                    for comp_info in self._decoder.updates.values()
                                )

                                # Update Jinja globals (might need lock if accessed concurrently?)
                                current_app.jinja_env.globals["update_available"] = update_available
                                current_app.jinja_env.globals["firmware_update_available"] = (
                                    self._updater.check_firmware()
                                )

                                # Save last check time to DB
                                self.last_check_time = check_time
                                last_check_setting = db.session.merge(
                                    Setting(
                                        name="version_checker_last_check_time",
                                        value=str(self.last_check_time),
                                    )
                                )
                                # db.session.add(last_check_setting) # Merge handles add
                                db.session.commit()
                                self.logger.info(
                                    f"Update check complete. Update available: {update_available}"
                                )

                            except Exception as err_inner:
                                self.logger.error(
                                    f"Error during update check: {err_inner}", exc_info=True
                                )
                                db.session.rollback()  # Rollback DB changes on error

                except Exception as err_outer:
                    self.logger.error(
                        f"Error in VersionChecker run loop: {err_outer}", exc_info=True
                    )

            # Sleep regardless of whether check was performed or disabled
            # Use a shorter internal sleep and check time logic above
            # This makes stop() more responsive
            timeout_div = int(self.version_checker_timeout / 10.0)
            sleep_duration = min(self.TIMEOUT, max(1, timeout_div))
            time.sleep(sleep_duration)

        self.logger.info("VersionChecker thread stopped.")


class CameraChecker(threading.Thread):
    TIMEOUT = 1

    def __init__(self, decoder):
        threading.Thread.__init__(self)
        self.daemon = True
        self._decoder = decoder
        self._running = False
        # Initialize CameraSystem only if needed/safe outside app context
        # Or initialize it inside run within app context if it needs config/db
        self._cameras = CameraSystem()
        self.logger = decoder.app.logger

    def stop(self):
        self._running = False

    def run(self):
        self._running = True
        self.logger.info("CameraChecker thread started.")
        while self._running:
            try:
                with self._decoder.app.app_context():  # Context likely needed for DB access
                    self._cameras.refresh_camera_ids()  # Assumes this uses current_app or db
                    active_ids = self._cameras.get_camera_ids()
                    if active_ids:
                        self.logger.debug(f"Checking active camera IDs: {active_ids}")
                        for cam_id in active_ids:
                            # This probably writes image to disk, ensure paths are correct
                            self._cameras.write_image(cam_id)

            except Exception as err:
                self.logger.error(f"Error in CameraChecker: {err}", exc_info=True)

            time.sleep(self.TIMEOUT)
        self.logger.info("CameraChecker thread stopped.")


class ExportChecker(threading.Thread):
    TIMEOUT = 60  # Check frequency (in seconds)

    def __init__(self, decoder):
        threading.Thread.__init__(self)
        self.daemon = True
        self._decoder = decoder
        self._running = False
        self.logger = decoder.app.logger
        self.first_run = True  # Skip export on first check after start

        # Load initial settings (needs app context)
        self.export_frequency = 0
        self.last_check_time = 0
        self.email_enable = False
        self.local_storage = False
        self.days_to_keep = 7
        self._mailer = None
        self._exporter = None
        self.send_from = None
        self.to = []
        self.subject = "AlarmDecoder Settings Database Backup"
        self.body = "AlarmDecoder Settings Database Backup\r\n"
        try:
            # Initial param load requires app context
            with self._decoder.app.app_context():
                self.prepParams()
        except Exception as e:
            self.logger.error(f"Failed to initialize ExportChecker parameters: {e}", exc_info=True)

    def prepParams(self):
        """Loads/reloads parameters from DB settings (requires app context)."""
        self.logger.debug("Loading/reloading export parameters.")
        # Email settings
        server = Setting.get_by_name("system_email_server", default="localhost").value
        port = Setting.get_by_name("system_email_port", default=25).value
        tls = Setting.get_by_name("system_email_tls", default=False).value
        auth_required = Setting.get_by_name("system_email_auth", default=False).value
        username = Setting.get_by_name("system_email_username", default=None).value
        password = Setting.get_by_name("system_email_password", default=None).value
        self.send_from = Setting.get_by_name("system_email_from", default="root@alarmdecoder").value
        mailer_to_addr = Setting.get_by_name("export_mailer_to", default=None).value
        self.to = [mailer_to_addr] if mailer_to_addr else []

        # Export settings
        self.export_frequency = int(
            Setting.get_by_name("export_frequency", default=0).value
        )  # Stored as int
        self.local_storage = Setting.get_by_name("enable_local_file_storage", default=False).value
        self.local_path = Setting.get_by_name(
            "export_local_path", default=os.path.join(INSTANCE_FOLDER_PATH, "exports")
        ).value
        self.email_enable = Setting.get_by_name("export_email_enable", default=False).value
        self.days_to_keep = int(Setting.get_by_name("days_to_keep", default=7).value)
        self.last_check_time = int(Setting.get_by_name("export_last_check_time", default=0).value)

        # Initialize helpers
        self._mailer = Mailer(server, port, tls, auth_required, username, password)
        self._exporter = Exporter()  # Exporter now uses config for path

        self.logger.info(
            f"Export parameters set: Freq={self.export_frequency}s, Email={self.email_enable}, Local={self.local_storage}"
        )

    def stop(self):
        self._running = False

    # Remove update methods, rely on prepParams being called periodically or on signal
    # def updateFrequency(self, frequency): ... REMOVE ...
    # ... (remove other update methods) ...

    def run(self):
        self._running = True
        self.logger.info("ExportChecker thread started.")
        while self._running:
            try:
                # Reload params periodically in case settings changed in UI
                # Or implement a signaling mechanism
                with self._decoder.app.app_context():
                    self.prepParams()  # Reload settings

                if self.export_frequency > 0:  # Only run if frequency is set
                    now = time.time()
                    # Check if it's time to export
                    if now > self.last_check_time + self.export_frequency:
                        self.logger.info(
                            f'Scheduled export check - last run at: {datetime.datetime.fromtimestamp(self.last_check_time).strftime("%Y-%m-%d %H:%M:%S") if self.last_check_time > 0 else "Never"}'
                        )

                        if not self.first_run:
                            with (
                                self._decoder.app.app_context()
                            ):  # Need context for exporter/mailer
                                try:
                                    self._exporter.exportSettings()  # Creates archive in memory
                                    full_path = self._exporter.writeFile()  # Writes to disk
                                    self.logger.info(f"Settings exported to {full_path}")

                                    files_to_attach = [full_path] if full_path else []

                                    # Send email if enabled and file created
                                    if self.email_enable and files_to_attach and self.to:
                                        self.logger.info(f"Sending export email to: {self.to}")
                                        # Ensure mailer parameters are up-to-date (handled by prepParams)
                                        self._mailer.send_mail(
                                            self.send_from,
                                            self.to,
                                            self.subject,
                                            self.body,
                                            files_to_attach,
                                        )
                                        self.logger.info("Export email sent.")

                                    # Remove file if local storage disabled AND email was attempted (or not enabled)
                                    if not self.local_storage and full_path:
                                        self.logger.info(
                                            f"Removing non-persisted export file: {full_path}"
                                        )
                                        self._exporter.removeFile()

                                    # Clean up old files regardless
                                    self.logger.info(
                                        f"Cleaning up export files older than {self.days_to_keep} days."
                                    )
                                    self._exporter.removeOldFiles(self.days_to_keep)

                                    # Update last check time in DB
                                    self.last_check_time = now
                                    last_check_setting = db.session.merge(
                                        Setting(
                                            name="export_last_check_time",
                                            value=str(int(self.last_check_time)),
                                        )
                                    )
                                    # db.session.add(last_check_setting) # Merge handles add
                                    db.session.commit()

                                except Exception as export_err:
                                    self.logger.error(
                                        f"Error during settings export/send: {export_err}",
                                        exc_info=True,
                                    )
                                    db.session.rollback()  # Rollback DB changes on error

                        else:  # End of first_run check
                            self.logger.info("Skipping export on first run.")
                            self.first_run = False
                            # Still update time to prevent immediate run next cycle if frequency is short
                            self.last_check_time = now
                            with self._decoder.app.app_context():
                                last_check_setting = db.session.merge(
                                    Setting(
                                        name="export_last_check_time",
                                        value=str(int(self.last_check_time)),
                                    )
                                )
                                db.session.commit()

                else:  # export_frequency <= 0
                    # If frequency is 0, maybe sleep longer?
                    pass

            except Exception as err_outer:
                self.logger.error(f"Error in ExportChecker run loop: {err_outer}", exc_info=True)

            # Sleep based on configured timeout or a default
            sleep_duration = self.TIMEOUT
            # Optionally adjust sleep based on export_frequency if > 0
            # if self.export_frequency > 0:
            #      sleep_duration = min(self.TIMEOUT, max(60, self.export_frequency / 10.0))
            time.sleep(sleep_duration)

        self.logger.info("ExportChecker thread stopped.")


# --- REMOVE Old SocketIO Server Creation and Blueprint ---
# def create_decoder_socket(app): ... REMOVED ...
# decodersocket = Blueprint('sock', __name__) ... REMOVED ...
# @decodersocket.route('/<path:remaining>') ... REMOVED ...

# --- Flask-SocketIO Namespace ---
# Register the namespace with the global socketio instance


class DecoderNamespace(Namespace):
    """
    Socket.IO namespace for handling communication with clients using Flask-SocketIO.
    """

    # No __init__ needed typically, unless passing specific args

    # Use Flask-SocketIO connection event decorator
    @socketio.on("connect", namespace="/alarmdecoder")
    def on_connect(self):
        """Handles new Socket.IO client connections."""
        # Session ID from Flask-SocketIO request context
        sid = request.sid  # type: ignore[attr-defined]
        try:
            # Use Flask context directly
            with (
                current_app.app_context()
            ):  # Ensure context if needed, though usually available in handlers
                # Access decoder via current_app
                decoder = getattr(current_app, "decoder", None)
                logger.info(f"SocketIO client connecting: {sid} from {request.remote_addr}")

                # Authentication / Setup check (adapted from old recv_connect)
                user_id = None
                if "user_id" in session:  # Use Flask session
                    user_id = session["user_id"]
                    # Optional: Re-validate user_id here if needed

                setup_stage = Setting.get_by_name("setup_stage").value

                # Allow connection if setup is complete OR a user is logged in (has user_id in session)
                # OR if setup is not complete (to allow setup pages to use socket?) - ADJUST LOGIC AS NEEDED
                allow_connection = (setup_stage == SETUP_COMPLETE) or user_id is not None

                if allow_connection:
                    logger.info(
                        f"Client {sid} authenticated/authorized for '/alarmdecoder' namespace."
                    )
                    # No ACL methods needed in Flask-SocketIO, just use decorators for events
                    # Store auth status in Flask-SocketIO session if needed by other events
                    # from flask_socketio import session as sio_session # Alias if needed
                    # sio_session['authenticated'] = True

                    # Example: Send current status immediately on connect
                    if decoder and decoder.device and decoder.device.last_message:
                        self.emit(
                            "message",
                            {
                                "message": str(decoder.device.last_message.raw),
                                "message_type": "panel",
                            },
                            room=sid,
                        )  # Send only to connecting client
                else:
                    logger.warning(
                        f"Client {sid} not authorized for '/alarmdecoder' namespace (Setup Stage: {setup_stage}, UserID: {user_id}). Disconnecting."
                    )
                    # Disconnect unauthorized clients
                    # from flask_socketio import disconnect # Import if needed
                    # disconnect(sid=sid, namespace='/alarmdecoder') # Might cause issues if called within connect handler, check docs
                    return False  # Returning False from connect handler usually disconnects

        except Exception as e:
            logger.error(f"Error during SocketIO connect handler: {e}", exc_info=True)
            return False  # Disconnect on error

    # Use Flask-SocketIO disconnection event decorator
    @socketio.on("disconnect", namespace="/alarmdecoder")
    def on_disconnect(self):
        """Handles Socket.IO client disconnections."""
        logger.info(f"SocketIO client disconnected: {request.sid}")  # type: ignore[attr-defined]
        # Perform any cleanup related to this session if needed

    # Keep other event handlers, ensure they use current_app.decoder or similar
    @socketio.on("keypress", namespace="/alarmdecoder")
    def on_keypress(self, key):
        """Handles websocket keypress events."""
        try:
            # Access decoder via current_app
            decoder = getattr(current_app, "decoder", None)
            if not decoder or not decoder.device:
                logger.warning("Keypress received but no device available.")
                return

            # Use a mapping or cleaner structure?
            key_map = {
                1: AlarmDecoder.KEY_F1,
                2: AlarmDecoder.KEY_F2,
                3: AlarmDecoder.KEY_F3,
                4: AlarmDecoder.KEY_F4,
                5: AlarmDecoder.KEY_PANIC,
            }  # Panic key mapping? Check AlarmDecoder consts

            if key in key_map:
                decoder.device.send(key_map[key])
            else:  # Assume direct key press character/string
                decoder.device.send(str(key))  # Ensure it's a string

            logger.debug(f"Sent keypress '{key}' to device.")

        except (CommError, AttributeError):
            logger.error("Error sending keypress to device", exc_info=True)
        except Exception as e:
            logger.error(f"Unexpected error processing keypress: {e}", exc_info=True)

    @socketio.on("firmwareupload", namespace="/alarmdecoder")
    def on_firmwareupload(self, *args):  # Data might be passed in args/kwargs
        """Handles firmware upload initiation via Socket.IO."""
        # Access decoder via current_app
        decoder = getattr(current_app, "decoder", None)
        if not decoder:
            logger.error("Cannot perform firmware upload: Decoder not initialized.")
            return

        reopen_with_reader = False
        try:
            with current_app.app_context():  # Ensure context for DB/settings access
                # Check if firmware details are set
                if not decoder.firmware_file or decoder.firmware_length < 0:
                    logger.error("Firmware file details not set before upload requested.")
                    # Use emit back to the specific client (request.sid)
                    emit("firmwareupload", {"stage": "STAGE_ERROR", "error": "Firmware file not prepared."}, room=request.sid)  # type: ignore[attr-defined]
                    return

                logger.info(f"Starting firmware update: {decoder.firmware_file}")
                # Use emit for progress updates back to client
                emit("firmwareupload", {"stage": "STAGE_START"}, room=request.sid)  # type: ignore[attr-defined]

                # Ensure device is closed without reader thread for update
                decoder.close()
                decoder.open(no_reader_thread=True)  # Reopen without reader

                if not decoder.device:
                    raise RuntimeError("Failed to reopen device for firmware update.")

                # Pass update callback to FirmwareUpdater? Check FirmwareUpdater usage.
                # This example assumes FirmwareUpdater handles its own progress/completion.
                firmware_updater = FirmwareUpdater(
                    device=decoder.device,  # Pass device
                    filename=decoder.firmware_file,
                    length=decoder.firmware_length,
                )
                # Add callbacks if FirmwareUpdater supports them for progress
                # firmware_updater.on_progress += lambda stage, progress: emit(...)

                firmware_updater.update()  # Blocking call? Consider thread/async?

                if firmware_updater.completed:
                    logger.info("Firmware update completed successfully.")
                    emit("firmwareupload", {"stage": "STAGE_FINISHED"}, room=request.sid)  # type: ignore[attr-defined]
                    reopen_with_reader = True  # Reopen normally after success
                else:
                    # Updater might have its own error status/message
                    logger.error("Firmware update failed or did not complete.")
                    emit("firmwareupload", {"stage": "STAGE_ERROR", "error": "Firmware update did not complete."}, room=request.sid)  # type: ignore[attr-defined]

        except Exception as err:
            logger.error(f"Error during firmware upload process: {err}", exc_info=True)
            emit("firmwareupload", {"stage": "STAGE_ERROR", "error": f"Error: {err}"}, room=request.sid)  # type: ignore[attr-defined]

        finally:
            # Always try to close and reopen the device in normal mode (with reader)
            logger.info(
                f"Reopening device after firmware update attempt (reader={reopen_with_reader})."
            )
            decoder.close()
            try:
                # Reopen with reader thread enabled by default after attempt
                decoder.open(no_reader_thread=False)
            except Exception as reopen_err:
                logger.error(
                    f"Failed to reopen device after firmware update: {reopen_err}", exc_info=True
                )
            # Clear firmware state regardless of success?
            decoder.firmware_file = None
            decoder.firmware_length = -1

    @socketio.on("test", namespace="/alarmdecoder")
    def on_test(self, *args):
        """Handles device test initiation via Socket.IO."""
        logger.info("Device test initiated via SocketIO.")
        # Access decoder via current_app
        decoder = current_app.decoder
        if not decoder:
            logger.error("Cannot perform test: Decoder not initialized.")
            return

        try:
            # Run tests sequentially, emitting results back to the specific client
            self._test_open(decoder)  # Pass decoder instance
            time.sleep(0.5)  # Allow time between tests
            self._test_config(decoder)
            time.sleep(0.5)
            self._test_send(decoder)
            time.sleep(0.5)
            self._test_receive(decoder)
            logger.info("Device tests complete.")

        except Exception as e:
            logger.error(f"Error running device tests: {e}", exc_info=True)
            # Emit a general error back to client
            emit("test", {"test": "overall", "results": "ERROR", "details": f"Error during testing: {e}"}, room=request.sid)  # type: ignore[attr-defined]

    # --- Test Helper Methods (now outside class or passed decoder) ---
    # Pass decoder instance to these helpers or access via current_app.decoder
    # Changed broadcast calls to emit back to the requesting client (request.sid)

    def _test_open(self, decoder):
        """Tests opening the AlarmDecoder device."""
        logger.debug("Running test: Open Device")
        results, details = "PASS", ""
        try:
            decoder.close()
            decoder.open()  # Assumes open handles context if needed for settings
            if not decoder.device:  # Check if open actually succeeded
                raise NoDeviceError("Device object not created after open attempt.")

        except NoDeviceError as err:
            results, details = "FAIL", f"Device not found or failed to open: {err}"
            logger.error(f"Test Open Failed: {err}", exc_info=True)
        except Exception as err:
            results, details = "FAIL", f"Unexpected error opening device: {err}"
            logger.error(f"Test Open Failed (Unexpected): {err}", exc_info=True)
        finally:
            emit("test", {"test": "open", "results": results, "details": details}, room=request.sid)  # type: ignore[attr-defined]

    def _test_config(self, decoder):
        """Tests retrieving and saving the AlarmDecoder configuration."""
        logger.debug("Running test: Config Save/Receive")
        if not decoder or not decoder.device:
            emit("test", {"test": "config", "results": "FAIL", "details": "Device not open/available."}, room=request.sid)  # type: ignore[attr-defined]
            return

        config_received_flag = threading.Event()
        results, details = "TIMEOUT", "Test timed out waiting for config response."

        def on_config_received(device, **kwargs):
            nonlocal results, details
            logger.debug("Test Config: on_config_received triggered.")
            results, details = "PASS", ""
            config_received_flag.set()  # Signal that config was received

        # Use a simple timeout mechanism
        timeout_seconds = 10
        start_time = time.time()

        try:
            # Attach temporary handler
            decoder.device.on_config_received += on_config_received

            # Load settings within app context
            with current_app.app_context():
                panel_mode = Setting.get_by_name("panel_mode").value
                keypad_address = Setting.get_by_name("keypad_address").value
                address_mask = Setting.get_by_name("address_mask").value
                lrr_enabled = Setting.get_by_name("lrr_enabled").value
                zone_expanders = Setting.get_by_name("emulate_zone_expanders").value
                relay_expanders = Setting.get_by_name("emulate_relay_expanders").value
                deduplicate = Setting.get_by_name("deduplicate").value

                # Basic validation/defaults
                if not panel_mode:
                    panel_mode = "ADEMCO"
                if not keypad_address:
                    keypad_address = 18
                if not address_mask:
                    address_mask = "FFFFFFFF"

                zx_str = (zone_expanders or "").split(",")
                rx_str = (relay_expanders or "").split(",")
                zx = [x.strip().lower() == "true" for x in zx_str if x.strip()]
                rx = [x.strip().lower() == "true" for x in rx_str if x.strip()]

            # Apply config to device
            decoder.device.mode = panel_mode
            decoder.device.address = int(keypad_address)
            decoder.device.address_mask = int(address_mask, 16)
            decoder.device.emulate_zone = zx
            decoder.device.emulate_relay = rx
            decoder.device.emulate_lrr = bool(lrr_enabled)
            decoder.device.deduplicate = bool(deduplicate)

            logger.debug("Test Config: Sending SAVE command.")
            decoder.device.save_config()

            # Wait for the event or timeout
            config_received_flag.wait(timeout=timeout_seconds)  # Wait for signal

        except Exception as err:
            results, details = "FAIL", f"Error sending config command: {err}"
            logger.error(f"Test Config Failed: {err}", exc_info=True)
        finally:
            # Ensure handler is removed
            if (
                hasattr(decoder, "device")
                and decoder.device
                and on_config_received in decoder.device.on_config_received
            ):
                decoder.device.on_config_received.remove(on_config_received)
            # Emit final result
            emit("test", {"test": "config", "results": results, "details": details}, room=request.sid)  # type: ignore[attr-defined]

    def _test_send(self, decoder):
        """Tests keypress sending functionality."""
        logger.debug("Running test: Send Keypress")
        if not decoder or not decoder.device:
            emit("test", {"test": "send", "results": "FAIL", "details": "Device not open/available."}, room=request.sid)  # type: ignore[attr-defined]
            return

        send_ok_flag = threading.Event()
        results, details = "TIMEOUT", "Test timed out waiting for send confirmation."

        def on_sending_received(device, status, message):
            nonlocal results, details
            logger.debug(f"Test Send: on_sending_received triggered with status {status}.")
            if status == True:
                # Note: AlarmDecoder library might just pass True/False
                results, details = "PASS", ""
            else:
                results, details = "FAIL", "Device reported send failure. Check wiring/address."
            send_ok_flag.set()

        timeout_seconds = 10
        try:
            decoder.device.on_sending_received += on_sending_received
            logger.debug("Test Send: Sending '*' key.")
            decoder.device.send("*\r")  # Send a harmless key

            # Wait for event or timeout
            send_ok_flag.wait(timeout=timeout_seconds)

        except Exception as err:
            results, details = "FAIL", f"Error sending command: {err}"
            logger.error(f"Test Send Failed: {err}", exc_info=True)
        finally:
            if (
                hasattr(decoder, "device")
                and decoder.device
                and on_sending_received in decoder.device.on_sending_received
            ):
                decoder.device.on_sending_received.remove(on_sending_received)
            emit("test", {"test": "send", "results": results, "details": details}, room=request.sid)  # type: ignore[attr-defined]

    def _test_receive(self, decoder):
        """Tests message received events."""
        logger.debug("Running test: Receive Message")
        if not decoder or not decoder.device:
            emit("test", {"test": "recv", "results": "FAIL", "details": "Device not open/available."}, room=request.sid)  # type: ignore[attr-defined]
            return

        message_received_flag = threading.Event()
        results, details = "TIMEOUT", "Test timed out waiting for message from device."

        def on_message(device, message):
            nonlocal results, details
            logger.debug("Test Receive: on_message triggered.")
            results, details = "PASS", ""
            message_received_flag.set()

        timeout_seconds = 10
        try:
            decoder.device.on_message += on_message
            # Sending a keypress might trigger a response message
            logger.debug("Test Receive: Sending '*' key to provoke response.")
            decoder.device.send("*\r")

            # Wait for event or timeout
            message_received_flag.wait(timeout=timeout_seconds)

        except Exception as err:
            results, details = "FAIL", f"Error during receive test: {err}"
            logger.error(f"Test Receive Failed: {err}", exc_info=True)
        finally:
            if (
                hasattr(decoder, "device")
                and decoder.device
                and on_message in decoder.device.on_message
            ):
                decoder.device.on_message.remove(on_message)
            emit("test", {"test": "recv", "results": results, "details": details}, room=request.sid)  # type: ignore[attr-defined]


# --- Removed create_decoder_socket and decodersocket blueprint ---
