# -*- coding: utf-8 -*-
import pytest
from ad2web.extensions import db
from ad2web.app import create_app
from ad2web.settings.models import Setting

# Force import of all models so db.create_all() picks up every table
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

@pytest.fixture(scope="session")
def app():
    test_config = {
        "TESTING": True,
        "WTF_CSRF_ENABLED": False,
        # shared on‑disk DB so in‑memory tables persist across connections
        "SQLALCHEMY_DATABASE_URI": "sqlite:///test.db",
        "SQLALCHEMY_ENGINE_OPTIONS": {"connect_args": {"check_same_thread": False}},
    }
    app, _ = create_app(config=test_config)

    with app.app_context():
        # start from a clean slate
        db.drop_all()
        db.create_all()

        # seed essential settings
        for name, kwargs in [
            ("setup_complete", {"int_value": 1}),
            ("device_type",    {"string_value": "network"}),
            ("use_ssl",        {"int_value": 0}),
            ("system_email_server", {"string_value": "localhost"}),
        ]:
            if not Setting.query.filter_by(name=name).first():
                s = Setting(name=name)
                for k,v in kwargs.items():
                    setattr(s, k, v)
                db.session.add(s)
        db.session.commit()

    return app

@pytest.fixture
def client(app):
    """Provide a test client for pytest-style tests (test_main.py)."""
    return app.test_client()
