# -*- coding: utf-8 -*-
from markupsafe import Markup
from flask import Blueprint
from flask_wtf import FlaskForm as Form
from wtforms import (HiddenField, BooleanField, StringField,
        PasswordField, SubmitField)
from wtforms.validators import DataRequired, Length, EqualTo, Email
from wtforms.fields import EmailField
from .forms import BaseUserForm
from ..utils import PASSWORD_LEN_MIN, PASSWORD_LEN_MAX

frontend = Blueprint('frontend', __name__)


class LoginForm(Form):
    next = HiddenField()
    login = StringField(u'Username or email', [DataRequired()])
    password = PasswordField('Password', [DataRequired(), Length(PASSWORD_LEN_MIN, PASSWORD_LEN_MAX)])
    remember = BooleanField('Remember me')
    submit = SubmitField('Sign in')


class SignupForm(BaseUserForm):
    next = HiddenField()
    agree = BooleanField(u'Agree to the ' +
                         Markup('<a target="_blank" rel="noopener noreferrer" href="/terms">Terms of Service</a>'),
                         [DataRequired()])
    submit = SubmitField('Sign up')


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


class CreateProfileForm(BaseUserForm):
    openid = HiddenField()
    submit = SubmitField(u'Create Profile')


class LicenseAgreementForm(Form):
    agree = BooleanField(u'I agree to the license agreement', [DataRequired()], default=False)
    submit = SubmitField(u'Save')
