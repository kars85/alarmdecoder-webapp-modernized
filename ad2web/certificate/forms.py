# -*- coding: utf-8 -*-

from flask_wtf import FlaskForm as Form
from wtforms import (StringField, HiddenField,
        SubmitField)
from wtforms.validators import (DataRequired, Length)

class GenerateCertificateForm(Form):
    next = HiddenField()
    name = StringField(u'Name', [DataRequired(), Length(max=32)])
    description = StringField(u'Description', [Length(max=255)])

    submit = SubmitField(u'Generate')
