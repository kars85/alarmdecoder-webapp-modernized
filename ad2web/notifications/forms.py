# -*- coding: utf-8 -*-

import re
import json
from flask_wtf import FlaskForm as Form
from wtforms.fields import URLField, EmailField, TelField
import wtforms
import ast
from wtforms import (ValidationError, StringField, HiddenField,
        PasswordField, SubmitField, TextAreaField, IntegerField, RadioField,
        FileField, DecimalField, BooleanField, SelectField, FormField, FieldList,
        SelectMultipleField)
from wtforms.validators import (DataRequired, Length, EqualTo, Email, NumberRange,
        URL, AnyOf, Optional, DataRequired)
from wtforms.widgets import ListWidget, CheckboxInput
from .constants import (NOTIFICATIONS, NOTIFICATION_TYPES, SUBSCRIPTIONS, DEFAULT_SUBSCRIPTIONS, EMAIL, PUSHOVER, PUSHOVER_PRIORITIES,
                        LOWEST, LOW, NORMAL, HIGH, EMERGENCY, PROWL_PRIORITIES, GROWL, GROWL_PRIORITIES, GROWL_TITLE,
                        URLENCODE, JSON, XML, CUSTOM_METHOD_POST, CUSTOM_METHOD_GET_TYPE, UPNPPUSH)
from .models import NotificationSetting
from ..widgets import ButtonField, MultiCheckboxField


class NotificationButtonForm(wtforms.Form):
    cancel = ButtonField(u'Cancel', onclick="location.href='/settings/notifications'")
    submit = SubmitField(u'Save')
    test = SubmitField(u'Save & Test')


class CreateNotificationForm(Form):
    type = SelectField(u'Notification Type', choices=[nt for t, nt in NOTIFICATIONS.items()])

    submit = SubmitField(u'Next')
    cancel = ButtonField(u'Cancel', onclick="location.href='/settings/notifications'")


class EditNotificationMessageForm(Form):
    id = HiddenField()
    text = TextAreaField(u'Message Text', [DataRequired(), Length(max=255)])

    submit = SubmitField(u'Save')
    cancel = ButtonField(u'Cancel', onclick="location.href='/settings/notifications/messages'")


class NotificationReviewForm(Form):
    buttons = FormField(NotificationButtonForm)


class TimeValidator(object):
    def __init__(self, message=None):
        if not message:
            message = u'Field must be in the 24 hour time format: 00:00:00'

        self.message = message

    def __call__(self, form, field):
        result = re.match("^(\d\d):(\d\d):(\d\d)$", field.data)
        if result is None:
            raise ValidationError(self.message)

        h = int(result.group(1))
        m = int(result.group(2))
        s = int(result.group(3))

        if (h < 0 or h > 23 or
            m < 0 or m > 59 or
            s < 0 or s > 59):
            raise ValidationError(self.message)


class TimeSettingsInternalForm(Form):
    starttime =  StringField(u'Start Time', [DataRequired(), Length(max=8), TimeValidator()], default='00:00:00', description=u'Start time for this event notification (24hr format)')
    endtime =  StringField(u'End Time', [DataRequired(), Length(max=8), TimeValidator()], default='23:59:59', description=u'End time for this event notification (24hr format)')
    delaytime = IntegerField(u'Zone Tracker Notification Delay', [DataRequired(), NumberRange(min=0)], default=0, description=u'Time in minutes to delay sending Zone Tracker notification')
    suppress = BooleanField(u'Suppress Zone Tracker Restore?', [Optional()], description=u'Suppress Zone Tracker notification if restored before delay')

    def __init__(self, *args, **kwargs):
        kwargs['csrf_enabled'] = False
        super(TimeSettingsInternalForm, self).__init__(*args, **kwargs)


