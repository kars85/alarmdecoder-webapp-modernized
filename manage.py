# -*- coding: utf-8 -*-

# --- Gevent ---
from gevent import monkey
monkey.patch_all()

import click
from flask.cli import with_appcontext

from ad2web.app import create_app, init_app
from ad2web.extensions import db
from ad2web.notifications.models import NotificationMessage
from ad2web.notifications.constants import DEFAULT_EVENT_MESSAGES

from alembic.config import Config as AlembicConfig
from alembic import command as alembic_command

app, socketio = create_app()

@click.group()
def cli():
    """Management script for the AlarmDecoder WebApp"""
    pass

@cli.command("run")
def run_dev_server():
    """Run the development server with SocketIO."""
    init_app(app, socketio)
    app.debug = True
    socketio.run(app, host="0.0.0.0", port=5000)

@cli.command("initdb")
@click.option('--drop', is_flag=True, help='Drop all tables before creating.')
@with_appcontext
def init_db(drop):
    """Initialize or reset the database."""
    try:
        if drop:
            click.confirm('This will DROP all tables. Continue?', abort=True)
            db.drop_all()
            click.echo('Dropped all tables.')

        db.create_all()

        alembic_cfg = AlembicConfig('alembic.ini')
        alembic_command.stamp(alembic_cfg, "head")

        for event, message in DEFAULT_EVENT_MESSAGES.items():
            db.session.add(NotificationMessage(id=event, text=message))

        db.session.commit()
        click.echo("Database initialization complete!")
    except Exception as err:
        click.echo(f"Database initialization failed: {err}", err=True)
        db.session.rollback()

if __name__ == "__main__":
    cli()
