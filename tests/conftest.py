import pytest
from ad2web.app import create_app
from ad2web.extensions import db


@pytest.fixture
def app():
    # Force test config *before* create_app
    test_config = {
        "TESTING": True,
        "WTF_CSRF_ENABLED": False,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
    }

    app, _ = create_app(config=test_config)

    with app.app_context():
        db.create_all()
        yield app


@pytest.fixture
def client(app):
    return app.test_client()
