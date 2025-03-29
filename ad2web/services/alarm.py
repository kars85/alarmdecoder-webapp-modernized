# ad2web/services/alarm.py

from alarmdecoder.decoder import AlarmDecoder

def setup_decoder(app):
    decoder = AlarmDecoder()
    app.decoder = decoder  # Store instance on the app object
