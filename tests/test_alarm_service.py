import pytest
from unittest.mock import MagicMock, patch
from ad2web.services import alarm_service
from ad2web.services.alarm_service import setup_alarmdecoder

def test_setup_alarmdecoder(app):
    setup_alarmdecoder(app)
    assert hasattr(app, 'decoder')
    assert app.decoder is not None

@pytest.fixture
def fake_decoder():
    mock_device = MagicMock()
    decoder = MagicMock()
    decoder.device = mock_device
    return decoder


def test_send_panel_command_success(app, fake_decoder):
    with app.app_context():
        with patch("ad2web.services.alarm_service.get_decoder", return_value=fake_decoder):
            assert fake_decoder.device is not None  # sanity
            alarm_service.send_panel_command("1234")
            fake_decoder.device.send.assert_called_once_with("1234\r")


def test_send_panel_command_no_device(app, caplog):
    fake_decoder = MagicMock()
    fake_decoder.device = None
    with app.app_context():
        with patch("ad2web.services.alarm_service.get_decoder", return_value=fake_decoder):
            alarm_service.send_panel_command("1234")
            assert "no device available" in caplog.text.lower()

def test_send_panel_command_empty_string(app, fake_decoder):
    with app.app_context():
        with patch("ad2web.services.alarm_service.get_decoder", return_value=fake_decoder):
            alarm_service.send_panel_command("")
            fake_decoder.device.send.assert_called_once_with("\r")

def test_send_panel_command_none_input(app, fake_decoder):
    with app.app_context():
        with patch("ad2web.services.alarm_service.get_decoder", return_value=fake_decoder):
            alarm_service.send_panel_command(None)
            fake_decoder.device.send.assert_called_once_with("None\r")

def test_send_panel_command_missing_send(app, caplog):
    decoder = MagicMock()
    decoder.device = MagicMock()
    del decoder.device.send
    with app.app_context():
        with patch("ad2web.services.alarm_service.get_decoder", return_value=decoder):
            alarm_service.send_panel_command("1234")
            assert "no send method" in caplog.text.lower()

