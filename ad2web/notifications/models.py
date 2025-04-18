# -*- coding: utf-8 -*-

from sqlalchemy import Column
from sqlalchemy.orm.collections import attribute_mapped_collection

from ..extensions import db


class Notification(db.Model):
    __tablename__ = "notifications"

    id = Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(128), nullable=False)  # optional: required constraint
    description = Column(db.String(255), nullable=False)
    type = Column(db.Integer, nullable=False)
    user_id = Column(db.Integer, db.ForeignKey("users.id"))
    enabled = Column(db.Integer, default=1)

    settings = db.relationship(
        "NotificationSetting",
        backref="notification",
        collection_class=attribute_mapped_collection("name"),
        cascade="all, delete-orphan",
    )

    def get_setting(self, name, default=None):
        if name in self.settings:
            return self.settings[name].value
        return default

    @property
    def zones(self):
        setting = self.settings.get("zones") if self.settings else None
        if not setting or not setting.string_value:
            return []
        try:
            return list(map(int, setting.string_value.split(",")))
        except Exception:
            return []

    @zones.setter
    def zones(self, value):
        # Defensive: ensure settings dict is initialized
        if self.settings is None:
            self.settings = {}

        zone_str = ",".join(str(z) for z in value or [])
        setting = self.settings.get("zones")

        if setting is None:
            setting = NotificationSetting(name="zones", string_value=zone_str)
            self.settings["zones"] = setting
            # Ensure the backref is properly linked for SQLAlchemy
            setting.notification = self
        else:
            setting.string_value = zone_str


class NotificationSetting(db.Model):
    __tablename__ = "notification_settings"

    id = Column(db.Integer, primary_key=True, autoincrement=True)
    name = Column(db.String(32), nullable=False)

    notification_id = Column(db.Integer, db.ForeignKey("notifications.id"))

    int_value = Column(db.Integer)
    string_value = Column(db.String(255))

    @property
    def value(self):
        for k in ("int_value", "string_value"):
            v = getattr(self, k)
            if v is not None:
                return v
        return None

    @value.setter
    def value(self, value):
        if isinstance(value, int):
            self.int_value = value
            self.string_value = None
        else:
            self.string_value = str(value)
            self.int_value = None


class NotificationMessage(db.Model):
    __tablename__ = "notification_messages"

    id = Column(db.Integer, primary_key=True)
    content = Column(db.Text, nullable=False)

    # 🧩 Fix: add this to support `notification=...` during init
    notification_id = db.Column(db.Integer, db.ForeignKey("notifications.id"))
    notification = db.relationship("Notification", backref="messages")

