# -*- coding: utf-8 -*-
"""
    Unit Tests
    ~~~~~~~~~~

    Define TestCase as base class for unit tests.
    Ref: http://packages.python.org/Flask-Testing/
"""
import inspect  # <--- ADD THIS
from flask_testing import TestCase as Base, Twill

from ad2web.app import create_app
# --- ADD THIS PRINT STATEMENT ---
print(f"\n--- tests/__init__.py: Imported create_app from: {inspect.getfile(create_app)} ---\n")
# --- END PRINT --
from ad2web.user import User, UserDetail, ADMIN, USER, ACTIVE
from ad2web.config import TestConfig
from ad2web.extensions import db
from ad2web.utils import MALE


# tests/__init__.py
class TestCase(Base):
    def create_app(self):
        # ...
        # CHANGE THIS:
        # app, _ = create_app(TestConfig)
        # TO THIS:
        app = create_app(TestConfig)
        return app
    # ...
    def init_data(self):

        demo = User(
                name=u'demo',
                email=u'demo@example.com',
                password=u'123456',
                role_code=USER,
                status_code=ACTIVE,
                user_detail=UserDetail(
                    sex_code=MALE,
                    age=10,
                    url=u'http://demo.example.com',
                    deposit=100.00,
                    location=u'Hangzhou',
                    bio=u'admin Guy is ... hmm ... just a demo guy.'))
        admin = User(
                name=u'admin',
                email=u'admin@example.com',
                password=u'123456',
                role_code=ADMIN,
                status_code=ACTIVE,
                user_detail=UserDetail(
                    sex_code=MALE,
                    age=10,
                    url=u'http://admin.example.com',
                    deposit=100.00,
                    location=u'Hangzhou',
                    bio=u'admin Guy is ... hmm ... just a admin guy.'))
        db.session.add(demo)
        db.session.add(admin)
        db.session.commit()

    def setUp(self):
        """Reset all tables before testing."""

        db.create_all()
        self.init_data()

    def tearDown(self):
        """Clean db session and drop all tables."""

        db.drop_all()

    def login(self, username, password):
        # ... (data setup and post) ...
        response = self.client.post('/login', data=data, follow_redirects=True)
        # --- CHANGE THIS ASSERTION ---
        # From:
        # assert "Hello" in response.data.decode('utf-8')
        # To (Example - check for Logout):
        self.assertIn("Logout", response.data.decode('utf-8'), "Logout link not found after login")
        # Or (Example - check for username):
        # self.assertIn(f"Logged in as {username}", response.data.decode('utf-8')) # Adjust based on actual welcome message
        return response

    def _logout(self):
        response = self.client.get('/logout')
        self.assertRedirects(response, location='/')

    def _test_get_request(self, endpoint, template=None):
        response = self.client.get(endpoint)
        self.assert_200(response)
        if template:
            self.assertTemplateUsed(name=template)
        return response
