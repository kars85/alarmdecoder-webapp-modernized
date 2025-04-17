# -*- coding: utf-8 -*-

from flask_wtf import FlaskForm as Form
from wtforms import StringField, SubmitField, SelectField
from wtforms.validators import DataRequired, Length, Optional

# from ..user import User

from ..widgets import ButtonField
from .constants import (
    FIRE,
    MEDICAL,
    POLICE,
    SPECIAL_4,
    SPECIAL_CUSTOM,
    STAY,
    AWAY,
    CHIME,
    RESET,
    EXIT,
)

from alarmdecoder import AlarmDecoder


class KeypadButtonForm(Form):
    text = StringField("Label", [DataRequired(), Length(max=32)])
    code = StringField("Code", [DataRequired(), Length(max=32)])

    submit = SubmitField("Save")
    cancel = ButtonField("Cancel", onclick="location.href='/keypad/button_index'")


class SpecialButtonFormAdemco(Form):
    special_1 = SelectField(
        "Special Button 1",
        choices=[
            (FIRE, "Fire"),
            (POLICE, "Police"),
            (MEDICAL, "Medical"),
            (SPECIAL_4, "Panel Default"),
            (SPECIAL_CUSTOM, "Custom"),
        ],
        default=FIRE,
        coerce=int,
    )
    special_1_key = StringField("Key Code", [Optional(), Length(max=5)], default="<S1>")

    special_2 = SelectField(
        "Special Button 2",
        choices=[
            (FIRE, "Fire"),
            (POLICE, "Police"),
            (MEDICAL, "Medical"),
            (SPECIAL_4, "Panel Default"),
            (SPECIAL_CUSTOM, "Custom"),
        ],
        default=POLICE,
        coerce=int,
    )
    special_2_key = StringField("Key Code", [Optional(), Length(max=5)], default="<S2>")

    special_3 = SelectField(
        "Special Button 3",
        choices=[
            (FIRE, "Fire"),
            (POLICE, "Police"),
            (MEDICAL, "Medical"),
            (SPECIAL_4, "Panel Default"),
            (SPECIAL_CUSTOM, "Custom"),
        ],
        default=MEDICAL,
        coerce=int,
    )
    special_3_key = StringField("Key Code", [Optional(), Length(max=5)], default="<S3>")

    special_4 = SelectField(
        "Special Button 4",
        choices=[
            (FIRE, "Fire"),
            (POLICE, "Police"),
            (MEDICAL, "Medical"),
            (SPECIAL_4, "Panel Default"),
            (SPECIAL_CUSTOM, "Custom"),
        ],
        default=SPECIAL_4,
        coerce=int,
    )
    special_4_key = StringField("Key Code", [Optional(), Length(max=5)], default="<S4>")

    submit = SubmitField("Save")
    cancel = ButtonField("Cancel", onclick="location.href='/keypad/button_index'")


class SpecialButtonFormDSC(Form):
    special_1 = SelectField(
        "Special Button 1",
        choices=[
            (FIRE, "Fire"),
            (POLICE, "Police"),
            (MEDICAL, "Medical"),
            (STAY, "Stay"),
            (AWAY, "Away"),
            (CHIME, "Chime"),
            (RESET, "Reset"),
            (EXIT, "Exit"),
        ],
        default=FIRE,
        coerce=int,
    )
    special_1_key = StringField(
        "Key Code", [Optional(), Length(max=5)], default=AlarmDecoder.KEY_F1
    )

    special_2 = SelectField(
        "Special Button 2",
        choices=[
            (FIRE, "Fire"),
            (POLICE, "Police"),
            (MEDICAL, "Medical"),
            (STAY, "Stay"),
            (AWAY, "Away"),
            (CHIME, "Chime"),
            (RESET, "Reset"),
            (EXIT, "Exit"),
        ],
        default=POLICE,
        coerce=int,
    )
    special_2_key = StringField(
        "Key Code", [Optional(), Length(max=5)], default=AlarmDecoder.KEY_F2
    )

    special_3 = SelectField(
        "Special Button 3",
        choices=[
            (FIRE, "Fire"),
            (POLICE, "Police"),
            (MEDICAL, "Medical"),
            (STAY, "Stay"),
            (AWAY, "Away"),
            (CHIME, "Chime"),
            (RESET, "Reset"),
            (EXIT, "Exit"),
        ],
        default=MEDICAL,
        coerce=int,
    )
    special_3_key = StringField(
        "Key Code", [Optional(), Length(max=5)], default=AlarmDecoder.KEY_F3
    )

    special_4 = SelectField(
        "Special Button 4",
        choices=[
            (FIRE, "Fire"),
            (POLICE, "Police"),
            (MEDICAL, "Medical"),
            (STAY, "Stay"),
            (AWAY, "Away"),
            (CHIME, "Chime"),
            (RESET, "Reset"),
            (EXIT, "Exit"),
        ],
        default=STAY,
        coerce=int,
    )
    special_4_key = StringField(
        "Key Code", [Optional(), Length(max=5)], default=AlarmDecoder.KEY_F4
    )

    special_5 = SelectField(
        "Special Button 5",
        choices=[
            (FIRE, "Fire"),
            (POLICE, "Police"),
            (MEDICAL, "Medical"),
            (STAY, "Stay"),
            (AWAY, "Away"),
            (CHIME, "Chime"),
            (RESET, "Reset"),
            (EXIT, "Exit"),
        ],
        default=AWAY,
        coerce=int,
    )
    special_5_key = StringField(
        "Key Code", [Optional(), Length(max=5)], default=chr(5) + chr(5) + chr(5)
    )

    special_6 = SelectField(
        "Special Button 6",
        choices=[
            (FIRE, "Fire"),
            (POLICE, "Police"),
            (MEDICAL, "Medical"),
            (STAY, "Stay"),
            (AWAY, "Away"),
            (CHIME, "Chime"),
            (RESET, "Reset"),
            (EXIT, "Exit"),
        ],
        default=CHIME,
        coerce=int,
    )
    special_6_key = StringField(
        "Key Code", [Optional(), Length(max=5)], default=chr(6) + chr(6) + chr(6)
    )

    special_7 = SelectField(
        "Special Button 7",
        choices=[
            (FIRE, "Fire"),
            (POLICE, "Police"),
            (MEDICAL, "Medical"),
            (STAY, "Stay"),
            (AWAY, "Away"),
            (CHIME, "Chime"),
            (RESET, "Reset"),
            (EXIT, "Exit"),
        ],
        default=RESET,
        coerce=int,
    )
    special_7_key = StringField(
        "Key Code", [Optional(), Length(max=5)], default=chr(7) + chr(7) + chr(7)
    )

    special_8 = SelectField(
        "Special Button 8",
        choices=[
            (FIRE, "Fire"),
            (POLICE, "Police"),
            (MEDICAL, "Medical"),
            (STAY, "Stay"),
            (AWAY, "Away"),
            (CHIME, "Chime"),
            (RESET, "Reset"),
            (EXIT, "Exit"),
        ],
        default=EXIT,
        coerce=int,
    )
    special_8_key = StringField(
        "Key Code", [Optional(), Length(max=5)], default=chr(8) + chr(8) + chr(8)
    )

    submit = SubmitField("Save")
    cancel = ButtonField("Cancel", onclick="location.href='/keypad/button_index'")
