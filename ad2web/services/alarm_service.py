# ad2web/services/alarm_service.py
from alarmdecoder.decoder import AlarmDecoder

def setup_alarmdecoder(app):
    decoder = AlarmDecoder()
    app.decoder = decoder
