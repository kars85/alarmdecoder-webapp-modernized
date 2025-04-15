from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509 import CertificateRevocationListBuilder, RevokedCertificateBuilder, Name, NameAttribute
from cryptography.x509.oid import NameOID

import os
from datetime import datetime, timezone, timedelta
from flask import current_app
from sqlalchemy import Column, Integer, SmallInteger, String, Text, TIMESTAMP, ForeignKey
from sqlalchemy.orm import reconstructor

from ad2web.extensions import db
from ad2web.settings.models import Setting
from ad2web.certificate.constants import CA, REVOKED

class Certificate(db.Model):
    __tablename__ = 'certificates'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(32), unique=True, nullable=False)
    serial_number = Column(String(32), nullable=False)
    status = Column(SmallInteger, nullable=False, default=0)
    type = Column(SmallInteger, nullable=False)
    certificate = Column(Text, nullable=False)
    key = Column(Text, nullable=True)
    created_on = Column(TIMESTAMP, server_default=db.func.current_timestamp())
    revoked_on = Column(TIMESTAMP, nullable=True)
    description = Column(String(255), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    ca_id = Column(Integer, nullable=True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.key_obj = None
        self.certificate_obj = None

    @reconstructor
    def init_on_load(self):
        try:
            if self.key:
                self.key_obj = serialization.load_pem_private_key(
                    self.key.encode('utf-8'),
                    password=None,
                    backend=default_backend()
                )
        except Exception as e:
            current_app.logger.error(f"Failed to load private key for cert ID {self.id}: {e}")
            self.key_obj = None

        try:
            if self.certificate:
                self.certificate_obj = x509.load_pem_x509_certificate(
                    self.certificate.encode('utf-8'),
                    backend=default_backend()
                )
        except Exception as e:
            current_app.logger.error(f"Failed to load certificate for cert ID {self.id}: {e}")
            self.certificate_obj = None

    def revoke(self):
        if self.status != REVOKED:
            self.status = REVOKED
            self.revoked_on = datetime.now(timezone.utc)
            return True
        return False


class CertificateManager:
    def __init__(self, cert_model, ca_model=None):
        self.cert = cert_model
        self.ca = ca_model

    def generate(self, common_name):
        self.cert.serial_number = str(self._generate_serial_number())
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048, backend=default_backend())
        req = self._create_request(common_name, key)
        cert = self._create_cert(req, key)

        self.cert.key = key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption()
        ).decode('utf-8')

        self.cert.certificate = cert.public_bytes(serialization.Encoding.PEM).decode('utf-8')
        self.cert.key_obj = key
        self.cert.certificate_obj = cert

    def export(self, path):
        os.makedirs(path, exist_ok=True)
        with open(os.path.join(path, f"{self.cert.name}.key"), 'w') as key_file:
            key_file.write(self.cert.key)
        with open(os.path.join(path, f"{self.cert.name}.pem"), 'w') as cert_file:
            cert_file.write(self.cert.certificate)
    @staticmethod
    def _generate_serial_number():
        serial_setting = Setting.get_by_name('ssl_serial_number', default='1')
        try:
            current_serial = int(serial_setting.value or '1')
        except ValueError:
            current_app.logger.warning(f"Invalid ssl_serial_number '{serial_setting.value}', resetting to 1.")
            current_serial = 1
        next_serial = current_serial + 1
        serial_setting.value = str(next_serial)
        db.session.add(serial_setting)
        return current_serial
    @staticmethod
    def _create_request(common_name, key):
        subject = Name([
            NameAttribute(NameOID.COMMON_NAME, common_name),
            NameAttribute(NameOID.ORGANIZATION_NAME, "AlarmDecoder")
        ])
        return x509.CertificateSigningRequestBuilder().subject_name(subject).sign(
            key, hashes.SHA256(), default_backend()
        )

    def _create_cert(self, req, key):
        issuer = self.ca.certificate_obj.subject if self.ca else req.subject
        issuer_key = self.ca.key_obj if self.ca else key

        cert_builder = x509.CertificateBuilder()
        cert_builder = cert_builder.subject_name(req.subject)
        cert_builder = cert_builder.issuer_name(issuer)
        cert_builder = cert_builder.public_key(req.public_key())
        cert_builder = cert_builder.serial_number(int(self.cert.serial_number))
        cert_builder = cert_builder.not_valid_before(datetime.now(timezone.utc))
        cert_builder = cert_builder.not_valid_after(datetime.now(timezone.utc) + timedelta(days=7300))
        cert_builder = cert_builder.add_extension(
            x509.BasicConstraints(ca=(self.ca is None), path_length=None), critical=True
        )

        return cert_builder.sign(private_key=issuer_key, algorithm=hashes.SHA256(), backend=default_backend())

    @classmethod
    def save_revocation_list(cls):
        config_path_setting = Setting.get_by_name('ser2sock_config_path')
        if not config_path_setting or not config_path_setting.value:
            current_app.logger.error('ser2sock_config_path is not set.')
            return

        path = os.path.join(config_path_setting.value, 'ser2sock.crl')
        os.makedirs(os.path.dirname(path), exist_ok=True)

        ca_cert = Certificate.query.filter_by(type=CA).first()
        if not ca_cert or not ca_cert.certificate_obj or not ca_cert.key_obj:
            current_app.logger.error("CA certificate or key not found or not loaded. Cannot generate CRL.")
            return

        builder = CertificateRevocationListBuilder()
        builder = builder.issuer_name(ca_cert.certificate_obj.subject)
        builder = builder.last_update(datetime.now(timezone.utc))
        builder = builder.next_update(datetime.now(timezone.utc) + timedelta(days=365))

        revoked_certs = Certificate.query.filter(Certificate.type != CA, Certificate.status == REVOKED).all()

        for cert in revoked_certs:
            if not cert.serial_number:
                current_app.logger.warning(f"Skipping revoked cert ID {cert.id} due to missing serial number.")
                continue

            revocation_date = cert.revoked_on or datetime.now(timezone.utc)

            try:
                revoked = RevokedCertificateBuilder()
                revoked = revoked.serial_number(int(cert.serial_number))
                revoked = revoked.revocation_date(revocation_date)
                builder = builder.add_revoked_certificate(revoked.build(default_backend()))
            except Exception as e:
                current_app.logger.error(f"Failed to add revoked cert ID {cert.id}: {e}")

        try:
            crl = builder.sign(
                private_key=ca_cert.key_obj,
                algorithm=hashes.SHA256(),
                backend=default_backend()
            )

            with open(path, 'wb') as crl_file:
                crl_file.write(crl.public_bytes(serialization.Encoding.PEM))

            current_app.logger.info(f"CRL saved successfully to {path}")
        except Exception as e:
            current_app.logger.error(f"Failed to export CRL: {e}")
