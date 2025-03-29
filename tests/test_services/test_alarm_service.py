from ad2web.app.services.alarm_service import setup_alarmdecoder

def test_setup_alarmdecoder(app):
    setup_alarmdecoder(app)
    assert hasattr(app, 'decoder')
    assert app.decoder is not None
