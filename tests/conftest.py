# tests/conftest.py

import pytest
from datetime import datetime
from ad2web.app import create_app
from ad2web.extensions import db
from ad2web.settings.models import Setting
from ad2web.user.models import User, UserDetail
from ad2web.certificate.models import Certificate
from ad2web.certificate.constants import CA, SERVER
from ad2web.notifications.models import Notification, NotificationMessage
from ad2web.zones.models import Zone


@pytest.fixture(scope="session")
def app():
    test_config = {
        "TESTING": True,
        "WTF_CSRF_ENABLED": False,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
    }

    app, _ = create_app(config=test_config)

    with app.app_context():
        db.create_all()

        # Seed critical settings
        settings_to_seed = [
            {"name": "setup_complete", "int_value": 1},
            {"name": "device_type", "string_value": "network"},
            {"name": "use_ssl", "int_value": 0},
            {"name": "system_email_server", "string_value": "localhost"},
        ]
        for row in settings_to_seed:
            existing = Setting.query.filter_by(name=row["name"]).first()
            if existing:
                if "int_value" in row:
                    existing.int_value = row["int_value"]
                if "string_value" in row:
                    existing.string_value = row["string_value"]
            else:
                s = Setting(name=row["name"])
                if "int_value" in row:
                    s.int_value = row["int_value"]
                if "string_value" in row:
                    s.string_value = row["string_value"]
                db.session.add(s)

        # Test user
        user = User(
            id=1,
            name="demo",
            email="demo@example.com",
            password="123456",  # raw for now
            role_code=1,
            status_code=1,
            created_time=datetime.utcnow(),
        )
        user.user_detail = UserDetail()
        db.session.add(user)

        # Certificates
        db.session.add(Certificate(type=CA, user=user, name="Root CA", content="--CERT--", key="--KEY--"))
        db.session.add(Certificate(type=SERVER, user=user, name="Server Cert", content="--CERT--", key="--KEY--"))

        # Zones
        zone = Zone(id=1, name="Front Door", enabled=True)
        db.session.add(zone)

        # Notifications
        notification = Notification(id=1, name="Zone Alert", enabled=True, type="email")
        notification.zones.append(zone)  # assuming `zone` was added earlier and `notification.zones` is a relationship
        message = NotificationMessage(notification=notification, content="Zone triggered at {{ timestamp }}")
        db.session.add(notification)
        db.session.add(message)

        db.session.commit()

        yield app


@pytest.fixture
def client(app):
    return app.test_client()
