# -*- coding: utf-8 -*-

import os
import html
import json
import collections

from flask import Blueprint, render_template, request, url_for, redirect
from flask import current_app as APP
from flask_login import login_required

from ..extensions import db
from ..decorators import admin_required
from .constants import (
    ARM,
    DISARM,
    POWER_CHANGED,
    ALARM,
    FIRE,
    BYPASS,
    BOOT,
    CONFIG_RECEIVED,
    ZONE_FAULT,
    ZONE_RESTORE,
    LOW_BATTERY,
    PANIC,
    EVENT_TYPES,
    LRR,
    READY,
    RFX,
    EXP,
    AUI,
)
from .models import EventLogEntry
from ..logwatch import LogWatcher
from ..utils import INSTANCE_FOLDER_PATH

log = Blueprint("log", __name__, url_prefix="/log")


@log.context_processor
def log_context_processor():
    return {
        "ARM": ARM,
        "DISARM": DISARM,
        "POWER_CHANGED": POWER_CHANGED,
        "ALARM": ALARM,
        "FIRE": FIRE,
        "BYPASS": BYPASS,
        "BOOT": BOOT,
        "CONFIG_RECEIVED": CONFIG_RECEIVED,
        "ZONE_FAULT": ZONE_FAULT,
        "ZONE_RESTORE": ZONE_RESTORE,
        "LOW_BATTERY": LOW_BATTERY,
        "PANIC": PANIC,
        "LRR": LRR,
        "READY": READY,
        "EXP": EXP,
        "RFX": RFX,
        "AUI": AUI,
        "TYPES": EVENT_TYPES,
    }


@log.route("/")
@login_required
def events():
    return render_template("log/events.html", active="events")


@log.route("/live")
@login_required
@admin_required
def live():
    return render_template("log/live.html", active="live")


@log.route("/delete")
@login_required
@admin_required
def delete():
    EventLogEntry.query.delete()
    db.session.commit()
    return redirect(url_for("log.events"))


@log.route("/alarmdecoder")
@login_required
@admin_required
def alarmdecoder_logfile():
    return render_template("log/alarmdecoder.html", active="AlarmDecoder")


@log.route("/alarmdecoder/get_data/<int:lines>", methods=["GET"])
@login_required
@admin_required
def get_log_data(lines):
    log_file = os.path.join(INSTANCE_FOLDER_PATH, "logs", "info.log")
    try:
        log_text = LogWatcher.tail(log_file, lines)
    except IOError as err:
        return json.dumps([str(err)])
    return json.dumps(log_text)


@log.route("/retrieve_events_paging_data")
@login_required
def get_events_paging_data():
    try:
        return json.dumps(DataTablesServer(request).output_result())
    except TypeError as ex:
        APP.logger.warning(f"Error processing datatables request: {ex}")
        return json.dumps({})


class DataTablesServer:
    Pages = collections.namedtuple("Pages", ["start", "length"])

    def __init__(self, request):
        self.request_values = request.values
        self.result_data = None
        self.cardinality = 0
        self.cardinality_filtered = 0
        self.run_queries()

    def output_result(self):
        return {
            "sEcho": html.escape(str(int(self.request_values["sEcho"]))),
            "iTotalRecords": int(self.cardinality),
            "iTotalDisplayRecords": int(self.cardinality_filtered),
            "aaData": [
                [str(row.timestamp), EVENT_TYPES[row.type], row.message] for row in self.result_data
            ],
        }

    def run_queries(self):
        pages = self.paging()
        search_filter = self.filtering()

        start = pages.start or 0
        limit = pages.length or 10

        try:
            if search_filter:
                query = EventLogEntry.query.filter(EventLogEntry.message.like(f"%{search_filter}%"))
                self.result_data = (
                    query.order_by(EventLogEntry.timestamp.desc()).limit(limit).offset(start)
                )
                self.cardinality_filtered = query.count()
                self.cardinality = query.count()
            else:
                query = EventLogEntry.query.order_by(EventLogEntry.timestamp.desc())
                self.result_data = query.limit(limit).offset(start)
                self.cardinality_filtered = query.count()
                self.cardinality = query.count()
        except Exception as e:
            APP.logger.error(f"Error querying event logs: {e}")

    def filtering(self):
        if "sSearch" in self.request_values and self.request_values["sSearch"]:
            return html.escape(str(self.request_values["sSearch"]))
        return None

    def paging(self):
        try:
            start_str = self.request_values.get("iDisplayStart", "")
            length_str = self.request_values.get("iDisplayLength", "")
            if start_str.isdigit() and length_str.isdigit():
                return self.Pages(start=int(start_str), length=int(length_str))
        except Exception:
            pass
        return self.Pages(start=0, length=10)
