# -*- coding: utf-8 -*-
"""
    Utils has nothing to do with models and views.
"""

import string
import random
import os
import io
import tarfile
import time

from datetime import datetime, timezone


# Instance folder path, make it independent.
INSTANCE_FOLDER_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'instance'))
LOG_FOLDER = os.path.join(INSTANCE_FOLDER_PATH, 'logs')
ALLOWED_AVATAR_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}


# Form validation

USERNAME_LEN_MIN = 4
USERNAME_LEN_MAX = 25

REALNAME_LEN_MIN = 4
REALNAME_LEN_MAX = 25

PASSWORD_LEN_MIN = 6
PASSWORD_LEN_MAX = 64

AGE_MIN = 1
AGE_MAX = 300

DEPOSIT_MIN = 0.00
DEPOSIT_MAX = 9999999999.99

# Sex type.
MALE = 1
FEMALE = 2
OTHER = 9
SEX_TYPE = {
    MALE: 'Male',
    FEMALE: 'Female',
    OTHER: 'Other',
}

# Model
STRING_LEN = 64


def get_current_time():
    return datetime.now(timezone.utc)


def pretty_date(dt, default=None):
    """
    Returns string representing "time since" e.g.
    3 days ago, 5 hours ago etc.
    Ref: https://bitbucket.org/danjac/newsmeme/src/a281babb9ca3/newsmeme/
    """

    if default is None:
        default = 'just now'

    now = datetime.now(timezone.utc)
    diff = now - dt

    periods = (
        (diff.days // 365, 'year', 'years'),
        (diff.days // 30, 'month', 'months'),
        (diff.days // 7, 'week', 'weeks'),
        (diff.days,  'day', 'days'),
        (diff.seconds // 3600, 'hour', 'hours'),
        (diff.seconds // 60, 'minute', 'minutes'),
        (diff.seconds, 'second', 'seconds'),
    )

    for period, singular, plural in periods:
        if not period:
            continue

        if period == 1:
            return '%d %s ago' % (period, singular)
        else:
            return '%d %s ago' % (period, plural)

    return default


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1] in ALLOWED_AVATAR_EXTENSIONS


def id_generator(size=10, chars=string.ascii_letters + string.digits):
    #return base64.urlsafe_b64encode(os.urandom(size))
    return ''.join(random.choice(chars) for _ in range(size))


def make_dir(dir_path):
    try:
        if not os.path.exists(dir_path):
            os.mkdir(dir_path)
    except Exception as e:
        raise e


def tar_add_directory(tar, name):
    ti = tarfile.TarInfo(name=name)
    ti.mtime = int(time.time())
    ti.type = tarfile.DIRTYPE
    ti.mode = 0o755
    tar.addfile(ti)


def tar_add_textfile(tar, name, data, parent_path=None):
    path = name
    if parent_path:
        path = os.path.join(parent_path, name)

    ti = tarfile.TarInfo(name=path)
    ti.mtime = int(time.time())
    ti.size = len(data)

    if isinstance(data, str):
        data = data.encode('ascii')  # ensure bytes

    tar.addfile(ti, io.BytesIO(data))


def user_is_authenticated(user):
    if user is None:
        return False

    is_auth = getattr(user, "is_authenticated", False)
    return is_auth() if callable(is_auth) else is_auth


def user_is_anonymous(user):
    if user is None:
        return False

    if callable(user.is_anonymous):
        return user.is_anonymous()
    else:
        return user.is_anonymous
