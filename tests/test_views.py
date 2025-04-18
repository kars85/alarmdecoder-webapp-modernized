# -*- coding: utf-8 -*-
#tests/test_views.py

from ad2web.user import User
from ad2web.extensions import db, mail

from tests import TestCase
from tests.test_utils import create_test_app


class TestFrontend(TestCase):

    def create_app(self):
        return create_test_app()

    def test_show(self):
        response = self.client.get('/', follow_redirects=True)  # Correct
        assert response.status_code == 200
        # Also likely needs self. if _test_get_request is a method of TestCase:
        self._test_get_request('/', 'index.html')

    def test_signup(self):
        self._test_get_request('/signup', 'frontend/signup.html')

        data = {
            'email': 'new_user@example.com',
            'password': '123456',
            'password_again': '123456',  # <-- Required by your form
            'name': 'new_user',
            'agree': True,
        }
        response = self.client.post('/signup', data=data, follow_redirects=True)
        assert b'Sign in' in response.data or b'Log in' in response.data
        new_user = User.query.filter_by(name=data['name']).first()
        assert new_user is not None

    def test_login(self):
        self._test_get_request('/login', 'frontend/login.html')

    def test_logout(self):  # Fix indentation
        self