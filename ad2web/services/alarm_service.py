# ad2web/services/alarm_service.py

from alarmdecoder.decoder import AlarmDecoder
from alarmdecoder.devices.base_device import Device

class MockDevice(Device):
    """
    A mock device for testing AlarmDecoder without real hardware or sockets.
    """

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
        return b''

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
