# -*- coding: utf-8 -*-

from markupsafe import Markup

from flask import Blueprint

frontend = Blueprint('frontend', __name__)

from flask_wtf import FlaskForm as Form
from wtforms import (ValidationError, HiddenField, BooleanField, StringField,
        PasswordField, SubmitField)
from wtforms.validators import DataRequired, Length, EqualTo, Email
from wtforms.fields import EmailField

from ..user import User
from ..utils import (PASSWORD_LEN_MIN, PASSWORD_LEN_MAX,
        USERNAME_LEN_MIN, USERNAME_LEN_MAX)


class LoginForm(Form):
    next = HiddenField()
    login = StringField(u'Username or email', [DataRequired()])
    password = PasswordField('Password', [DataRequired(), Length(PASSWORD_LEN_MIN, PASSWORD_LEN_MAX)])
    remember = BooleanField('Remember me')
    submit = SubmitField('Sign in')


class SignupForm(Form):
    next = HiddenField()
    email = EmailField(u'Email', [DataRequired(), Email()],
            description=u"What's your email address?")
    password = PasswordField(u'Password', [DataRequired(), Length(PASSWORD_LEN_MIN, PASSWORD_LEN_MAX)],
            description=u'%s characters or more! Be tricky.' % PASSWORD_LEN_MIN)
    name = StringField(u'Choose your username', [DataRequired(), Length(USERNAME_LEN_MIN, USERNAME_LEN_MAX)],
            description=u"Don't worry. you can change it later.")
    agree = BooleanField(u'Agree to the ' +
        Markup('<a target="_blank" rel="noopener noreferrer" href="/terms">Terms of Service</a>'), [DataRequired()])
    submit = SubmitField('Sign up')

    def validate_name(self, field):
        if User.query.filter_by(name=field.data).first() is not None:
            raise ValidationError(u'This username is taken')

    def validate_email(self, field):
        if User.query.filter_by(email=field.data).first() is not None:
            raise ValidationError(u'This email is taken')


class RecoverPasswordForm(Form):
    email = EmailField(u'Your email', [Email()])
    submit = SubmitField('Send instructions')


class ChangePasswordForm(Form):
    activation_key = HiddenField()
    password = PasswordField(u'Password', [DataRequired()])
    password_again = PasswordField(u'Password again', [EqualTo('password', message="Passwords don't match")])
    submit = SubmitField('Save')


class ReauthForm(Form):
    next = HiddenField()
    password = PasswordField(u'Password', [DataRequired(), Length(PASSWORD_LEN_MIN, PASSWORD_LEN_MAX)])
    submit = SubmitField('Reauthenticate')


class OpenIDForm(Form):
    openid = StringField(u'Your OpenID', [DataRequired()])
    submit = SubmitField(u'Log in with OpenID')


class CreateProfileForm(Form):
    openid = HiddenField()
    name = StringField(u'Choose your username', [DataRequired(), Length(USERNAME_LEN_MIN, USERNAME_LEN_MAX)],
            description=u"Don't worry. you can change it later.")
    email = EmailField(u'Email', [DataRequired(), Email()], description=u"What's your email address?")
    password = PasswordField(u'Password', [DataRequired(), Length(PASSWORD_LEN_MIN, PASSWORD_LEN_MAX)],
            description=u'%s characters or more! Be tricky.' % PASSWORD_LEN_MIN)
    submit = SubmitField(u'Create Profile')

    def validate_name(self, field):
        if User.query.filter_by(name=field.data).first() is not None:
            raise ValidationError(u'This username is taken.')

    def validate_email(self, field):
        if User.query.filter_by(email=field.data).first() is not None:
            raise ValidationError(u'This email is taken.')

class LicenseAgreementForm(Form):
    agree = BooleanField(u'I agree to the license agreement', [DataRequired()], default=False)

    submit = SubmitField(u'Save')