import pytest
from ad2web.services.alarm_service import MockDevice

def test_mock_device_write_and_readline():
    device = MockDevice()
    device.inject("test message")
    assert device.readline() == b"test message"
    assert device.readline() == b""  # Empty after buffer is drained

def test_mock_device_open_close():
    device = MockDevice()
    device.is_open = False
    device.open()
    assert device.is_open is True
    device.close()
    assert device.is_open is False

def test_mock_device_write_buffer():
    device = MockDevice()
    device.write("hello")
    device.write("world")
    assert device.write_buffer == ["hello", "world"]

def test_mock_device_fileno():
    device = MockDevice()
    assert device.fileno() == -1