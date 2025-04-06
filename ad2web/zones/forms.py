# -*- coding: utf-8 -*-

from flask_wtf import FlaskForm as Form
from wtforms.fields import URLField, EmailField, TelField
from wtforms import (ValidationError, StringField, HiddenField,
        PasswordField, SubmitField, TextAreaField, IntegerField, RadioField,
        FileField, DecimalField, BooleanField, SelectField, FormField, FieldList)
from wtforms.validators import (DataRequired, Length, EqualTo, Email, NumberRange,
        URL, AnyOf, Optional)
from flask_login import current_user

from ..utils import PASSWORD_LEN_MIN, PASSWORD_LEN_MAX, AGE_MIN, AGE_MAX, DEPOSIT_MIN, DEPOSIT_MAX
from ..widgets import ButtonField

class ZoneForm(Form):
    zone_id = IntegerField(u'Zone ID', [DataRequired(), NumberRange(1, 65535)])
    name = StringField(u'Name', [DataRequired(), Length(max=32)])  # Changed to StringField and DataRequired
    description = StringField(u'Description', [Length(max=255)])  # Changed to StringField

    submit = SubmitField(u'Save')
    cancel = ButtonField(u'Cancel', onclick="location.href='/settings/zones'")