class EditNotificationForm(Form):
    type = HiddenField()
    description = StringField(u'Description', [DataRequired(), Length(max=255)], description=u'Brief description of this notification')
    suppress_timestamp = BooleanField(u'Suppress Timestamp?', [Optional()], description=u'Removes Timestamp from Message Body and Subject')
    time_field = FormField(TimeSettingsInternalForm)
    subscriptions = MultiCheckboxField(u'Notification Events', choices=[(str(k), v) for k, v in SUBSCRIPTIONS.items()])

    def populate_settings(self, settings, id=None):
        settings['subscriptions'] = self.populate_setting('subscriptions', json.dumps({str(k): True for k in self.subscriptions.data}))
        settings['starttime'] = self.populate_setting('starttime', self.time_field.starttime.data or '00:00:00')
        settings['endtime'] = self.populate_setting('endtime', self.time_field.endtime.data or '23:59:59')
        settings['delay'] = self.populate_setting('delay', self.time_field.delaytime.data)
        settings['suppress'] = self.populate_setting('suppress', self.time_field.suppress.data)
        settings['suppress_timestamp'] = self.populate_setting('suppress_timestamp', self.suppress_timestamp.data)

    def populate_from_settings(self, id):
        subscriptions = self.populate_from_setting(id, 'subscriptions')
        if subscriptions:
            self.subscriptions.data = [k if v == True else False for k, v in json.loads(subscriptions).items()]

        self.time_field.starttime.data = self.populate_from_setting(id, 'starttime', default='00:00:00')
        self.time_field.endtime.data = self.populate_from_setting(id, 'endtime', default='23:59:59')
        self.time_field.delaytime.data = self.populate_from_setting(id, 'delay', default=0)
        # HACK: workaround for bad form that was pushed up.
        if self.time_field.delaytime.data is None or self.time_field.delaytime.data == '':
            self.time_field.delaytime.data = 0
        self.time_field.suppress.data = self.populate_from_setting(id, 'suppress', default=False)
        self.suppress_timestamp.data = self.populate_from_setting(id, 'suppress_timestamp', default=False)

    def populate_setting(self, name, value, id=None):
        if id is not None:
            setting = NotificationSetting.query.filter_by(notification_id=id, name=name).first()
        else:
            setting = NotificationSetting(name=name)

        setting.value = value

        return setting

    def populate_from_setting(self, id, name, default=None):
        ret = default

        setting = NotificationSetting.query.filter_by(notification_id=id, name=name).first()
        if setting is not None:
            ret = setting.value

        return ret


class EmailNotificationInternalForm(Form):
    source = StringField(u'Source Address (From)', [DataRequired(), Length(max=255)], default='youremail@example.com', description=u'Emails will originate from this address')
    destination = StringField(u'Destination Address (To)', [DataRequired(), Length(max=255)], description=u'Emails will be sent to this address')

    subject = StringField(u'Email Subject', [DataRequired(), Length(max=255)], default='AlarmDecoder: Alarm Event', description=u'Emails will contain this text as the subject')

    server = StringField(u'Email Server (Configured using local server by default, not preferred due to ISP filtering)', [DataRequired(), Length(max=255)], default='localhost')
    port = IntegerField(u'Server Port (If using your own server, check that port is not filtered by ISP)', [DataRequired(), NumberRange(1, 65535)], default=25)
    tls = BooleanField(u'Use TLS? (Do not pick SSL if using TLS)', default=False)
    ssl = BooleanField(u'Use SSL? (Do not pick TLS if using SSL)', default=False)
    authentication_required = BooleanField(u'Authenticate with email server?', default=False)
    username = StringField(u'Username', [Optional(), Length(max=255)])
    password = PasswordField(u'Password', [Optional(), Length(max=255)])

    def __init__(self, *args, **kwargs):
        kwargs['csrf_enabled'] = False
        super(EmailNotificationInternalForm, self).__init__(*args, **kwargs)


