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
        """Access zones via settings if present."""
        return self.get_setting("zones")

    @zones.setter
    def zones(self, value):
        if "zones" not in self.settings:
            self.settings["zones"] = NotificationSetting(name="zones")
        self.settings["zones"].value = value


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
    text = Column(db.Text, nullable=False)
