# -*- coding: utf-8 -*-

from flask import current_app
import time
import datetime
import smtplib
import threading
from email.mime.text import MIMEText
from email.utils import formatdate
from urllib.parse import urlparse

import json
import re
import ssl
import sys
import base64
import uuid
import traceback
import functools
from alarmdecoder.panels import ADEMCO, DSC
from alarmdecoder.zonetracking import Zone as ADZone

try:
    from concurrent.futures import ThreadPoolExecutor
    from concurrent.futures import as_completed
    have_threadpoolexecutor = True
except ImportError:
    have_threadpoolexecutor = False

try:
    from chump import Application
    have_chump = True
except ImportError:
    have_chump = False

try:
    import twilio

    # Old API ~5.6.0
    try:
        from twilio.rest import TwilioRestClient
        from twilio.TwilioRestException import TwilioRestException
        have_twilio = True
    except ImportError:
        # New API 6.0+
        try:
            from twilio.rest import Client as TwilioRestClient
            from twilio.base.exceptions import TwilioRestException
            have_twilio = True
        except ImportError:
            have_twilio = False

except ImportError:
    have_twilio = False

from xml.etree.ElementTree import Element
from xml.etree.ElementTree import SubElement
from xml.etree.ElementTree import Comment
from xml.etree.ElementTree import tostring
import ast

#https connection support - used for prowl, Matrix, custom post notifiation, etc.
try:
    from http.client import HTTPSConnection
except ImportError:
    from httplib import HTTPSConnection


#normal http connection support (future POST to custom url)
try:
    from http.client import HTTPConnection
except ImportError:
    from httplib import HTTPConnection

try:
    from urllib.parse import urlencode, quote
except ImportError:
    from urllib import urlencode, quote

try:
    import gntp.notifier
    have_gntp = True
except ImportError:
    have_gntp = False

from .constants import (EMAIL, DEFAULT_EVENT_MESSAGES, PUSHOVER, TWILIO, PROWL, PROWL_URL, PROWL_PATH, PROWL_EVENT, PROWL_METHOD,
                        PROWL_CONTENT_TYPE, PROWL_HEADER_CONTENT_TYPE, PROWL_USER_AGENT, GROWL_APP_NAME, GROWL_DEFAULT_NOTIFICATIONS,
                        GROWL, CUSTOM, URLENCODE, JSON, XML, CUSTOM_CONTENT_TYPES, CUSTOM_USER_AGENT, CUSTOM_METHOD,
                        ZONE_FAULT, ZONE_RESTORE, BYPASS, CUSTOM_METHOD_GET, CUSTOM_METHOD_POST, CUSTOM_METHOD_GET_TYPE,
                        CUSTOM_TIMESTAMP, CUSTOM_MESSAGE, CUSTOM_REPLACER_SEARCH, TWIML, ARM, DISARM, ALARM, PANIC, FIRE, MATRIX,
                        UPNPPUSH, LRR, READY, CHIME, TIME_MULTIPLIER, XML_EVENT_TEMPLATE, XML_EVENT_PROPERTY, EVENT_TYPES,
                        RAW_MESSAGE, EVENTID_MESSAGE, EVENTDESC_MESSAGE, POWER_CHANGED, BOOT, LOW_BATTERY, RFX, EXP, AUI)

from .models import Notification, NotificationMessage
from ..extensions import db
from ..log.models import EventLogEntry
from ..zones import Zone
from ..utils import user_is_authenticated
from .util import check_time_restriction
from ..settings import Setting

