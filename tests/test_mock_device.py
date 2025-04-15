import pytest
from ad2web.services.alarm_service import MockDevice

def test_mock_device_write_and_readline():
    device = MockDevice()
    device.inject("test message")
    assert device.readline() == b"test message"
    assert device.readline() == b""  # Empty after buffer is drained

def test_mock_device_write_buffer():
    device = MockDevice()
    device.write("hello")
    device.write("world")
    assert device.write_buffer == ["hello", "world"]

def test_mock_device_fileno():
    device = MockDevice()
    assert device.fileno() == -1

def test_mock_device_open_close():
    device = MockDevice()
    assert device.is_open is True
    device.close()
    assert not device.is_open
    device.open()
    assert device.is_open is True

def test_mock_device_inject_and_readline():
    device = MockDevice()
    device.inject("test123")
    assert device.readline() == b"test123"
    assert device.readline() == b""  # Buffer now empty
