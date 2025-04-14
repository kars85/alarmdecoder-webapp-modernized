# -*- coding: utf-8 -*-

from flask_wtf import FlaskForm as Form
from wtforms import (SubmitField, FileField, SelectField)
from wtforms.validators import (DataRequired)

from ..widgets import ButtonField

class UpdateFirmwareForm(Form):
    firmware_file = FileField(u'Firmware File', [DataRequired()])

    submit = SubmitField(u'Upload')
    cancel = ButtonField(u'Cancel', onclick="location.href='/settings'")

class UpdateFirmwareJSONForm(Form):
    firmware_file_json = SelectField(u'Firmware File', coerce=str)

    json_submit = SubmitField(u'Upload')
    cancel = ButtonField(u'Cancel', onclick="location.href='/settings'")
