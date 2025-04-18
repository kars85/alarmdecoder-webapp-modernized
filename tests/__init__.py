# tests/__init__.py
# -*- coding: utf-8 -*-
"""
    Unit Tests
    ~~~~~~~~~~

    Define TestCase as base class for unit tests.
    Ref: http://packages.python.org/Flask-Testing/
"""
import os
import inspect
from flask_testing import TestCase as Base, Twill
from flask import url_for

# Core app factory and config
from ad2web.app import create_app
from ad2web.config import TestConfig
from ad2web.extensions import db

# Force model discovery by importing all modules
import ad2web.api.models
import ad2web.cameras.models
import ad2web.certificate.models
import ad2web.common.models
import ad2web.keypad.models
import ad2web.log.models
import ad2web.notifications.models
import ad2web.settings.models
import ad2web.setup.models
import ad2web.updater.models
import ad2web.user.models
import ad2web.zones.models

# User model constants
from ad2web.user import User, UserDetail, ADMIN, USER, ACTIVE
from ad2web.utils import MALE

# tests/__init__.py
class TestCase(Base):
    def create_app(self):
        """
        Create the Flask app instance for testing.
        """
        app, _ = create_app(config=TestConfig)
        return app

    def init_data(self):
        # Seed demo and admin users
        demo = User(
            name=u'demo', email=u'demo@example.com', password=u'123456',
            role_code=USER, status_code=ACTIVE, user_detail=UserDetail())
        admin = User(
            name=u'admin', email=u'admin@example.com', password=u'123456',
            role_code=ADMIN, status_code=ACTIVE, user_detail=UserDetail())
        db.session.add_all([demo, admin])
        db.session.commit()

    def setUp(self):
        os.makedirs(self.app.instance_path, exist_ok=True)
        self._app_context = self.app.app_context()
        self._app_context.push()

        # Drop all existing tables
        db.drop_all()

        # Ensure all models are registered
        import ad2web.api.models
        import ad2web.cameras.models
        import ad2web.certificate.models
        import ad2web.common.models
        import ad2web.keypad.models
        import ad2web.log.models
        import ad2web.notifications.models
        import ad2web.settings.models
        import ad2web.setup.models
        import ad2web.updater.models
        import ad2web.user.models
        import ad2web.zones.models

        # Create fresh schema
        db.create_all()
        self.init_data()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        if hasattr(self, '_app_context'):
            self._app_context.pop()

    def login(self, username, password):
        data = {'email': f'{username}@example.com', 'password': password}
        return self.client.post('/login', data=data, follow_redirects=True)

    def _logout(self):
        response = self.client.get('/logout')
        self.assertRedirects(response, url_for('frontend.index'))

    def _test_get_request(self, endpoint, template=None):
        response = self.client.get(endpoint)
        self.assert200(response)
        if template:
            self.assertTemplateUsed(name=template)
        return response