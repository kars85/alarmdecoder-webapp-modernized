# -*- coding: utf-8 -*-

from flask_wtf import FlaskForm as Form
from wtforms.fields import URLField, EmailField, TelField
from wtforms import (ValidationError, StringField, HiddenField,
        PasswordField, SubmitField, TextAreaField, IntegerField, RadioField,
        FileField, DecimalField)
from wtforms.validators import (DataRequired, Length, EqualTo, Email, NumberRange,
        URL, AnyOf, Optional)

class GenerateCertificateForm(Form):
    next = HiddenField()
    name = StringField(u'Name', [DataRequired(), Length(max=32)])
    description = StringField(u'Description', [Length(max=255)])

    submit = SubmitField(u'Generate')