class EmailNotificationForm(EditNotificationForm):
    legend = (
        "<div style=\"font-size: 16px;\">"
        "</div>"
    )
    form_field = FormField(EmailNotificationInternalForm)

    submit = SubmitField(u'Next')
    cancel = ButtonField(u'Cancel', onclick="location.href='/settings/notifications'")

    def populate_settings(self, settings, id=None):
        EditNotificationForm.populate_settings(self, settings, id)

        settings['source'] = self.populate_setting('source', self.form_field.source.data)
        settings['destination'] = self.populate_setting('destination', self.form_field.destination.data)
        settings['subject'] = self.populate_setting('subject', self.form_field.subject.data)
        settings['server'] = self.populate_setting('server', self.form_field.server.data)
        settings['port'] = self.populate_setting('port', self.form_field.port.data)
        settings['tls'] = self.populate_setting('tls', self.form_field.tls.data)
        settings['ssl'] = self.populate_setting('ssl', self.form_field.ssl.data)
        settings['authentication_required'] = self.populate_setting('authentication_required', self.form_field.authentication_required.data)
        settings['username'] = self.populate_setting('username', self.form_field.username.data)
        settings['password'] = self.populate_setting('password', self.form_field.password.data)

    def populate_from_settings(self, id):
        EditNotificationForm.populate_from_settings(self, id)

        self.form_field.source.data = self.populate_from_setting(id, 'source')
        self.form_field.destination.data = self.populate_from_setting(id, 'destination')
        self.form_field.subject.data = self.populate_from_setting(id, 'subject')
        self.form_field.server.data = self.populate_from_setting(id, 'server')
        self.form_field.tls.data = self.populate_from_setting(id, 'tls')
        self.form_field.ssl.data = self.populate_from_setting(id, 'ssl')
        self.form_field.port.data = self.populate_from_setting(id, 'port')
        self.form_field.authentication_required.data = self.populate_from_setting(id, 'authentication_required')
        self.form_field.username.data = self.populate_from_setting(id, 'username')
        self.form_field.password.widget.hide_value = False
        self.form_field.password.data = self.populate_from_setting(id, 'password')


class PushoverNotificationInternalForm(Form):
    token = StringField(u'API Token', [DataRequired(), Length(max=30)], description=u'Your Application\'s API Token')
    user_key = StringField(u'User/Group Key', [DataRequired(), Length(max=30)], description=u'Your user or group key')
    priority = SelectField(u'Message Priority', choices=[PUSHOVER_PRIORITIES[LOWEST], PUSHOVER_PRIORITIES[LOW], PUSHOVER_PRIORITIES[NORMAL], PUSHOVER_PRIORITIES[HIGH], PUSHOVER_PRIORITIES[EMERGENCY]], default=PUSHOVER_PRIORITIES[LOW], description='Pushover message priority', coerce=int)
    title = StringField(u'Title of Message', [Length(max=255)], description=u'Title of Notification Messages')

    def __init__(self, *args, **kwargs):
        kwargs['csrf_enabled'] = False
        super(PushoverNotificationInternalForm, self).__init__(*args, **kwargs)


class PushoverNotificationForm(EditNotificationForm):
    legend = (
        "<div style=\"font-size: 16px;\">"
        "</div>"
    )
    form_field = FormField(PushoverNotificationInternalForm)

    submit = SubmitField(u'Next')
    cancel = ButtonField(u'Cancel', onclick="location.href='/settings/notifications'")

    def populate_settings(self, settings, id=None):
        EditNotificationForm.populate_settings(self, settings, id)
        settings['token'] = self.populate_setting('token', self.form_field.token.data)
        settings['user_key'] = self.populate_setting('user_key', self.form_field.user_key.data)
        settings['priority'] = self.populate_setting('priority', self.form_field.priority.data)
        settings['title'] = self.populate_setting('title', self.form_field.title.data)

    def populate_from_settings(self, id):
        EditNotificationForm.populate_from_settings(self, id)
        self.form_field.token.data = self.populate_from_setting(id, 'token')
        self.form_field.user_key.data = self.populate_from_setting(id, 'user_key')
        self.form_field.priority.data = self.populate_from_setting(id, 'priority')
        self.form_field.title.data = self.populate_from_setting(id, 'title')


class TwilioNotificationInternalForm(Form):
    account_sid = StringField(u'Account SID', [DataRequired(), Length(max=50)], description=u'Your Twilio Account SID')
    auth_token = StringField(u'Auth Token', [DataRequired(), Length(max=50)], description=u'Your Twilio User Auth Token')
    number_to = StringField(u'To', [DataRequired(), Length(max=15)], description=u'Number to send SMS/call to')
    number_from = StringField(u'From', [DataRequired(), Length(max=15)], description=u'Must Be A Valid Twilio Phone Number')

    def __init__(self, *args, **kwargs):
        kwargs['csrf_enabled'] = False
        super(TwilioNotificationInternalForm, self).__init__(*args, **kwargs)


