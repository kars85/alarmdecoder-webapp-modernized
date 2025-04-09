# -*- coding: utf-8 -*-
# In ad2web/settings/constants.py

from ..settings import Setting

from ..notifications import Notification, NotificationSetting, NotificationMessage
from ..zones import Zone
from ..keypad import KeypadButton
from ..cameras import Camera
from ..api import APIKey

HOSTS_FILE = '/etc/hosts'
HOSTNAME_FILE = '/etc/hostname'
NETWORK_FILE = '/etc/network/interfaces'

NONE = 0
DAILY = 86400
WEEKLY = 7 * DAILY
MONTHLY = 30 * DAILY

import importlib

# Function to dynamically import User and related constants
def get_user_and_detail():
    user_module = importlib.import_module('ad2web.user')
    return user_module.User, user_module.USER_ROLE, user_module.USER_STATUS, user_module.ADMIN

# Function to dynamically import Certificate
def get_certificates():
    certificate_module = importlib.import_module('ad2web.certificate')
    return certificate_module.Certificate

# DO NOT call these functions at module level
# We'll use them only when needed inside functions or classes

# Define EXPORT_MAP within a function to avoid circular imports
def get_export_map():
    User, USER_ROLE, USER_STATUS, ADMIN = get_user_and_detail()
    UserDetail = User.user_detail.property.mapper.class_
    Certificate = get_certificates()

    return {
        'settings.json': Setting,
        'certificates.json': Certificate,
        'notifications.json': Notification,
        'notification_settings.json': NotificationSetting,
        'notification_messages.json': NotificationMessage,
        'users.json': User,
        'user_details.json': UserDetail,
        'zones.json': Zone,
        'buttons.json': KeypadButton,
        'cameras.json': Camera,
        'apikeys.json': APIKey
    }

IP_CHECK_SERVER_URL = "https://www.httpbin.org/ip"

KNOWN_MODULES = [ 'heapq', 'code', 'functools', 'random', 'cffi', 'tty', 'datetime', 'sysconfig', 'gc', 'pty', 'xml',
 'importlib', 'flask', 'base64', 'collections', 'imp', 'itsdangerous', 'ConfigParser', 'zipimport',
 'SocketServer', 'string', 'zipfile', 'httplib2', 'textwrap', 'markupsafe', 'jinja2', 'subprocess', 'twilio', 'decimal',
 'compiler', 'httplib', 'resource', 'bisect', 'quopri', 'uuid', 'psutil', 'token', 'greenlet', 'usb', 'signal', 'dis',
 'cStringIO', 'openid', 'locale', 'stat', 'atexit', 'gevent', 'HTMLParser', 'encodings',
 'BaseHTTPServer', 'jsonpickle', 'calendar', 'abc', 'threading', 'warnings', 'tarfile', 'urllib', 're',
 'werkzeug', 'posix', 'email', 'math', 'cgi', 'blinker', 'ast', 'UserDict', 'inspect', 'urllib2', 'Queue',
 'exceptions', 'ctypes', 'codecs', 'posixpath', 'fcntl', 'logging', 'socket', 'thread', 'StringIO', 'traceback', 'unicodedata',
 'weakref', 'tempfile', 'itertools', 'opcode', 'wtforms', 'os', 'marshal', 'alembic', 'pprint', 'binascii', 'unittest',
 'pycparser', 'chump', 'pygments', 'operator', 'array', 'gntp', 'select', 'pkgutil', 'platform', 'errno', 'cv2', 'symbol', 'zlib',
 'json', 'tokenize', 'numpy', 'sleekxmpp', 'cPickle', 'sqlalchemy', 'termios', 'site', 'hashlib', 'miniupnpc',
 'pwd', 'pytz', 'copy', 'cryptography', 'smtplib', 'keyword', 'socketio', 'uu', 'stringprep', 'markupbase',
 'fnmatch', 'getpass', 'mimetools', 'pickle', 'parser', 'ad2web', 'contextlib', 'numbers', 'io', 'pyexpat',
 'shutil', 'serial', 'mako', 'grp', 'alarmdecoder', 'six', 'genericpath', 'OpenSSL', 'gettext', 'sqlite3',
 'mimetypes', 'rfc822', 'pyftdi', 'glob', 'time', 'htmlentitydefs', 'struct', 'sys', 'codeop', 'ssl', 'geventwebsocket',
 'types', 'strop', 'argparse', 'sitecustomize', 'pyasn1', 'difflib', 'urlparse', 'linecache', 'sh', 'netifaces', 'babel', 'gzip', 'hmac' ]
