# ad2web/services/alarm_service.py

from alarmdecoder.decoder import AlarmDecoder
from alarmdecoder.devices.base_device import Device


class MockDevice(Device):

    def __init__(self):
        super().__init__()
        self.is_open = True
        self.read_buffer = []
        self.write_buffer = []

    def open(self):
        self.is_open = True

    def close(self):
        self.is_open = False

    def write(self, data):
        self.write_buffer.append(data)

    def readline(self):
        if self.read_buffer:
            return self.read_buffer.pop(0)
        return b""

    def inject(self, data):
        """
        Simulate receiving data from the device.
        """
        self.read_buffer.append(data.encode("utf-8"))

    def fileno(self):
        return -1  # Mocked value for compatibility


def setup_alarmdecoder(app):
    """
    Initializes the AlarmDecoder using a mock device and attaches it to the app context.
    """
    device = MockDevice()
    decoder = AlarmDecoder(device=device)
    app.decoder = decoder


def get_decoder():
    from flask import current_app

    return getattr(current_app, "decoder", None)


def send_panel_command(cmd: str):
    """
    Sends a raw command to the panel via the AlarmDecoder.
    """
    from flask import current_app

    decoder = get_decoder()
    if not decoder or not decoder.device:
        current_app.logger.warning("No device available to send command.")
        return

    if not hasattr(decoder.device, "send"):
        current_app.logger.warning("Device has no send method.")
        return

    try:
        decoder.device.send(str(cmd) + "\r")
    except Exception as e:
        current_app.logger.error(f"Failed to send command: {e}")
