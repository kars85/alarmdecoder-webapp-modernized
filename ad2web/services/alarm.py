# ad2web/services/alarm.py

from alarmdecoder.devices.mock_device import MockDevice
from alarmdecoder.decoder import AlarmDecoder

device = MockDevice()
decoder = AlarmDecoder(device=device)
