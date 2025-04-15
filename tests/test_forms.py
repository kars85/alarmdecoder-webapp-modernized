# tests/test_forms.py
from werkzeug.datastructures import MultiDict
import pytest
from ad2web.user import User
from ad2web.frontend.forms import SignupForm, CreateProfileForm
from ad2web.extensions import db


@pytest.mark.usefixtures("app")
class TestForms:

    def test_signup_valid(self, app):
        with app.app_context(), app.test_request_context():
            # Create the form data dictionary separately
            form_data = MultiDict({
                "email": "unique@example.com",
                "name": "uniqueuser",
                "password": "123456",
                "agree": True,
            })
            # Pass the dictionary using the 'formdata' keyword argument
            # Explicitly pass obj=None which might help IDE type checkers
            form = SignupForm(obj=None, formdata=form_data)
            assert form.validate() is True

    def test_signup_duplicate_email(self, app):
        with app.app_context(), app.test_request_context():
            user = User(name="existing", email="taken@example.com")
            # Assuming User model handles password hashing internally (e.g., via property setter)
            # If not, use the actual method (e.g., user.set_password("123456"))
            user.password = "123456"
            db.session.add(user)
            db.session.commit()

            # Create the form data dictionary separately
            form_data = MultiDict({
                "email": "taken@example.com",
                "name": "newuser",
                "password": "123456",
                "agree": True,
            })
            # Pass the dictionary using the 'formdata' keyword argument
            # Explicitly pass obj=None
            form = SignupForm(obj=None, formdata=form_data)
            assert form.validate() is False
            assert "This email is taken" in form.email.errors[0]

    def test_signup_duplicate_username(self, app):
        with app.app_context(), app.test_request_context():
            user = User(name="takenuser", email="unique2@example.com")
            # Assuming User model handles password hashing internally
            user.password = "123456"
            db.session.add(user)
            db.session.commit()

            # Create the form data dictionary separately
            form_data = MultiDict({
                "email": "fresh@example.com",
                "name": "takenuser",
                "password": "123456",
                "agree": True,
            })
             # Pass the dictionary using the 'formdata' keyword argument
             # Explicitly pass obj=None
            form = SignupForm(obj=None, formdata=form_data)
            assert form.validate() is False
            assert "This username is taken" in form.name.errors[0]

    def test_create_profile_openid_field(self, app):
        with app.app_context(), app.test_request_context():
            # Create the form data dictionary separately
            form_data = MultiDict({
                "openid": "someopenid",
                "email": "user3@example.com",
                "name": "user3",
                "password": "123456",
            })
            # Pass the dictionary using the 'formdata' keyword argument
            # Explicitly pass obj=None
            form = CreateProfileForm(obj=None, formdata=form_data)
            assert form.validate() is True

# Removed the placeholder set_password_stub as it should be part of the actual User model
# or the tests should rely on the model's real password handling mechanism.