# -*- coding: utf-8 -*-

from ad2web.user import User, UserDetail

from tests import TestCase
from tests.test_utils import create_test_app


class TestUser(TestCase):

    def create_app(self):
        return create_test_app()

    def test_get_current_time(self):

        assert User.query.count() == 2
        assert UserDetail.query.count() == 2
