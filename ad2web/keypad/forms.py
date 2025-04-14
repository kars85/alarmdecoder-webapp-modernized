# -*- coding: utf-8 -*-

from flask_wtf import FlaskForm as Form
from wtforms import (StringField, SubmitField, SelectField)
from wtforms.validators import (DataRequired, Length, Optional)

#from ..user import User

from ..widgets import ButtonField
from .constants import FIRE, MEDICAL, POLICE, SPECIAL_4, SPECIAL_CUSTOM, STAY, AWAY, CHIME, RESET, EXIT

from alarmdecoder import AlarmDecoder

class KeypadButtonForm(Form):
    text = StringField(u'Label', [DataRequired(), Length(max=32)])
    code = StringField(u'Code', [DataRequired(), Length(max=32)])

    submit = SubmitField(u'Save')
    cancel = ButtonField(u'Cancel', onclick="location.href='/keypad/button_index'")

class SpecialButtonFormAdemco(Form):
    special_1 = SelectField(u'Special Button 1', choices=[(FIRE, u'Fire'), (POLICE, u'Police'), (MEDICAL, u'Medical'), (SPECIAL_4, u'Panel Default'), (SPECIAL_CUSTOM, u'Custom')], default=FIRE, coerce=int)
    special_1_key = StringField(u'Key Code', [Optional(), Length(max=5)], default="<S1>")

    special_2 = SelectField(u'Special Button 2', choices=[(FIRE, u'Fire'), (POLICE, u'Police'), (MEDICAL, u'Medical'), (SPECIAL_4, u'Panel Default'), (SPECIAL_CUSTOM, u'Custom')], default=POLICE, coerce=int)
    special_2_key = StringField(u'Key Code', [Optional(), Length(max=5)], default="<S2>")

    special_3 = SelectField(u'Special Button 3', choices=[(FIRE, u'Fire'), (POLICE, u'Police'), (MEDICAL, u'Medical'), (SPECIAL_4, u'Panel Default'), (SPECIAL_CUSTOM, u'Custom')], default=MEDICAL, coerce=int)
    special_3_key = StringField(u'Key Code', [Optional(), Length(max=5)], default="<S3>")

    special_4 = SelectField(u'Special Button 4', choices=[(FIRE, u'Fire'), (POLICE, u'Police'), (MEDICAL, u'Medical'), (SPECIAL_4, u'Panel Default'), (SPECIAL_CUSTOM, u'Custom')], default=SPECIAL_4, coerce=int)
    special_4_key = StringField(u'Key Code', [Optional(), Length(max=5)], default="<S4>")

    submit = SubmitField(u'Save')
    cancel = ButtonField(u'Cancel', onclick="location.href='/keypad/button_index'")

class SpecialButtonFormDSC(Form):
    special_1 = SelectField(u'Special Button 1', choices=[(FIRE, u'Fire'), (POLICE, u'Police'), (MEDICAL, u'Medical'), (STAY, u'Stay'), (AWAY, u'Away'), (CHIME, u'Chime'), (RESET, u'Reset'), (EXIT, u'Exit')], default=FIRE, coerce=int)
    special_1_key = StringField(u'Key Code', [Optional(), Length(max=5)], default=AlarmDecoder.KEY_F1)

    special_2 = SelectField(u'Special Button 2', choices=[(FIRE, u'Fire'), (POLICE, u'Police'), (MEDICAL, u'Medical'), (STAY, u'Stay'), (AWAY, u'Away'), (CHIME, u'Chime'), (RESET, u'Reset'), (EXIT, u'Exit')], default=POLICE, coerce=int)
    special_2_key = StringField(u'Key Code', [Optional(), Length(max=5)], default=AlarmDecoder.KEY_F2)

    special_3 = SelectField(u'Special Button 3', choices=[(FIRE, u'Fire'), (POLICE, u'Police'), (MEDICAL, u'Medical'), (STAY, u'Stay'), (AWAY, u'Away'), (CHIME, u'Chime'), (RESET, u'Reset'), (EXIT, u'Exit')], default=MEDICAL, coerce=int)
    special_3_key = StringField(u'Key Code', [Optional(), Length(max=5)], default=AlarmDecoder.KEY_F3)

    special_4 = SelectField(u'Special Button 4', choices=[(FIRE, u'Fire'), (POLICE, u'Police'), (MEDICAL, u'Medical'), (STAY, u'Stay'), (AWAY, u'Away'), (CHIME, u'Chime'), (RESET, u'Reset'), (EXIT, u'Exit')], default=STAY, coerce=int)
    special_4_key = StringField(u'Key Code', [Optional(), Length(max=5)], default=AlarmDecoder.KEY_F4)

    special_5 = SelectField(u'Special Button 5', choices=[(FIRE, u'Fire'), (POLICE, u'Police'), (MEDICAL, u'Medical'), (STAY, u'Stay'), (AWAY, u'Away'), (CHIME, u'Chime'), (RESET, u'Reset'), (EXIT, u'Exit')], default=AWAY, coerce=int)
    special_5_key = StringField(u'Key Code', [Optional(), Length(max=5)], default=chr(5) + chr(5) + chr(5))

    special_6 = SelectField(u'Special Button 6', choices=[(FIRE, u'Fire'), (POLICE, u'Police'), (MEDICAL, u'Medical'), (STAY, u'Stay'), (AWAY, u'Away'), (CHIME, u'Chime'), (RESET, u'Reset'), (EXIT, u'Exit')], default=CHIME, coerce=int)
    special_6_key = StringField(u'Key Code', [Optional(), Length(max=5)], default=chr(6) + chr(6) + chr(6))

    special_7 = SelectField(u'Special Button 7', choices=[(FIRE, u'Fire'), (POLICE, u'Police'), (MEDICAL, u'Medical'), (STAY, u'Stay'), (AWAY, u'Away'), (CHIME, u'Chime'), (RESET, u'Reset'), (EXIT, u'Exit')], default=RESET, coerce=int)
    special_7_key = StringField(u'Key Code', [Optional(), Length(max=5)], default=chr(7) + chr(7) + chr(7))

    special_8 = SelectField(u'Special Button 8', choices=[(FIRE, u'Fire'), (POLICE, u'Police'), (MEDICAL, u'Medical'), (STAY, u'Stay'), (AWAY, u'Away'), (CHIME, u'Chime'), (RESET, u'Reset'), (EXIT, u'Exit')], default=EXIT, coerce=int)
    special_8_key = StringField(u'Key Code', [Optional(), Length(max=5)], default=chr(8) + chr(8) + chr(8))

    submit = SubmitField(u'Save')
    cancel = ButtonField(u'Cancel', onclick="location.href='/keypad/button_index'")
