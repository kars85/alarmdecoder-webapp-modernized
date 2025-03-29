import os
from flask import Flask
from ad2web.utils import make_dir, INSTANCE_FOLDER_PATH, LOG_FOLDER
from ad2web.extensions import db, login_manager, babel
from ad2web.services.alarm_service import setup_alarmdecoder
from ad2web.blueprints.main import main as main_blueprint

def create_app():
    app = Flask(__name__, instance_relative_config=True)

    # Create folders safely
    make_dir(INSTANCE_FOLDER_PATH)
    make_dir(LOG_FOLDER)
    make_dir(UPLOAD_FOLDER)
    make_dir(OPENID_FS_STORE_PATH)
    app.config.from_mapping(
        SECRET_KEY='dev',
        SQLALCHEMY_DATABASE_URI='sqlite:///alarmdecoder.db',
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        BABEL_DEFAULT_LOCALE='en',
    )

    db.init_app(app)
    login_manager.init_app(app)
    babel.init_app(app)

    setup_alarmdecoder(app)
    app.register_blueprint(main_blueprint)

    return app
