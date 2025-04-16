# -*- coding: utf-8 -*-
#/tests/test_utils.py
from datetime import datetime, timedelta, UTC

from ad2web.utils import pretty_date
from ad2web.app import create_app as _create_app
from tests import TestCase


class TestPrettyDate(TestCase):

    def create_app(self):
        return create_test_app()

    def test_func(self):
        days = [
            [timedelta(days=365 * 3), '3 years ago'],
            [timedelta(days=365), '1 year ago'],
            [timedelta(days=30 * 6), '6 months ago'],
            [timedelta(seconds=(60 * 5) + 40), '5 minutes ago'],
        ]
        now = datetime.now(UTC)  # Make sure it’s naive
        for delta, expected in days:
            ago = now - delta
            assert pretty_date(ago) == expected


def create_test_app():
    app, _ = _create_app()
    app.config.update({
        "TESTING": True,
        "WTF_CSRF_ENABLED": False,
    })
    return app