'''
Decorator for better logging of notification task exceptions.
'''
def raise_with_stack(func):

    @functools.wraps(func)
    def wrapped(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            tb = traceback.format_exc(e).splitlines()
            # Grab error and line number
            raise StandardError("%s %s" % (repr(e), tb[3].split(",")[1].strip()))

    return wrapped

'''
 Decorator for adding functions to a green thread pooling. This is more
 efficient for tasks that have a large amount of IO wait time such as
 sending an email.

 You can access local self values but avoid looking at any alarm states
 inside of the AD as they will changed since the time the thread was created.

 To use for example in SomeNotification.send() create a sub function that
 receives this Decorator. Then inside of send() gather the current alarm state
 and then pass it to the sub function _send() that has this Decorator.
'''
def threaded(func):
    def wrapper(*args, **kwargs):
        fcname = "%s.%s()" % (args[0].__class__.__name__, func.__name__)

        # If we have it use it.
        if have_threadpoolexecutor:
            notifier = current_app.decoder._notifier_system

            # pass in current app as var. Better way?
            myapp = current_app._get_current_object()
            future = notifier._tpool.submit(func, *args, app=myapp, **kwargs)
            future.fcname = fcname

            with notifier._lock:
                notifier._futures.append(future)

            myapp.logger.info('Background notification function {0} starting.'.format(future.fcname))

        else:
            # No threading so block and run it synchronously.
            return func(*args, **kwargs)

        return
    return wrapper


class NotificationSystem(object):
    def __init__(self):
        self._notifiers = {}
        self._messages = DEFAULT_EVENT_MESSAGES
        self._wait_list = []
        self._tpool = None
        self._lock = threading.Lock()
        self._futures = []
        self._init_notifiers()

        '''
        subscribers to UPNPPushNotification
        '''
        self._subscribers = {}

        '''
        if we have ThreadPoolExecutor and workers > 0 then init ThreadPoolExecutor
        '''
        if have_threadpoolexecutor:
            current_app.logger.info('Library concurrent.futures.ThreadPoolExecutor found and loaded.')
            # enabled by default with 5 threads.
            workers = Setting.get_by_name('max_notification_workers',default=5).value
            if workers:
                current_app.logger.info('ThreadPoolExecutor enabled for notifications with max_workders {0}.'.format(workers))
                self._tpool = ThreadPoolExecutor(max_workers=workers)
            else:
                current_app.logger.info('ThreadPoolExecutor for notifications disabled.')
        else:
            current_app.logger.info('Library concurrent.futures.ThreadPoolExecutor not found. Use "sudo apt-get install python-concurrent.futures" to enable Threaded notifications.')

    def send(self, type, **kwargs):
        errors = []

        for id, n in self._notifiers.iteritems():
            if n and n.subscribes_to(type, **kwargs):
                try:
                    message, rawmessage = self._build_message(type, **kwargs)

                    if message:
                        if n.delay > 0 and type in (ZONE_FAULT, ZONE_RESTORE, BYPASS):
                            message_send_time = time.mktime((datetime.datetime.combine(datetime.date.today(), datetime.datetime.time(datetime.datetime.now())) + datetime.timedelta(minutes=delay)).timetuple())

                            notify = {}
                            notify['notification'] = n
                            notify['message_send_time'] = message_send_time
                            notify['message'] = message
                            notify['raw'] = rawmessage
                            notify['type'] = type
                            notify['zone'] = int(kwargs.get('zone', -1))

                            if notify not in self._wait_list:
                                self._wait_list.append(notify)
                        else:
                            n.send(type, message, rawmessage)

                except Exception as err:
                    errors.append('Exception in notification {0}.send(): {1}'.format(n.__class__.__name__,str(err)))

        return errors

    def refresh_notifier(self, id):
        n = Notification.query.filter_by(id=id,enabled=1).first()
        if n:
            self._notifiers[id] = TYPE_MAP[n.type](n)
        else:
            try:
                del self._notifiers[id]
            except KeyError:
                pass

    def test_notifier(self, id):
        try:
            n = self._notifiers.get(id)
            if n:
                n.send(None, 'Test Notification', None)

        except Exception as err:
            return str(err)
        else:
            return None

    def add_subscriber(self, host, callback, timeout):
        """
        Add subscriber callback to our dictionary

        ---- example subscriber request headers ----
        SUBSCRIBE /api/v1/alarmdecoder/event?apikey=FOOBARKEY HTTP/1.1
        Accept: */*
        User-Agent: Linux UPnP/1.0 SmartThings
        HOST: XXX.XXX.XXX.XXX:5000
        CALLBACK: <http://XXX.XXX.XXX.XXX:39500/notify>
        NT: upnp:event
        TIMEOUT: Second-28800
        """

        sub_uuid = None

        try:
            # if we find the host:callback in _subscribers then
            # updated it and return the same subscription ID back.
            for k, v in self._subscribers.items():
                if v['host'] == host and v['callback'] == callback:
                    sub_uuid = k
                    break

            # did we find an existing sid? if not make a new one.
            if sub_uuid is None:
                sub_uuid = str(uuid.uuid1())

            # set the expireation time
            tmultiplier, tval = timeout.split("-", 1)
            tlength = TIME_MULTIPLIER.get(tmultiplier,1) * int(tval)
            self._subscribers.update({sub_uuid: {'host':host, 'callback':callback, 'timeout':time.time()+tlength}})

            current_app.logger.info('add_subscriber: {0}'.format(sub_uuid))

        except Exception as err:
            current_app.logger.error('Error adding subscriber for host:{0} callback:{1} timeout:{2} err: {3}'.format(host, callback, timeout, str(err)))

        return sub_uuid

    def remove_subscriber(self, host, subuuid):
        """
        find the subscriber and remove it.

        Remove subscriber if found our our dictionary
        """
        found = self._subscribers.pop(subuudi, None)
        if found:
            current_app.logger.info('remove_subscriber: found {0}'.format(subuuid))
        else:
            current_app.logger.info('remove_subscriber: not found {0}'.format(subuuid))

    def get_subscribers(self):
        return self._subscribers

    def _init_notifiers(self):
        self._notifiers = {-1: LogNotification()}   # Force LogNotification to always be present

        for n in Notification.query.filter_by(enabled=1).all():
            self._notifiers[n.id] = TYPE_MAP[n.type](n)

    def _build_message(self, type, **kwargs):
        message = NotificationMessage.query.filter_by(id=type).first()
        if message:
            message = message.text

        kwargs = self._fill_replacers(type, **kwargs)

        if message:
            message = message.format(**kwargs)

        rawmessage = kwargs.get('message', None)
        if rawmessage:
            rawmessage = getattr(rawmessage,'raw', None)

        return message, rawmessage

    def _fill_replacers(self, type, **kwargs):
        if 'zone' in kwargs:
            zone_name = Zone.get_name(kwargs['zone'])
            kwargs['zone_name'] = zone_name if zone_name else '<unnamed>'

        if type == ARM:
            status = kwargs.get('stay', False)
            kwargs['arm_type'] = 'STAY' if status else 'AWAY'

        if type == LRR:
            message = kwargs.get('message', None)

            # If it has a dict method then the backend API is newer
            if hasattr(message, "dict"):
                message = message.dict()
                vp = message.get('partition', -1)
                ved = message.get('event_description', 'Unknown')
                vs = 'Event' if message.get('event_status', 1) == 1 else 'Restore'
                vedt = message.get('event_data_type', -1)
                vd = message.get('event_data', -1)
                kwargs['status'] = "Partition {0} {1} {2} {3}{4}".format(vp, ved, vs, vedt, vd)
            else:
                kwargs['status'] = message

        if type == AUI:
            message = kwargs.get('message', None)
            if hasattr(message, "dict"):
                message = message.dict()
                kwargs['value'] = message.get('value')

        if type == EXP:
            message = kwargs.get('message', None)
            if hasattr(message, "dict"):
                expmessage = message.dict()
                kwargs['type'] = "ZONE" if message.type == 0 else "RELAY"
                kwargs['address'] = expmessage.get('address')
                kwargs['channel'] = expmessage.get('channel')
                kwargs['value'] = expmessage.get('value')

        if type == RFX:
            message = kwargs.get('message', None)
            if hasattr(message, "dict"):
                rfxmessage = message.dict()
                kwargs['sn'] = rfxmessage.get('serial_number')
                kwargs['bat'] = int(rfxmessage.get('battery'))
                kwargs['supv'] = int(rfxmessage.get('supervision'))
                kwargs['loop0'] = int(message.loop[0]) # Not added to dict? Ok
                kwargs['loop1'] = int(message.loop[1])
                kwargs['loop2'] = int(message.loop[2])
                kwargs['loop3'] = int(message.loop[3])

        return kwargs

    def process_wait_list(self):
        errors = []

        for notifier in self._wait_list:
            try:
                if notifier['notification'].suppress > 0 and self._check_suppress(notifier):
                    self._remove_suppressed_zone(notifier['zone'])

            except Exception as err:
                errors.append('Error sending notification for {0}: {1}'.format(notifier['notification'].description, str(err)))

        for notifier in self._wait_list:
            try:
                if time.time() >= notifier['message_send_time']:
                    notifier['notification'].send(notifier['type'], notifier['message'], notifier['raw'])
                    self._wait_list.remove(notifier)

            except Exception as err:
                errors.append('Error sending notification for {0}: {1}'.format(notifier['notification'].description, str(err)))

        return errors

    def _check_suppress(self, notifier):
        if notifier['type'] in (ZONE_RESTORE, BYPASS):
            zone = notifier['zone']

            #check the first notifier that is a zone fault, get its id, see if there was a zone restore or bypass
            #for the same zone.   If we're suppressed on the notifier, then we won't send it out.
            for n in self._wait_list:
                if n['zone'] == zone:
                    if n['type'] == ZONE_FAULT and n['notification'].suppress == 1:
                        return True

        #right now only suppress zone spam
        return False

    def _remove_suppressed_zone(self, id):
        to_remove = []

        for n in self._wait_list:
            if n['zone'] != -1 and n['zone'] == id:
                to_remove.append(n)

        for n in to_remove:
            self._wait_list.remove(n)


class NotificationThread(threading.Thread):
    def __init__(self, decoder):
        threading.Thread.__init__(self)

        self._decoder = decoder
        self._running = False

    def stop(self):
        self._running = False

    def run(self):
        self._running = True

        notifier = self._decoder._notifier_system
        while self._running:
            # This could be moved down to reduce lock time.
            # Easy button for now is keep it at the top level of this code.
            with notifier._lock:
                ncount = len(notifier._futures)
                if ncount > 0:
                    with self._decoder.app.app_context():
                        current_app.logger.info('Background notification functions running {0}.'.format(ncount))

                    remove = []
                    data = ""
                    for i in range(ncount):
                        f = notifier._futures[i]
                        if f.done():
                            extra_msg = ""
                            try:
                                date = f.result()
                            except Exception as exc:
                                extra_msg = exc
                            else:
                                extra_msg = 'no exceptions'

                            with self._decoder.app.app_context():
                                current_app.logger.info('Background notification function {0} finished with {1}.'.format(f.fcname, extra_msg))

                            remove.append(f)

                    for f in remove:
                        notifier._futures.remove(f)

            with self._decoder.app.app_context():
                errors = self._decoder._notifier_system.process_wait_list()
                for e in errors:
                    current_app.logger.error(e)

            time.sleep(5)


class BaseNotification(object):
    def __init__(self, obj):
        if 'subscriptions' in obj.settings.keys():
            self._subscriptions = {int(k): v for k, v in json.loads(obj.settings['subscriptions'].value).iteritems()}
        else:
            self._subscriptions = {}

        if 'zone_filter' in obj.settings.keys():
            self._zone_filters = [int(k) for k in json.loads(obj.settings['zone_filter'].value)]
        else:
            self._zone_filters = []

        self.id = obj.id
        self.description = obj.description

        self.starttime = obj.get_setting('starttime', default='00:00:00')
        self.endtime = obj.get_setting('endtime', default='23:59:59')
        self.delay = obj.get_setting('delay', default=0)
        # HACK: fix for bad form that was pushed.
        if self.delay is None or self.delay == '':
            self.delay = 0
        self.suppress = obj.get_setting('suppress', default=True)

    def subscribes_to(self, type, **kwargs):
        if type in self._subscriptions.keys():
            if type in (ZONE_FAULT, ZONE_RESTORE, BYPASS):
                zone = kwargs.get('zone', -1)
                if int(zone if zone else -1) in self._zone_filters:
                    return True
                else:
                    return False

            return True

        return False


class LogNotification(object):
    def __init__(self):
        self.id = -1
        self.description = 'Logger'
        self.delay = 0
        self.suppress = 0

    def subscribes_to(self, type, **kwargs):
        return True

    def send(self, type, text, raw):
        with current_app.app_context():
            if type == ZONE_RESTORE or type == ZONE_FAULT or type == BYPASS:
                current_app.logger.debug('Event: {0}'.format(text))
            else:
                current_app.logger.info('Event: {0}'.format(text))

        db.session.add(EventLogEntry(type=type, message=text))
        db.session.commit()

class UPNPPushNotification(BaseNotification):
    def __init__(self, obj):
        BaseNotification.__init__(self, obj)

        self.notification_description = obj.description
        # FIXME Make this user configurable.
        #
        self._events = [LRR, RFX, EXP, AUI, READY, CHIME, ARM, DISARM, ALARM, PANIC, FIRE, BYPASS, ZONE_FAULT, ZONE_RESTORE, BOOT, POWER_CHANGED, LOW_BATTERY]
        self.description = 'UPNPPush'
        self.api_token = obj.get_setting('token')
        self.api_endpoint = obj.get_setting('url')

    def subscribes_to(self, type, **kwargs):
        return (type in self._events)

    @raise_with_stack
    def send(self, type, text, raw):
        if type is None or type in self._events:
            self._notify_subscribers(type, text, raw)

    def _notify_subscribers(self, type, text, raw):
        panelState = self._build_panel_state()

        # if we find the host:callback in _subscribers then
        # updated it and return the same subscription ID back.
        subscribers = current_app.decoder._notifier_system.get_subscribers()

        response =  XML_EVENT_TEMPLATE.format(
            self._build_property("eventid", type, False),
            self._build_property("eventdesc", (EVENT_TYPES[type] if type is not None else "Testing"), False),
            self._build_property("eventmessage", text, True),
            self._build_property("rawmessage", raw, True),
            panelState
        )
        for k, v in subscribers.items():
            self._send_notify_event(k, v['callback'], response)

    def _build_panel_state(self):
        mode = current_app.decoder.device.mode
        if mode == ADEMCO:
            mode = 'ADEMCO'
        elif mode == DSC:
            mode = 'DSC'
        else:
            mode = 'UNKNOWN'

        relay_status = Element("panel_relay_status")
        for (address, channel), value in current_app.decoder.device._relay_status.items():
            child = Element("r") # keep it small
            SubElement(child,"a").text = str(address)
            SubElement(child,"c").text = str(channel)
            SubElement(child,"v").text = str(value)
            relay_status.append(child)

        faulted_zones = Element("panel_zones_faulted")
        for zid, z in current_app.decoder.device._zonetracker.zones.iteritems():
            if z.status != ADZone.CLEAR:
                child = Element("z") # keep it small
                child.text = str(z.zone)
                faulted_zones.append(child)

        ret = {
            'panel_type': mode,
            'panel_powered': current_app.decoder.device._power_status,
            'panel_ready': getattr(current_app.decoder.device, "_ready_status", True),
            'panel_alarming': current_app.decoder.device._alarm_status,
            'panel_bypassed': None in current_app.decoder.device._bypass_status,
            'panel_armed': current_app.decoder.device._armed_status,
            'panel_armed_stay': getattr(current_app.decoder.device, "_armed_stay", False),
            'panel_fire_detected': current_app.decoder.device._fire_status,
            'panel_battery_trouble': current_app.decoder.device._battery_status[0],
            'panel_panicked': current_app.decoder.device._panic_status,
            'panel_chime': getattr(current_app.decoder.device, "_chime_status", False),
            'panel_perimeter_only': getattr(current_app.decoder.device, "_perimeter_only_status", False),
            'panel_entry_delay_off': getattr(current_app.decoder.device, "_entry_delay_off_status", False),
            'panel_exit': getattr(current_app.decoder.device, "_exit", False)
        }

        # convert to XML
        el = Element("panelstate")
        for key, val in ret.items():
            child = Element(key)
            child.text = str(val)
            el.append(child)

        # add faulted zones
        el.append(relay_status)

        # add faulted zones
        el.append(faulted_zones)

        # HACK: do not allow parsing of last_message_received as XML it is cdata
        cdel = Element("last_message_received")
        cdel.append(Comment(' --><![CDATA[' + (current_app.decoder.last_message_received or "") + ']]><!-- '))
        el.append(cdel)
        # wrap in a property tag
        ep = Element("e:property")
        ep.append(el)

        return tostring(ep)

    # Warning: Threaded so it may be sent later and state may change.
    # Never access any AD2* state vars in a threaded function.
    @threaded
    @raise_with_stack
    def _send_notify_event(self, uuid, notify_url, notify_message, app=None):
        """
        Send out notify event to subscriber and return a response.
        """

        # If threaded app will be valid if not it will be None.
        # We need app to send logs and access static values only.
        if app is None:
            app = current_app

        # Remove <> that surround the real unicode url if they exist...
        notify_url = notify_url.translate({ord(k): u"" for k in "<>"})
        parsed_url = urlparse(notify_url)

        headers = {
            'HOST': parsed_url.netloc,
            'Content-Type': 'text/xml',
            'SID': 'uuid:' + uuid,
            'Content-Length': len(notify_message),
            'NT': 'upnp:event',
            'NTS': 'upnp:propchange'
        }

        http_handler = HTTPConnection(parsed_url.netloc)

        http_handler.request('NOTIFY', parsed_url.path, notify_message, headers)
        http_response = http_handler.getresponse()

        app.logger.info('{0}_send_notify_event: status:{1} reason:{2} headers:{3}'.format(self.description, http_response.status, http_response.reason, headers))

        if http_response.status != 200:
            error_msg = '{0} Notification failed: ({1}: {2})'.format(self.description, http_response.status, http_response.read())

            app.logger.warning(error_msg)
            raise Exception(error_msg)

    def _build_property(self, name, value, cdatatag):
        xmleventrawmessage = ""
        if value != None:
            if cdatatag:
                value = "<![CDATA[" + value + "]]>"
            xmleventrawmessage = XML_EVENT_PROPERTY.format(name, value)
        return xmleventrawmessage

class MatrixNotification(BaseNotification):
    def __init__(self, obj):
        BaseNotification.__init__(self, obj)

        self.notification_description = obj.description
        self._events = [LRR, EXP, AUI, READY, CHIME, ARM, DISARM, ALARM, PANIC, FIRE, BYPASS, ZONE_FAULT, ZONE_RESTORE, BOOT, ]

        self.api_endpoint = obj.get_setting('domain')
        self.api_token = obj.get_setting('token')
        self.api_room_id = obj.get_setting('room_id')
        self.custom_values = obj.get_setting('custom_values')

        self.headers = {
            'User-Agent': CUSTOM_USER_AGENT,
            'Content-type': CUSTOM_CONTENT_TYPES[JSON]
        }

    def send(self, type, text, raw):

        try:
            result = False

            if check_time_restriction(self.starttime, self.endtime):
                message = NotificationMessage.query.filter_by(id=type).first()
                if message:
                    message = message.text

                notify_data = {
                    'msgtype': 'm.text',
                    'body': "From %s: %s" % (self.notification_description, text),
                    'notifier': self.notification_description,
                    'eventid': type,
                    'eventdesc': (EVENT_TYPES[type] if type is not None else "Testing"),
                    'raw': raw
                }

                if self.custom_values is not None:
                    if self.custom_values:
                        try:
                            self.custom_values = ast.literal_eval(self.custom_values)
                        except ValueError:
                            pass

                        notify_data.update(dict((str(i['custom_key']), i['custom_value']) for i in self.custom_values))


                #replace placeholder values with actual values
                for key,val in notify_data.items():
                    if val == CUSTOM_REPLACER_SEARCH[CUSTOM_TIMESTAMP]:
                        notify_data[key] = time.strftime("%Y-%m-%d %H:%M:%S %Z", time.localtime(time.time())) # ex: 2016-12-02 10:33:19 PST
                    if val == CUSTOM_REPLACER_SEARCH[CUSTOM_MESSAGE]:
                        notify_data[key] = text
                    if val == CUSTOM_REPLACER_SEARCH[RAW_MESSAGE]:
                        notify_data[key] = raw or ""
                    if val == CUSTOM_REPLACER_SEARCH[EVENTID_MESSAGE]:
                        notify_data[key] = type
                    if val == CUSTOM_REPLACER_SEARCH[EVENTDESC_MESSAGE]:
                        notify_data[key] = EVENT_TYPES[type]

                result = self._do_post(self._dict_to_json(notify_data) )

        except Exception as e:
            raise Exception('Matrix Notification Failed: {0} line: {1}' . format(e,sys.exc_info()[-1].tb_lineno))

        return result

    # Warning: Threaded so it may be sent later and state may change.
    # Never access any AD2* state vars in a threaded function.
    @threaded
    @raise_with_stack
    def _do_post(self, data, app=None):

        # If threaded app will be valid if not it will be None.
        # We need app to send logs and access static values only.
        if app is None:
            app = current_app

        parsed_url = urlparse("https://" + self.api_endpoint + "/_matrix/client/r0/rooms/" + self.api_room_id + "/send/m.room.message?access_token=" + self.api_token)

        if sys.version_info >= (2,7,9):
            http_handler = HTTPSConnection(parsed_url.netloc, context=ssl._create_unverified_context())
        else:
            http_handler = HTTPSConnection(parsed_url.netloc)

        http_handler.request(CUSTOM_METHOD, parsed_url.path+"?"+parsed_url.query, headers=self.headers, body=data)
        http_response = http_handler.getresponse()

        if http_response.status == 200:
            return True
        else:
            raise Exception('response fail (' + str(http_response.status) + ") " + http_response.reason)

    def _dict_to_json(self, d):
        return json.dumps(d)


class EmailNotification(BaseNotification):
    def __init__(self, obj):
        BaseNotification.__init__(self, obj)

        self.notification_description = obj.description
        self.source = obj.get_setting('source')
        self.destination = obj.get_setting('destination')
        self.subject = obj.get_setting('subject')
        self.server = obj.get_setting('server')
        self.port = obj.get_setting('port', default=25)
        self.tls = obj.get_setting('tls', default=False)
        self.ssl = obj.get_setting('ssl', default=False)
        self.authentication_required = obj.get_setting('authentication_required', default=False)
        self.username = obj.get_setting('username')
        self.password = obj.get_setting('password')
        self.suppress_timestamp = obj.get_setting('suppress_timestamp',default=False)

    def send(self, type, text, raw):
        if check_time_restriction(self.starttime, self.endtime):
            msg = MIMEText(text)

            if self.suppress_timestamp == False:
                message_timestamp = time.ctime(time.time())
                msg['Subject'] = self.subject + " (" + message_timestamp + ")"
            else:
                msg['Subject'] = self.subject

            msg['From'] = self.source
            recipients = re.split(r'\s*;\s*|\s*,\s*', self.destination)
            msg['To'] = ', '.join(recipients)
            msg['Date'] = formatdate(localtime=True)

            # Call function with static values and push into thread if possible.
            self._send(recipients, msg)

    # Warning: Threaded so it may be sent later and state may change.
    # Never access any AD2* state vars in a threaded function.
    @threaded
    @raise_with_stack
    def _send(self, recipients, msg, app=None):
        s = None
        if self.ssl:
            s = smtplib.SMTP_SSL(self.server, self.port)
        else:
            s = smtplib.SMTP(self.server, self.port)

        if self.tls and not self.ssl:
            s.starttls()

        if self.authentication_required:
            s.login(str(self.username), str(self.password))

        s.sendmail(self.source, recipients, msg.as_string())
        s.quit()


class PushoverNotification(BaseNotification):
    def __init__(self, obj):
        BaseNotification.__init__(self, obj)

        self.notification_description = obj.description
        self.token = obj.get_setting('token')
        self.user_key = obj.get_setting('user_key')
        self.priority = obj.get_setting('priority')
        self.title = obj.get_setting('title')

    def send(self, type, text, raw):
        if not have_chump:
            raise Exception('Missing Pushover library: chump - install using pip')

        if check_time_restriction(self.starttime, self.endtime):
            app = Application(self.token)
            if app.is_authenticated:
                user = app.get_user(self.user_key)

                if user_is_authenticated(user):
                    message = user.create_message(
                        title=self.title,
                        message=text,
                        html=True,
                        priority=self.priority,
                        timestamp=int(time.time())
                    )

                    is_sent = message.send()

                    if is_sent != True:
                        current_app.logger.info("Pushover Notification Failed")
                        raise Exception('Pushover Notification Failed')
                else:
                    current_app.logger.info("Pushover Notification Failed - bad user key: " + self.user_key)
                    raise Exception("Pushover Notification Failed - bad user key: " + self.user_key)

            else:
                current_app.logger.info("Pushover Notification Failed - bad application token: " + self.token)
                raise Exception("Pushover Notification Failed - bad application token: " + self.token)


class TwilioNotification(BaseNotification):
    def __init__(self, obj):
        BaseNotification.__init__(self, obj)

        self.notification_description = obj.description
        self.account_sid = obj.get_setting('account_sid')
        self.auth_token = obj.get_setting('auth_token')
        self.number_to = obj.get_setting('number_to')
        self.number_from = obj.get_setting('number_from')
        self.suppress_timestamp = obj.get_setting('suppress_timestamp', default=False)

    @raise_with_stack
    def send(self, type, text, raw):
        if have_twilio == False:
            raise Exception('Missing Twilio library: twilio - install using pip')

        text = " From " + self.notification_description + ". " + text

        if check_time_restriction(self.starttime, self.endtime):
            if self.suppress_timestamp == False:
                message_timestamp = time.ctime(time.time())
                msg_to_send = text + " Message Sent at: " + message_timestamp
            else:
                msg_to_send = text

            # Call function with static values and push into thread if possible.
            self._send(msg_to_send)

    # Warning: Threaded so it may be sent later and state may change.
    # Never access any AD2* state vars in a threaded function.
    @threaded
    @raise_with_stack
    def _send(self, twbody, app=None):

        # If threaded app will be valid if not it will be None.
        # We need app to send logs and access static values only.
        if app is None:
            app = current_app

        try:
            client = TwilioRestClient(self.account_sid, self.auth_token)
            message = client.messages.create(
                to=self.number_to,
                from_=self.number_from,
                body=twbody
                )
        except TwilioRestException as e:
            app.logger.info('Event Twilio Notification Failed: {0}' . format(e))
            raise Exception('Twilio Notification Failed: {0}' . format(e))


class TwiMLNotification(BaseNotification):
    def __init__(self, obj):
        BaseNotification.__init__(self, obj)

        self.notification_description = obj.description
        self.account_sid = obj.get_setting('account_sid')
        self.auth_token = obj.get_setting('auth_token')
        self.number_to = obj.get_setting('number_to')
        self.number_from = obj.get_setting('number_from')
        self.url = obj.get_setting('twimlet_url')
        self.suppress_timestamp = obj.get_setting('suppress_timestamp', default=False)

    @raise_with_stack
    def send(self, type, text, raw):
        text = " From " + self.notification_description + ". " + text
        if check_time_restriction(self.starttime, self.endtime):
            if self.suppress_timestamp == False:
                message_timestamp = time.ctime(time.time())
                self.msg_to_send = text + " Message Sent at: " + message_timestamp + "."
            else:
                self.msg_to_send = text

            if have_twilio == False:
                raise Exception('Missing Twilio library: twilio - install using pip')

            # Call function with static values and push into thread if possible.
            url = self.url + "?" + quote("Message[0]") + "=" + quote(self.msg_to_send)
            self._send(url)

    # Warning: Threaded so it may be sent later and state may change.
    # Never access any AD2* state vars in a threaded function.
    @threaded
    @raise_with_stack
    def _send(self, twurl, app=None):
        # If threaded app will be valid if not it will be None.
        # We need app to send logs and access static values only.
        if app is None:
            app = current_app

        try:
            client = TwilioRestClient(self.account_sid, self.auth_token)
            call = client.calls.create(
                to="+" + self.number_to,
                from_="+" + self.number_from,
                url=twurl
                )
        except TwilioRestException as e:
            app.logger.info('Event TWwiML Notification Failed: {0}' . format(e))
            raise Exception('TWwiML Notification Failed: {0}' . format(e))


class ProwlNotification(BaseNotification):
    def __init__(self, obj):
        BaseNotification.__init__(self, obj)

        self.notification_description = obj.description
        self.api_key = obj.get_setting('prowl_api_key')
        self.app_name = obj.get_setting('prowl_app_name')[:256].encode('utf8')
        self.priority = obj.get_setting('prowl_priority')
        self.event = PROWL_EVENT[:1024].encode('utf8')
        self.content_type = PROWL_CONTENT_TYPE
        self.headers = {
            'User-Agent': PROWL_USER_AGENT,
            'Content-type': PROWL_HEADER_CONTENT_TYPE
        }
        self.suppress_timestamp = obj.get_setting('suppress_timestamp', default=False)

    def send(self, type, text, raw):
        if check_time_restriction(self.starttime, self.endtime):
            if self.suppress_timestamp == False:
                message_timestamp = time.ctime(time.time())
                self.msg_to_send = text[:10000].encode('utf8') + " Message Sent at: " + message_timestamp
            else:
                self.msg_to_send = text[:10000].encode('utf8')

            notify_data = {
                'apikey': self.api_key,
                'application': self.app_name,
                'event': self.event,
                'description': self.msg_to_send,
                'priority': self.priority
            }

            self.msg_to_send = text + " From " + self.notification_description + "."

            if sys.version_info >= (2,7,9):
                http_handler = HTTPSConnection(PROWL_URL, context=ssl._create_unverified_context())
            else:
                http_handler = HTTPSConnection(PROWL_URL)

            http_handler.request(PROWL_METHOD, PROWL_PATH, headers=self.headers,body=urlencode(notify_data))

            http_response = http_handler.getresponse()

            if http_response.status == 200:
                return True
            else:
                current_app.logger.info('Event Prowl Notification Failed: {0}'. format(http_response.reason))
                raise Exception('Prowl Notification Failed: {0}' . format(http_response.reason))


class GrowlNotification(BaseNotification):
    def __init__(self, obj):
        BaseNotification.__init__(self, obj)

        self.notification_description = obj.description
        self.priority = obj.get_setting('growl_priority')
        self.hostname = obj.get_setting('growl_hostname')
        self.port = obj.get_setting('growl_port')
        self.password = obj.get_setting('growl_password')

        if self.password == '':
            self.password = None

        self.title = obj.get_setting('growl_title')

        if have_gntp:
            self.growl = gntp.notifier.GrowlNotifier(
                applicationName = GROWL_APP_NAME,
                notifications = GROWL_DEFAULT_NOTIFICATIONS,
                defaultNotifications = GROWL_DEFAULT_NOTIFICATIONS,
                hostname = self.hostname,
                password = self.password
            )
        else:
            self.growl = None

        self.suppress_timestamp = obj.get_setting('suppress_timestamp', default=False)

    def send(self, type, text, raw):
        if not have_gntp:
            raise Exception('Missing Growl library: gntp - install using pip')

        if check_time_restriction(self.starttime, self.endtime):
            if self.suppress_timestamp == False:
                message_timestamp = time.ctime(time.time())
                self.msg_to_send = text + " Message Sent at: " + message_timestamp
            else:
                self.msg_to_send = text

            growl_status = self.growl.register()
            if growl_status == True:
                growl_notify_status = self.growl.notify(
                    noteType = GROWL_DEFAULT_NOTIFICATIONS[0],
                    title = self.title,
                    description = self.msg_to_send,
                    priority = self.priority,
                    sticky = False
                )
                if growl_notify_status != True:
                    current_app.logger.info('Event Growl Notification Failed: {0}' . format(growl_notify_status))
                    raise Exception('Growl Notification Failed: {0}' . format(growl_notify_status))

            else:
                current_app.logger.info('Event Growl Notification Failed: {0}' . format(growl_status))
                raise Exception('Growl Notification Failed: {0}' . format(growl_status))


class CustomNotification(BaseNotification):
    def __init__(self, obj):
        BaseNotification.__init__(self, obj)

        self.notification_description = obj.description
        self.url = obj.get_setting('custom_url')
        self.path = obj.get_setting('custom_path')
        self.is_ssl = obj.get_setting('is_ssl')
        self.post_type = obj.get_setting('post_type')
        self.require_auth = obj.get_setting('require_auth')
        self.auth_username = obj.get_setting('auth_username', default='')
        self.auth_password = obj.get_setting('auth_password', default='')
        self.auth_username = self.auth_username.replace('\n', '')
        self.auth_password = self.auth_password.replace('\n', '')
        self.custom_values = obj.get_setting('custom_values')
        self.content_type = CUSTOM_CONTENT_TYPES[self.post_type]
        self.method = obj.get_setting('method')

        self.headers = {
            'User-Agent': CUSTOM_USER_AGENT,
            'Content-type': self.content_type
        }

        if self.require_auth:
            auth_string = self.auth_username + ':' + self.auth_password
            auth_string = base64.b64encode(auth_string)
            self.headers['Authorization'] = "Basic " + auth_string

    def _dict_to_xml(self,tag, d):
        el = Element(tag)
        for key, val in d.items():
            child = Element(key)
            child.text = str(val)
            el.append(child)

        return tostring(el)

    def _dict_to_json(self, d):
        return json.dumps(d)

    # Warning: Threaded so it may be sent later and state may change.
    # Never access any AD2* state vars in a threaded function.
    @threaded
    @raise_with_stack
    def _do_post(self, data, app=None):

        # If threaded app will be valid if not it will be None.
        # We need app to send logs and access static values only.
        if app is None:
            app = current_app

        if self.is_ssl:
            if sys.version_info >= (2,7,9):
                http_handler = HTTPSConnection(self.url, context=ssl._create_unverified_context(), timeout=10)
            else:
                http_handler = HTTPSConnection(self.url, timeout=10)
        else:
            http_handler = HTTPConnection(self.url, timeout=10)

        http_handler.request(CUSTOM_METHOD, self.path, headers=self.headers, body=data)
        http_response = http_handler.getresponse()

        if http_response.status >= 200 and http_response.status <= 299:
            return True
        else:
            app.logger.info('Event Custom Notification Failed')
            raise Exception('Custom Notification Failed (' + str(http_response.status) + ") " + http_response.reason)

    # Warning: Threaded so it may be sent later and state may change.
    # Never access any AD2* state vars in a threaded function.
    @threaded
    @raise_with_stack
    def _do_get(self, data, app=None):

        # If threaded app will be valid if not it will be None.
        # We need app to send logs and access static values only.
        if app is None:
            app = current_app

        if self.is_ssl:
            if sys.version_info >= (2,7,9):
                http_handler = HTTPSConnection(self.url, context=ssl._create_unverified_context())
            else:
                http_handler = HTTPSConnection(self.url)
        else:
            http_handler = HTTPConnection(self.url)

        get_path = self.path + '?' + data
        http_handler.request(CUSTOM_METHOD_GET, get_path, headers=self.headers)
        http_response = http_handler.getresponse()

        if http_response.status == 200:
            return True
        else:
            app.logger.info('Event Custom Notification Failed on GET method')
            raise Exception('Custom Notification Failed')

    @raise_with_stack
    def send(self, type, text, raw):
        self.msg_to_send = text

        result = False
        if check_time_restriction(self.starttime, self.endtime):
            notify_data = {}
            if self.custom_values is not None:
                if self.custom_values:
                    try:
                        self.custom_values = ast.literal_eval(self.custom_values)
                    except ValueError:
                        pass

                    notify_data = dict((str(i['custom_key']), i['custom_value']) for i in self.custom_values)


            #replace placeholder values with actual values
            if notify_data:
                for key,val in notify_data.items():
                    if val == CUSTOM_REPLACER_SEARCH[CUSTOM_TIMESTAMP]:
                        notify_data[key] = time.strftime("%Y-%m-%d %H:%M:%S %Z", time.localtime(time.time())) # ex: 2016-12-02 10:33:19 PST
                    if val == CUSTOM_REPLACER_SEARCH[CUSTOM_MESSAGE]:
                        notify_data[key] = self.msg_to_send
                    if val == CUSTOM_REPLACER_SEARCH[RAW_MESSAGE]:
                        notify_data[key] = raw or ""
                    if val == CUSTOM_REPLACER_SEARCH[EVENTID_MESSAGE]:
                        notify_data[key] = type
                    if val == CUSTOM_REPLACER_SEARCH[EVENTDESC_MESSAGE]:
                        notify_data[key] = EVENT_TYPES[type]

            if self.method == CUSTOM_METHOD_POST:
                if self.post_type == URLENCODE:
                   result =  self._do_post(urlencode(notify_data))

                if self.post_type == XML:
                   result =  self._do_post(self._dict_to_xml('notification', notify_data))

                if self.post_type == JSON:
                    result = self._do_post(self._dict_to_json(notify_data) )

            if self.method == CUSTOM_METHOD_GET_TYPE:
                if self.post_type == URLENCODE:
                    result = self._do_get(urlencode(notify_data))

                #only allow urlencoding on GET requests
                if self.post_type == XML:
                    return False

                if self.post_type == JSON:
                    return False

        return result

TYPE_MAP = {
    EMAIL: EmailNotification,
    PUSHOVER: PushoverNotification,
    TWILIO: TwilioNotification,
    PROWL: ProwlNotification,
    GROWL: GrowlNotification,
    CUSTOM: CustomNotification,
    TWIML: TwiMLNotification,
    UPNPPUSH: UPNPPushNotification,
    MATRIX: MatrixNotification
}