class TwilioNotificationForm(EditNotificationForm):
    legend = (
        "<div style=\"font-size: 16px;\">"
        "</div>"
    )
    form_field = FormField(TwilioNotificationInternalForm)

    submit = SubmitField(u'Next')
    cancel = ButtonField(u'Cancel', onclick="location.href='/settings/notifications'")

    def populate_settings(self, settings, id=None):
        EditNotificationForm.populate_settings(self, settings, id)
        settings['account_sid'] = self.populate_setting('account_sid', self.form_field.account_sid.data)
        settings['auth_token'] = self.populate_setting('auth_token', self.form_field.auth_token.data)
        settings['number_to'] = self.populate_setting('number_to', self.form_field.number_to.data)
        settings['number_from'] = self.populate_setting('number_from', self.form_field.number_from.data)

    def populate_from_settings(self, id):
        EditNotificationForm.populate_from_settings(self, id)
        self.form_field.account_sid.data = self.populate_from_setting(id, 'account_sid')
        self.form_field.auth_token.data = self.populate_from_setting(id, 'auth_token')
        self.form_field.number_to.data = self.populate_from_setting(id, 'number_to')
        self.form_field.number_from.data = self.populate_from_setting(id, 'number_from')


class TwiMLNotificationInternalForm(Form):
    account_sid = StringField(u'Account SID', [DataRequired(), Length(max=50)], description=u'Your Twilio Account SID')
    auth_token = StringField(u'Auth Token', [DataRequired(), Length(max=50)], description=u'Your Twilio User Auth Token')
    number_to = StringField(u'To', [DataRequired(), Length(max=15)], description=u'Number to send SMS/call to')
    number_from = StringField(u'From', [DataRequired(), Length(max=15)], description=u'Must Be A Valid Twilio Phone Number')
    twimlet_url = StringField(u'Twimlet URL', [DataRequired()], default="http://twimlets.com/message", description=u'Your twimlet URL (http://twimlets.com/message)')

    def __init__(self, *args, **kwargs):
        kwargs['csrf_enabled'] = False
        super(TwiMLNotificationInternalForm, self).__init__(*args, **kwargs)

class TwiMLNotificationForm(EditNotificationForm):
    legend = (
        "<div style=\"font-size: 16px;\">"
        "</div>"
    )
    form_field = FormField(TwiMLNotificationInternalForm)

    submit = SubmitField(u'Next')
    cancel = ButtonField(u'Cancel', onclick="location.href='/settings/notifications'")

    def populate_settings(self, settings, id=None):
        EditNotificationForm.populate_settings(self, settings, id)
        settings['account_sid'] = self.populate_setting('account_sid', self.form_field.account_sid.data)
        settings['auth_token'] = self.populate_setting('auth_token', self.form_field.auth_token.data)
        settings['number_to'] = self.populate_setting('number_to', self.form_field.number_to.data)
        settings['number_from'] = self.populate_setting('number_from', self.form_field.number_from.data)
        settings['twimlet_url'] = self.populate_setting('twimlet_url', self.form_field.twimlet_url.data)

    def populate_from_settings(self, id):
        EditNotificationForm.populate_from_settings(self, id)
        self.form_field.account_sid.data = self.populate_from_setting(id, 'account_sid')
        self.form_field.auth_token.data = self.populate_from_setting(id, 'auth_token')
        self.form_field.number_to.data = self.populate_from_setting(id, 'number_to')
        self.form_field.number_from.data = self.populate_from_setting(id, 'number_from')
        self.form_field.twimlet_url.data = self.populate_from_setting(id, 'twimlet_url')

