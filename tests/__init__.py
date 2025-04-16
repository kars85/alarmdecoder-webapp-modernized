# -*- coding: utf-8 -*-
"""
    Unit Tests
    ~~~~~~~~~~

    Define TestCase as base class for unit tests.
    Ref: http://packages.python.org/Flask-Testing/
"""
import inspect  # <--- ADD THIS
from flask_testing import TestCase as Base, Twill
from flask import url_for
import os
from ad2web.app import create_app
# --- ADD THIS PRINT STATEMENT ---
print(f"\n--- tests/__init__.py: Imported create_app from: {inspect.getfile(create_app)} ---\n")
# --- END PRINT --
from ad2web.user import User, UserDetail, ADMIN, USER, ACTIVE
from ad2web.config import TestConfig
from ad2web.extensions import db
from ad2web.utils import MALE
from ad2web.app import create_app

# tests/__init__.py
class TestCase(Base):
    def create_app(self):
        """
        Create the Flask app instance for testing.
        """
        print("\n--- TestCase.create_app: Creating app with TestConfig ---")
        app, _ = create_app(config=TestConfig) # Use the main factory

        # --- DEBUG: Print URL Map *AFTER* create_app ---
        print("--- TestCase.create_app: URL Map Rules AFTER factory call ---")
        try:
             # No need for app_context here, app object exists
             for rule in app.url_map.iter_rules():
                 print(f"  Endpoint: {rule.endpoint}, Rule: {rule.rule}, Methods: {rule.methods}")
        except Exception as e:
            print(f"  Error iterating URL map in create_app: {e}")
        print("--- End URL Map ---")
        # --- END DEBUG ---

        return app

    def init_data(self):
        # Ensure this runs within an app context provided by setUp
        print("--- TestCase.init_data: Adding initial data ---")
        demo = User(
            name=u'demo', email=u'demo@example.com', password=u'123456',
            role_code=USER, status_code=ACTIVE, user_detail=UserDetail())
        admin = User(
            name=u'admin', email=u'admin@example.com', password=u'123456',
            role_code=ADMIN, status_code=ACTIVE, user_detail=UserDetail())
        db.session.add(demo)
        db.session.add(admin)
        try:
            db.session.commit()
            print("--- TestCase.init_data: Initial data committed ---")
        except Exception as e:
            print(f"--- TestCase.init_data: ERROR committing data: {e} ---")
            db.session.rollback()

    def setUp(self):
        """Set up test fixtures before each test."""
        # Ensure the instance folder exists
        # Use self.app which is created by create_app()
        os.makedirs(self.app.instance_path, exist_ok=True)
        print(f"\n--- TestCase.setUp: Using DB URI: {self.app.config['SQLALCHEMY_DATABASE_URI']} ---")

        # Push an app context BEFORE db operations
        self._app_context = self.app.app_context()
        self._app_context.push()

        db.create_all()
        self.init_data()

    def tearDown(self):
        """Clean up after each test."""
        db.session.remove()
        db.drop_all()
        # Pop the app context
        if hasattr(self, '_app_context'):
            self._app_context.pop()

    def login(self, username, password):
        # ... (login method remains the same, using self.assert_200) ...
        data = {
            'email': f'{username}@example.com',
            'password': password,
        }
        print(f"--- Attempting login for {username} ---") # DEBUG
        response = self.client.post('/login', data=data, follow_redirects=True)
        self.assert_200(response)
        print(f"--- Login POST successful (status {response.status_code}) for {username} ---") # DEBUG
        return response

    def _logout(self):
        # ... (logout method remains the same) ...
        response = self.client.get('/logout')
        # Check the target of the redirect
        self.assertRedirects(response, url_for('frontend.index', _external=False))

    def _test_get_request(self, endpoint, template=None):
        # ... (_test_get_request remains the same) ...
        response = self.client.get(endpoint)
        self.assert_200(response)
        if template:
            self.assertTemplateUsed(name=template)
        return response
