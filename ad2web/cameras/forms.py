# -*- coding: utf-8 -*-

from flask_wtf import FlaskForm as Form
from wtforms.fields import URLField, EmailField, TelField
from wtforms import (ValidationError, StringField, HiddenField,
        PasswordField, SubmitField, TextAreaField, IntegerField, RadioField,
        FileField, DecimalField, BooleanField, SelectField, FormField, FieldList)
from wtforms.validators import (DataRequired, Length, EqualTo, Email, NumberRange,
        URL, AnyOf, Optional)
from flask_login import current_user

#from ..user import User
from ..utils import PASSWORD_LEN_MIN, PASSWORD_LEN_MAX, AGE_MIN, AGE_MAX, DEPOSIT_MIN, DEPOSIT_MAX

from ..widgets import ButtonField

class CameraForm(Form):
    name = StringField(u'Name', [DataRequired(), Length(max=32)])
    get_jpg_url = StringField(u'Snapshot URL', [Length(max=255)])
    username = StringField(u'Auth Username', [Length(max=32)])
    password = StringField(u'Auth Password', [Length(max=255)])
    submit = SubmitField(u'Save')
    cancel = ButtonField(u'Cancel', onclick="location.href='/cameras/camera_list'")
