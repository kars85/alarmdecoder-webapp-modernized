from flask import Flask
from dotenv import load_dotenv
from ad2web.extensions import db, login_manager, babel
from ad2web.services.alarm_service import setup_alarmdecoder
from ad2web.blueprints.main import main as main_blueprint
from ad2web.config import DefaultConfig

load_dotenv()

def create_app(config_class=None):
    # FIX: Ensure config_class is always defined
    if config_class is None:
        config_class = DefaultConfig

    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)

    db.init_app(app)
    login_manager.init_app(app)
    babel.init_app(app)

    setup_alarmdecoder(app)
    app.register_blueprint(main_blueprint)

    return app
