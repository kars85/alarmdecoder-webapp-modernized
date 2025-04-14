# -*- coding: utf-8 -*-
"""
Fabric tasks for local development and cert management.

Adapted from: https://github.com/kars85/alarmdecoder-webapp
"""

import os
from fabric.api import env, local
from flask_script import Manager

from ad2web.app import create_app
from ad2web.extensions import db
from ad2web.utils import INSTANCE_FOLDER_PATH
from ad2web.settings import Setting
from ad2web.certificate import Certificate
from ad2web.certificate.constants import ACTIVE, CA, SERVER, INTERNAL, CLIENT
from ad2web.decoder import Decoder
from ad2web.ser2sock import ser2sock

env.user = ''
env.hosts = ['']

def reset():
    """Reset local debug environment."""
    local(f"rm -rf {INSTANCE_FOLDER_PATH}")
    local(f"mkdir -p {INSTANCE_FOLDER_PATH}")
    local("python manage.py initdb")


def setup():
    """Set up local development environment."""
    local("python3 -m venv env")
    activate_this = "env/bin/activate_this.py"
    with open(activate_this) as f:
        exec(f.read(), dict(__file__=activate_this))
    local("python setup.py install")
    reset()


def d(skip_reset=False):
    """Run the app in debug mode."""
    if not skip_reset:
        reset()
    local("python manage.py run")


def certs():
    """Initialize default CA and issue sample certs."""
    reset()

    app, _ = create_app()
    manager = Manager(app)

    with app.app_context():
        db.session.add(Setting(name='ser2sock_config_path', value='/etc/ser2sock'))
        db.session.commit()

        ca = Certificate(name='AlarmDecoder CA', status=ACTIVE, type=CA)
        ca.generate(ca.name)

        server = Certificate(name='AlarmDecoder Server', status=ACTIVE, type=SERVER)
        server.generate(server.name, parent=ca)

        internal = Certificate(name='AlarmDecoder Internal', status=ACTIVE, type=INTERNAL)
        internal.generate(internal.name, parent=ca)

        test_1 = Certificate(name='Test #1', status=ACTIVE, type=CLIENT)
        test_1.generate(test_1.name, parent=ca)

        test_2 = Certificate(name='Test #2', status=ACTIVE, type=CLIENT)
        test_2.generate(test_2.name, parent=ca)

        db.session.add_all([ca, server, internal, test_1, test_2])
        db.session.commit()

        cert_dir = os.path.join(os.path.sep, 'etc', 'ser2sock', 'certs')
        for cert in [ca, server, internal, test_1, test_2]:
            cert.export(cert_dir)

        Certificate.save_certificate_index()
        Certificate.save_revocation_list()
        ser2sock.hup()


def revoke_cert(name):
    """Revoke a certificate by name."""
    print('Revoking:', name)

    decoder = Decoder(None, None)
    app, _ = create_app()
    manager = Manager(app)

    with app.app_context():
        cert = Certificate.query.filter_by(name=name).first()
        if cert:
            cert.revoke()
            Certificate.save_certificate_index()
            Certificate.save_revocation_list()
            ser2sock.hup()
            db.session.add(cert)
            db.session.commit()
            print(f"{name} successfully revoked.")
        else:
            print(f"{name} not found.")


def babel():
    """Compile translation catalogs using Babel."""
    local("python setup.py compile_catalog --directory `find -name translations` --locale zh -f")
