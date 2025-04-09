# -*- coding: utf-8 -*-

from flask_wtf import FlaskForm as Form
from wtforms import (StringField, SubmitField)
from wtforms.validators import (DataRequired, Length)

#from ..user import User

from ..widgets import ButtonField

class CameraForm(Form):
    name = StringField(u'Name', [DataRequired(), Length(max=32)])
    get_jpg_url = StringField(u'Snapshot URL', [Length(max=255)])
    username = StringField(u'Auth Username', [Length(max=32)])
    password = StringField(u'Auth Password', [Length(max=255)])
    submit = SubmitField(u'Save')
    cancel = ButtonField(u'Cancel', onclick="location.href='/cameras/camera_list'")