class ProwlNotificationInternalForm(Form):
    prowl_api_key = StringField(u'API Key', [DataRequired(), Length(max=50)], description=u'Your Prowl API Key')
    prowl_app_name = StringField(u'Application Name', [DataRequired(), Length(max=256)], description=u'Application Name to Show in Notifications', default='AlarmDecoder')
    prowl_priority = SelectField(u'Message Priority', choices=[PROWL_PRIORITIES[LOWEST], PROWL_PRIORITIES[LOW], PROWL_PRIORITIES[NORMAL], PROWL_PRIORITIES[HIGH], PROWL_PRIORITIES[EMERGENCY]], default=PROWL_PRIORITIES[LOW], description='Prowl message priority', coerce=int)

    def __init__(self, *args, **kwargs):
        kwargs['csrf_enabled'] = False
        super(ProwlNotificationInternalForm, self).__init__(*args, **kwargs)


class ProwlNotificationForm(EditNotificationForm):
    legend = (
        "<div style=\"font-size: 16px;\">"
        "</div>"
    )
    form_field = FormField(ProwlNotificationInternalForm)

    submit = SubmitField(u'Next')
    cancel = ButtonField(u'Cancel', onclick="location.href='/settings/notifications'")

    def populate_settings(self, settings, id=None):
        EditNotificationForm.populate_settings(self, settings, id)

        settings['prowl_api_key'] = self.populate_setting('prowl_api_key', self.form_field.prowl_api_key.data)
        settings['prowl_app_name'] = self.populate_setting('prowl_app_name', self.form_field.prowl_app_name.data)
        settings['prowl_priority'] = self.populate_setting('prowl_priority', self.form_field.prowl_priority.data)

    def populate_from_settings(self, id):
        EditNotificationForm.populate_from_settings(self, id)

        self.form_field.prowl_api_key.data = self.populate_from_setting(id, 'prowl_api_key')
        self.form_field.prowl_app_name.data = self.populate_from_setting(id, 'prowl_app_name')
        self.form_field.prowl_priority.data = self.populate_from_setting(id, 'prowl_priority')


class GrowlNotificationInternalForm(Form):
    growl_hostname = StringField(u'Hostname', [DataRequired(), Length(max=255)], description=u'Growl server to send notification to')
    growl_port = StringField(u'Port', [DataRequired(), Length(max=10)], description=u'Growl server port', default=23053)
    growl_password = PasswordField(u'Password', description=u'The password for the growl server')
    growl_title = StringField(u'Title', [DataRequired(), Length(max=255)], description=u'Notification Title', default=GROWL_TITLE)
    growl_priority = SelectField(u'Message Priority', choices=[GROWL_PRIORITIES[LOWEST], GROWL_PRIORITIES[LOW], GROWL_PRIORITIES[NORMAL], GROWL_PRIORITIES[HIGH], GROWL_PRIORITIES[EMERGENCY]], default=GROWL_PRIORITIES[LOW], description='Growl message priority', coerce=int)

    def __init__(self, *args, **kwargs):
        kwargs['csrf_enabled'] = False
        super(GrowlNotificationInternalForm, self).__init__(*args, **kwargs)


class GrowlNotificationForm(EditNotificationForm):
    legend = (
        "<div style=\"font-size: 16px;\">"
        "</div>"
    )
    form_field = FormField(GrowlNotificationInternalForm)

    submit = SubmitField(u'Next')
    cancel = ButtonField(u'Cancel', onclick="location.href='/settings/notifications'")

    def populate_settings(self, settings, id=None):
        EditNotificationForm.populate_settings(self, settings, id)

        settings['growl_hostname'] = self.populate_setting('growl_hostname', self.form_field.growl_hostname.data)
        settings['growl_port'] = self.populate_setting('growl_port', self.form_field.growl_port.data)
        settings['growl_password'] = self.populate_setting('growl_password', self.form_field.growl_password.data)
        settings['growl_title'] = self.populate_setting('growl_title', self.form_field.growl_title.data)
        settings['growl_priority'] = self.populate_setting('growl_priority', self.form_field.growl_title.data)

    def populate_from_settings(self, id):
        EditNotificationForm.populate_from_settings(self, id)

        self.form_field.growl_hostname.data = self.populate_from_setting(id, 'growl_hostname')
        self.form_field.growl_port.data = self.populate_from_setting(id, 'growl_port')
        self.form_field.growl_password.data = self.populate_from_setting(id, 'growl_password')
        self.form_field.growl_title.data = self.populate_from_setting(id, 'growl_title')
        self.form_field.growl_priority.data = self.populate_from_setting(id, 'growl_priority')


