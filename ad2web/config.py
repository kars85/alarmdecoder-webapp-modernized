#ad2web/config.py
import os
from .utils import INSTANCE_FOLDER_PATH

class BaseConfig(object):
    PROJECT = "ad2web"
    PROJECT_ROOT = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))

    DEBUG = False
    TESTING = False
    SECRET_KEY = 'dev'
    ADMINS = ['youremail@yourdomain.com']

    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    UPLOAD_FOLDER = os.path.join(INSTANCE_FOLDER_PATH, 'uploads')
    LOG_FOLDER = os.path.join(INSTANCE_FOLDER_PATH, 'logs')

    REMEMBER_COOKIE_SECURE = False
    REMEMBER_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SECURE = False
    SESSION_COOKIE_HTTPONLY = True


class DefaultConfig(BaseConfig):
    DEBUG = True
    SQLALCHEMY_ECHO = False
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_DATABASE_URI = f'sqlite:///{INSTANCE_FOLDER_PATH}/db.sqlite'

    ACCEPT_LANGUAGES = ['zh']
    BABEL_DEFAULT_LOCALE = 'en'

    CACHE_TYPE = 'simple'
    CACHE_DEFAULT_TIMEOUT = 60

    MAIL_DEBUG = True
    MAIL_SERVER = 'localhost'
    MAIL_PORT = 25
    MAIL_USERNAME = ''
    MAIL_PASSWORD = ''
    MAIL_DEFAULT_SENDER = 'test@example.com'
    MAIL_SUPPRESS_SEND = True
    OPENID_FS_STORE_PATH = os.path.join(INSTANCE_FOLDER_PATH, 'openid')
    ALARMDECODER_LIBRARY_PATH = os.path.join('/opt', 'alarmdecoder')


# In ad2web/config.py
class TestConfig(BaseConfig): # Make sure it inherits if needed, or define all needed keys
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:' # Or 'sqlite://'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = False
    SECRET_KEY = 'test'
    # ---> ADD THESE <---
    MAIL_SUPPRESS_SEND = True   # Don't send emails during tests
    MAIL_DEFAULT_SENDER = 'test@testing.com' # Provide a default
    # Add any other MAIL_ settings needed by your app/extensions, even if suppressing send


class ProductionConfig(BaseConfig):
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///prod.sqlite')
    SECRET_KEY = os.getenv('SECRET_KEY', 'replace-this')
