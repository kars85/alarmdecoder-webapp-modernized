# -*- coding: utf-8 -*-

from flask_wtf import FlaskForm as Form
from wtforms import StringField, SubmitField, IntegerField
from wtforms.validators import DataRequired, Length, NumberRange

from ..widgets import ButtonField


class ZoneForm(Form):
    zone_id = IntegerField("Zone ID", [DataRequired(), NumberRange(1, 65535)])
    name = StringField(
        "Name", [DataRequired(), Length(max=32)]
    )  # Changed to StringField and DataRequired
    description = StringField("Description", [Length(max=255)])  # Changed to StringField

    submit = SubmitField("Save")
    cancel = ButtonField("Cancel", onclick="location.href='/settings/zones'")