class CustomValueForm(Form):
    custom_key = StringField(label=None)
    custom_value = StringField(label=None)

    def __init__(self, *args, **kwargs):
        kwargs['csrf_enabled'] = False
        super(CustomValueForm, self).__init__(*args, **kwargs)


class CustomPostInternalForm(Form):
    custom_url = StringField(u'URL', [DataRequired(), Length(max=255)], description=u'URL to send data to (ex: www.alarmdecoder.com)')
    custom_path = StringField(u'Path', [DataRequired(), Length(max=400)], description=u'Path to send variables to (ex: /publicapi/add)')
    is_ssl = BooleanField(u'SSL?', default=False, description=u'Is the URL SSL or No?')
    method = RadioField(u'Method', choices=[(CUSTOM_METHOD_POST, 'POST'), (CUSTOM_METHOD_GET_TYPE, 'GET')], default=CUSTOM_METHOD_POST, coerce=int)
    post_type = RadioField(u'Type', choices=[(URLENCODE, 'urlencoded'), (JSON, 'JSON'), (XML, 'XML')], default=URLENCODE, coerce=int)
    require_auth = BooleanField(u'Basic Auth?', default=False, description=u'Does the URL require basic authentication?')
    auth_username = StringField(u'Username', [Optional(), Length(max=255)], description=u'Username for Basic Authentication')
    auth_password = PasswordField(u'Password', [Optional(), Length(max=255)], description=u'Password for Basic Authentication')

    custom_values = FieldList(FormField(CustomValueForm), validators=[Optional()], label=None)
    add_field = ButtonField(u'Add Field', onclick='addField();')

    def __init__(self, *args, **kwargs):
        kwargs['csrf_enabled'] = False
        super(CustomPostInternalForm, self).__init__(*args, **kwargs)


class CustomPostForm(EditNotificationForm):
    legend = (
        "<div style=\"font-size: 16px;\">"
        "</div>"
    )
    form_field = FormField(CustomPostInternalForm)

    submit = SubmitField(u'Next')
    cancel = ButtonField(u'Cancel', onclick="location.href='/settings/notifications'")

    def populate_settings(self, settings, id=None):
        EditNotificationForm.populate_settings(self, settings, id)

        settings['custom_url'] = self.populate_setting('custom_url', self.form_field.custom_url.data)
        settings['custom_path'] = self.populate_setting('custom_path', self.form_field.custom_path.data)
        settings['is_ssl'] = self.populate_setting('is_ssl', self.form_field.is_ssl.data)
        settings['method'] = self.populate_setting('method', self.form_field.method.data)
        settings['post_type'] = self.populate_setting('post_type', self.form_field.post_type.data)
        settings['require_auth'] = self.populate_setting('require_auth', self.form_field.require_auth.data)
        settings['auth_username'] = self.populate_setting('auth_username', self.form_field.auth_username.data)
        settings['auth_password'] = self.populate_setting('auth_password', self.form_field.auth_password.data)
        settings['custom_values'] = self.populate_setting('custom_values', self.form_field.custom_values.data)

    def populate_from_settings(self, id):
        EditNotificationForm.populate_from_settings(self, id)

        self.form_field.custom_url.data = self.populate_from_setting(id, 'custom_url')
        self.form_field.custom_path.data = self.populate_from_setting(id, 'custom_path')
        self.form_field.is_ssl.data = self.populate_from_setting(id, 'is_ssl')
        self.form_field.method.data = self.populate_from_setting(id, 'method')
        self.form_field.post_type.data = self.populate_from_setting(id, 'post_type')
        self.form_field.require_auth.data = self.populate_from_setting(id, 'require_auth')
        self.form_field.auth_username.data = self.populate_from_setting(id, 'auth_username')
        self.form_field.auth_password.data = self.populate_from_setting(id, 'auth_password')
        custom = self.populate_from_setting(id, 'custom_values')

        if custom is not None:
            custom = ast.literal_eval(custom)
            custom = dict((str(i['custom_key']), i['custom_value']) for i in custom)

            for key, value in custom.items():
                CVForm = CustomValueForm()
                CVForm.custom_key = key
                CVForm.custom_value = value

                self.form_field.custom_values.append_entry(CVForm)


class ZoneFilterForm(Form):
    zones = SelectMultipleField(choices=[], coerce=str)
    submit = SubmitField(u'Next')
    cancel = ButtonField(u'Cancel', onclick="location.href='/settings/notifications'")

    def populate_settings(self, settings, id=None):
        settings['zone_filter'] = self.populate_setting('zone_filter', json.dumps(self.zones.data))

    def populate_from_settings(self, id):
        zone_filters = self.populate_from_setting(id, 'zone_filter')
        if zone_filters:
            self.zones.data = [str(k) for k in json.loads(zone_filters)]

    def populate_setting(self, name, value, id=None):
        if id is not None:
            setting = NotificationSetting.query.filter_by(notification_id=id, name=name).first()
        else:
            setting = NotificationSetting(name=name)

        setting.value = value

        return setting

    def populate_from_setting(self, id, name, default=None):
        ret = default

        setting = NotificationSetting.query.filter_by(notification_id=id, name=name).first()
        if setting is not None:
            ret = setting.value

        return ret


class MatrixNotificationInternalForm(Form):
    domain = StringField(u'Domain', [DataRequired(), Length(max=255)], description=u'Domain or IP of matrix server ex. matrix.org')
    room_id = StringField(u'Room ID', [DataRequired(), Length(max=300)], description=u'Room ID and domain ex. !DPNBnAVwxPMvNKTvvY:matrix.org')
    token = StringField(u'Token', [DataRequired(), Length(max=300)], description=u'The long device authentication token. ex. D0gMQowMDI.....')
    custom_values = FieldList(FormField(CustomValueForm), validators=[Optional()], label=None)
    add_field = ButtonField(u'Add Field', onclick='addField();')

    def __init__(self, *args, **kwargs):
        kwargs['csrf_enabled'] = False
        super(MatrixNotificationInternalForm, self).__init__(*args, **kwargs)


class MatrixNotificationForm(Form):
    legend = (
        "<div style=\"font-size: 16px;\">"
        "Matrix.org is a free open source distributed network that supports end-to-end encryption.<br/>"
        "TODO: Add ability to generate the <b>Room ID</b> and <b>Token</b> using a User ID and Pass<br/>"
        "Notes: Create an account and a room on Riot.im that allows posts. You can get the room key from the Riot.im web client.<br/>"
        "See: <a href=\"https://gist.github.com/RickCogley/69f430d4418ae5498e8febab44d241c9\" target=\"_blank\">https://gist.github.com/RickCogley/69f430d4418ae5498e8febab44d241c9</a> for curl commands to generate a <b>Token</b>.<br/>"
        "See: <a href=\"https://matrix.org/\" target=\"_blank\">https://matrix.org</a> for more info on [Matrix]<br/>"
        "See: <a href=\"https://riot.im/\" target=\"_blank\">https://riot.im</a> for an open source client for web and phone to create, manage and use [Matrix] and create rooms.<br/>"
        "</div>"
    )

    type = HiddenField()

    description = StringField(u'Description', [DataRequired(), Length(max=255)], description=u'Brief description of this notification')
    time_field = FormField(TimeSettingsInternalForm)
    subscriptions = MultiCheckboxField(u'Notification Events', choices=[(str(k), v) for k, v in SUBSCRIPTIONS.items()])
    form_field = FormField(MatrixNotificationInternalForm)

    submit = SubmitField(u'Next')
    cancel = ButtonField(u'Cancel', onclick="location.href='/settings/notifications'")

    def populate_settings(self, settings, id=None):
        settings['subscriptions'] = self.populate_setting('subscriptions', json.dumps({str(k): True for k in self.subscriptions.data}))

        settings['starttime'] = self.populate_setting('starttime', self.time_field.starttime.data or '00:00:00')
        settings['endtime'] = self.populate_setting('endtime', self.time_field.endtime.data or '23:59:59')
        settings['delay'] = self.populate_setting('delay', self.time_field.delaytime.data)
        settings['suppress'] = self.populate_setting('suppress', self.time_field.suppress.data)

        settings['domain'] = self.populate_setting('domain', self.form_field.domain.data)
        settings['room_id'] = self.populate_setting('room_id', self.form_field.room_id.data)
        settings['token'] = self.populate_setting('token', self.form_field.token.data)
        settings['custom_values'] = self.populate_setting('custom_values', self.form_field.custom_values.data)

    def populate_from_settings(self, id):
        subscriptions = self.populate_from_setting(id, 'subscriptions')
        if subscriptions:
            self.subscriptions.data = [k if v == True else False for k, v in json.loads(subscriptions).items()]

        self.form_field.domain.data = self.populate_from_setting(id, 'domain')
        self.form_field.room_id.data = self.populate_from_setting(id, 'room_id')
        self.form_field.token.data = self.populate_from_setting(id, 'token')
        custom = self.populate_from_setting(id, 'custom_values')

        if custom is not None:
            custom = ast.literal_eval(custom)
            custom = dict((str(i['custom_key']), i['custom_value']) for i in custom)

            for key, value in custom.items():
                CVForm = CustomValueForm()
                CVForm.custom_key = key
                CVForm.custom_value = value

                self.form_field.custom_values.append_entry(CVForm)

    def populate_setting(self, name, value, id=None):
        if id is not None:
            setting = NotificationSetting.query.filter_by(notification_id=id, name=name).first()
        else:
            setting = NotificationSetting(name=name)

        setting.value = value

        return setting

    def populate_from_setting(self, id, name, default=None):
        ret = default

        setting = NotificationSetting.query.filter_by(notification_id=id, name=name).first()
        if setting is not None:
            ret = setting.value

        return ret

class UPNPPushNotificationInternalForm(Form):
    token = StringField(u'Token', [Length(max=255)], description=u'Currently not used leave blank')

    def __init__(self, *args, **kwargs):
        kwargs['csrf_enabled'] = False
        super(UPNPPushNotificationInternalForm, self).__init__(*args, **kwargs)


class UPNPPushNotificationForm(Form):
    legend = (
        "<div style=\"font-size: 16px;\">"
        "UPNP Push subscriptions.<br/>"
        "Enable UPNP Push subscriptions from clients on the local network using UPNP subscribe method.<br/>"
        "See: <a href=\"https://github.com/nutechsoftware/alarmdecoder-smartthings\" target=\"_blank\">https://github.com/nutechsoftware/alarmdecoder-smartthings</a><br/>"
        "<strong><font color=\"red\">Warning!</font></strong> Only enable one UPNP notification."
        "</div>"
    )

    type = HiddenField()
    subscriptions = HiddenField()
    description = StringField(u'Description', [DataRequired(), Length(max=255)], description=u'Brief description of this notification')
    form_field = FormField(UPNPPushNotificationInternalForm)

    submit = SubmitField(u'Next')
    cancel = ButtonField(u'Cancel', onclick="location.href='/settings/notifications'")

    def populate_settings(self, settings, id=None):
        settings['token'] = self.populate_setting('token', self.form_field.token.data)

    def populate_from_settings(self, id):
        self.form_field.token.data = self.populate_from_setting(id, 'token')

    def populate_setting(self, name, value, id=None):
        if id is not None:
            setting = NotificationSetting.query.filter_by(notification_id=id, name=name).first()
        else:
            setting = NotificationSetting(name=name)

        setting.value = value

        return setting

    def populate_from_setting(self, id, name, default=None):
        ret = default

        setting = NotificationSetting.query.filter_by(notification_id=id, name=name).first()
        if setting is not None:
            ret = setting.value

        return ret

class ReviewNotificationForm(Form):
    buttons = FormField(NotificationButtonForm)
