# -*- coding: utf-8 -*-

import os
import datetime
import tarfile
import io
import time
import tempfile
import subprocess

from flask import current_app

from OpenSSL import crypto
from sqlalchemy import Column, orm
# No longer need importlib here for this purpose
from ..extensions import db
from ..utils import tar_add_textfile

# --- FIX: Import Setting and Constants directly ---
from ad2web.settings.models import Setting
from .constants import (
    CA, REVOKED, TGZ, PKCS12, BKS, CRL_CODE
)
# --- END FIX ---

# --- REMOVE THIS FUNCTION ---
# # Function to dynamically import Setting and certificate constants from ad2web.settings and ad2web.user.constants
# # Replace the current function with:
# def get_certificate_constants():
#     settings_module = importlib.import_module('ad2web.settings.models')
#     Setting = settings_module.Setting
#
#     # Import these from certificate constants directly
#     # Instead of getting from user.constants
#     from .constants import (CA, SERVER, CLIENT, CERTIFICATE_STATUS,
#                             REVOKED, ACTIVE, EXPIRED, PACKAGE_TYPES,
#                             TGZ, PKCS12, BKS, CRL_CODE)
#
#     return Setting, CA, SERVER, CLIENT, CERTIFICATE_STATUS, REVOKED, ACTIVE, EXPIRED, PACKAGE_TYPES, TGZ, PKCS12, BKS, CRL_CODE
# --- END REMOVAL ---


class Certificate(db.Model):
    __tablename__ = 'certificates'

    id = Column(db.Integer, primary_key=True, autoincrement=True)
    name = Column(db.String(32), unique=True, nullable=False)
    serial_number = Column(db.String(32), nullable=False)
    status = Column(db.SmallInteger, nullable=False)
    type = Column(db.SmallInteger, nullable=False)
    certificate = Column(db.Text, nullable=False)
    key = Column(db.Text, nullable=True)
    created_on = Column(db.TIMESTAMP, server_default=db.func.current_timestamp())
    revoked_on = Column(db.TIMESTAMP)
    description = Column(db.String(255))
    user_id = Column(db.Integer, db.ForeignKey("users.id"))
    ca_id = Column(db.Integer)

    @orm.reconstructor
    def init_on_load(self):
        try:
            self.key_obj = crypto.load_privatekey(crypto.FILETYPE_PEM, self.key)
        except crypto.Error:
            self.key_obj = None

        try:
            self.certificate_obj = crypto.load_certificate(crypto.FILETYPE_PEM, self.certificate)
        except crypto.Error:
            self.certificate_obj = None

    @classmethod
    def get_by_id(cls, id):
        return cls.query.filter_by(id=id).first_or_404()

    @classmethod
    def save_certificate_index(cls):
        """
        Saves the certificate index used by ser2sock
        """
        # Now Setting is directly available
        ser2sock_config_path = Setting.get_by_name('ser2sock_config_path').value
        if not ser2sock_config_path:
            raise ValueError('ser2sock_config_path is not set.')

        path = os.path.join(ser2sock_config_path, 'certs', 'certindex')

        with open(path, 'w') as cert_index:
            for cert in cls.query.all():
                # Now CA is directly available
                if cert.type != CA:
                    revoked_time = ''
                    if cert.revoked_on:
                        revoked_time = time.strftime('%y%m%d%H%M%SZ', cert.revoked_on.utctimetuple())

                    subject = '/'.join(['='.join(t) for t in [()] + cert.certificate_obj.get_subject().get_components()])
                    cert_index.write("\t".join([
                        CRL_CODE[cert.status], # Now CRL_CODE is directly available
                        cert.certificate_obj.get_notAfter()[2:],  # trim off the first two characters in the year.
                        revoked_time,
                        cert.serial_number.zfill(2),
                        'unknown',
                        subject
                    ]) + "\n")

    @classmethod
    def save_revocation_list(cls):
        """
        Saves the certificate revocation list used by ser2sock.
        """
        # Now Setting is directly available
        ser2sock_config_path = Setting.get_by_name('ser2sock_config_path').value
        if not ser2sock_config_path:
            raise ValueError('ser2sock_config_path is not set.')

        path = os.path.join(ser2sock_config_path, 'ser2sock.crl')

        # Now CA is directly available
        ca_cert = cls.query.filter_by(type=CA).first()

        # Ensure CA certificate exists before proceeding
        if not ca_cert or not ca_cert.certificate_obj or not ca_cert.key_obj:
             current_app.logger.error("CA certificate or key not found or loaded correctly. Cannot generate CRL.")
             # Decide how to handle: raise error, return, log?
             # For now, let's prevent export if CA is invalid
             return # Or raise an exception

        with open(path, 'w') as crl_file:
            crl = crypto.CRL()

            for cert in cls.query.all():
                # Now CA is directly available
                if cert.type != CA:
                    # Now REVOKED is directly available
                    if cert.status == REVOKED:
                        revoked = crypto.Revoked()

                        revoked.set_reason(None)
                        # NOTE: crypto.Revoked() expects YYYY instead of YY as needed by the cert index above.
                        # Ensure revoked_on is not None before formatting
                        if cert.revoked_on:
                             revoked.set_rev_date(time.strftime('%Y%m%d%H%M%SZ', cert.revoked_on.utctimetuple()))
                        else:
                             # Handle case where status is REVOKED but date is missing? Log or use current time?
                             current_app.logger.warning(f"Certificate ID {cert.id} is REVOKED but has no revoked_on date. Using current time for CRL.")
                             revoked.set_rev_date(time.strftime('%Y%m%d%H%M%SZ', datetime.datetime.utcnow().utctimetuple()))

                        revoked.set_serial(cert.serial_number.encode('ascii')) # PyOpenSSL might need bytes

                        crl.add_revoked(revoked)

            try:
                # Ensure CA objects are valid before exporting
                crl_data = crl.export(ca_cert.certificate_obj, ca_cert.key_obj, days=365) # Added days argument for validity
                crl_file.write(crl_data.decode('ascii')) # export returns bytes
            except Exception as e:
                current_app.logger.error(f"Failed to export CRL: {e}")
                # Handle error appropriately

    def revoke(self):
        # Now REVOKED is directly available
        self.status = REVOKED
        self.revoked_on = datetime.datetime.utcnow() # Use UTC for consistency

    def generate(self, common_name, parent=None):
        self.serial_number = self._generate_serial_number(parent)

        # Generate a key and apply it to our cert.
        key = self._create_key()
        req = self._create_request(common_name, key)
        cert = self._create_cert(req, key, self.serial_number, parent)

        self.certificate = crypto.dump_certificate(crypto.FILETYPE_PEM, cert).decode('ascii')
        self.certificate_obj = cert

        self.key = crypto.dump_privatekey(crypto.FILETYPE_PEM, key).decode('ascii')
        self.key_obj = key

    def _create_key(self, type=crypto.TYPE_RSA, bits=2048):
        key = crypto.PKey()
        key.generate_key(type, bits)

        return key

    def _create_request(self, common_name, key):
        req = crypto.X509Req()

        subject = req.get_subject()
        subject.O = "AlarmDecoder"
        subject.CN = common_name # Should already be string

        req.set_pubkey(key)
        req.sign(key, 'sha256') # Use SHA256 instead of MD5

        return req

    def _create_cert(self, req, key, serial_number, parent=None):
        cert = crypto.X509()

        cert.set_version(2)
        # Ensure serial_number is an integer for set_serial_number
        try:
            cert.set_serial_number(int(serial_number))
        except ValueError:
            # Handle case where serial_number might not be a simple integer string
            # Maybe hash it or use a default? For now, raise error.
             raise ValueError(f"Invalid serial number format: {serial_number}")

        cert.gmtime_adj_notBefore(0)
        cert.gmtime_adj_notAfter(20*365*24*60*60)  # 20 years.
        cert.set_subject(req.get_subject())
        cert.set_pubkey(req.get_pubkey())

        # Set specific extensions based on whether or not we're the CA.
        if parent is None: # This is the CA
            # CA Constraints
            cert.add_extensions([
                crypto.X509Extension(b"basicConstraints", True, b"CA:TRUE"),
                crypto.X509Extension(b"keyUsage", True, b"keyCertSign, cRLSign"),
                crypto.X509Extension(b"subjectKeyIdentifier", False, b"hash", subject=cert),
            ])
             # Authority Key Identifier for self-signed CA points to itself
            cert.add_extensions([
                crypto.X509Extension(b"authorityKeyIdentifier", False, b"keyid:always,issuer:always", issuer=cert)
            ])


            # CA cert is self-signed.
            cert.set_issuer(cert.get_subject()) # Issuer is self
            cert.sign(key, 'sha256') # Use SHA256

        else: # This is a server/client certificate signed by parent (CA)
            # Ensure parent objects are valid
            if not parent.certificate_obj or not parent.key_obj:
                 raise ValueError("Parent CA certificate or key is not loaded correctly.")

             # End Entity Constraints (e.g., TLS Server/Client)
            cert.add_extensions([
                crypto.X509Extension(b"basicConstraints", False, b"CA:FALSE"),
                # Define key usage - adjust as needed for SERVER vs CLIENT type if distinguished
                crypto.X509Extension(b"keyUsage", True, b"digitalSignature, keyEncipherment"),
                # Extended Key Usage (e.g., serverAuth, clientAuth)
                crypto.X509Extension(b"extendedKeyUsage", False, b"serverAuth, clientAuth"),
                crypto.X509Extension(b"subjectKeyIdentifier", False, b"hash", subject=cert),
                crypto.X509Extension(b"authorityKeyIdentifier", False, b"keyid:always,issuer:always", issuer=parent.certificate_obj)
            ])

            # Signed by the CA.
            cert.set_issuer(parent.certificate_obj.get_subject())
            cert.sign(parent.key_obj, 'sha256') # Use SHA256

        return cert

    def _generate_serial_number(self, parent=None):
        if parent is None: # CA Serial Number
            # CAs often have serial 1, but ensure it doesn't conflict if regenerated
            # Maybe use timestamp or a fixed low number? Using 1 for simplicity.
            return 1

        # Now Setting is directly available
        # Ensure default value is treated as integer
        serial_setting = Setting.get_by_name('ssl_serial_number', default='1')
        current_serial = int(serial_setting.value)
        next_serial = current_serial + 1
        serial_setting.value = str(next_serial) # Store as string if DB expects it

        db.session.add(serial_setting)
        # db.session.commit() # Commit might be better handled by the calling view/function

        return next_serial # Return the integer value

    def export(self, path):
        # Ensure path exists
        os.makedirs(path, exist_ok=True)
        # Write with text mode ('w') since key/cert are strings now
        with open(os.path.join(path, '{0}.key'.format(self.name)), 'w') as f:
             f.write(self.key)
        with open(os.path.join(path, '{0}.pem'.format(self.name)), 'w') as f:
            f.write(self.certificate)


class CertificatePackage(object):
    """
    Represents a downloadable package of certificates
    """

    def __init__(self, certificate, ca):
        self.certificate = certificate
        self.ca = ca
        self.mime_type = None
        self.filename = None # Added filename attribute
        self.data = None

    # Now TGZ, PKCS12, BKS are defined at module level
    def create(self, package_type=TGZ):
        if package_type == TGZ:
            mime_type = 'application/x-gzip'
            filename, data = self._create_tgz()

        elif package_type == PKCS12:
            mime_type = 'application/x-pkcs12'
            filename, data = self._create_pkcs12()

        elif package_type == BKS:
            mime_type = 'application/octet-stream'
            filename, data = self._create_bks()

        else:
            raise ValueError('Invalid package type')

        self.mime_type = mime_type
        self.filename = filename
        self.data = data

        return mime_type, filename, data

    def _create_tgz(self):
        filename = self.certificate.name + '.tar.gz'
        fileobj = io.BytesIO()

        # Use text mode for tarfile since cert/key data are likely strings from DB
        # Need to encode them to bytes before adding
        with tarfile.open(name=filename, mode='w:gz', fileobj=fileobj) as tar:
            # Create a directory entry first
            tarinfo = tarfile.TarInfo(name=self.certificate.name)
            tarinfo.type = tarfile.DIRTYPE
            tarinfo.mode = 0o755
            tarinfo.mtime = int(time.time())
            tar.addfile(tarinfo)

            # Add files inside the directory
            tar_add_textfile(tar, 'ca.pem', self.ca.certificate.encode('utf-8'), parent_path=self.certificate.name)
            tar_add_textfile(tar, self.certificate.name + '.pem', self.certificate.certificate.encode('utf-8'), parent_path=self.certificate.name)
            tar_add_textfile(tar, self.certificate.name + '.key', self.certificate.key.encode('utf-8'), parent_path=self.certificate.name)

        return filename, fileobj.getvalue()

    def _create_pkcs12(self, password='', export=True):
        filename = self.certificate.name + '.p12'
        p12cert = crypto.PKCS12()

        # Ensure objects are valid
        if not self.ca.certificate_obj or not self.certificate.certificate_obj or not self.certificate.key_obj:
             raise ValueError("Cannot create PKCS12: Required certificate or key object is missing.")

        p12cert.set_ca_certificates((self.ca.certificate_obj,))
        p12cert.set_certificate(self.certificate.certificate_obj)
        p12cert.set_privatekey(self.certificate.key_obj)
        # Friendly name expects bytes
        try:
            p12cert.set_friendlyname(self.certificate.name.encode('utf-8'))
        except AttributeError:
             # Handle if name is not a string
             p12cert.set_friendlyname(str(self.certificate.name).encode('utf-8'))


        if export:
            # Export passphrase must be bytes
            data = p12cert.export(passphrase=password.encode('utf-8'))
        else:
            data = p12cert

        return filename, data

    def _create_bks(self, password='alarmdecoder'): # Set default password or require one
         # --- IMPORTANT SECURITY NOTE ---
         # Hardcoding passwords ('alarmdecoder' or '') is insecure.
         # Consider requiring a user-provided password for BKS/PKCS12 generation.
         bks_password = password # Use provided password

         # Check if keytool exists
         try:
             subprocess.run(['keytool', '-help'], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
         except (FileNotFoundError, subprocess.CalledProcessError):
              raise RuntimeError("`keytool` command not found or not working. BKS generation requires a Java Development Kit (JDK).")

         # Find BouncyCastle provider jar - This needs a reliable path
         # FIXME: Don't hardcode this path. Find it dynamically or require config.
         # Example: Use an environment variable or app config setting
         bouncycastle_path = current_app.config.get('BOUNCYCASTLE_JAR_PATH')
         if not bouncycastle_path or not os.path.exists(bouncycastle_path):
             # Fallback attempt (less reliable)
             # bouncycastle_path = '/usr/share/java/bcprov.jar' # Example path on some Linux systems
             # if not os.path.exists(bouncycastle_path):
                 raise FileNotFoundError("BouncyCastle JAR path not configured or invalid ('BOUNCYCASTLE_JAR_PATH'). Cannot generate BKS.")


         # Create our base PKCS12 cert (in memory)
         # Use an empty password for intermediate P12 as keytool will prompt otherwise or needs specific handling
         intermediate_p12_password = ''
         _, p12cert_obj = self._create_pkcs12(password=intermediate_p12_password, export=False) # Get the PKCS12 object
         p12data = p12cert_obj.export(passphrase=intermediate_p12_password.encode('utf-8'))

         filename = self.certificate.name + '.bks'
         tmpdir = tempfile.mkdtemp() # Create a temporary directory

         try:
             p12file_path = os.path.join(tmpdir, 'temp.p12')
             cafile_path = os.path.join(tmpdir, 'ca.pem')
             bksfile_path = os.path.join(tmpdir, 'temp.bks')

             # Write intermediate P12 file
             with open(p12file_path, 'wb') as p12file:
                 p12file.write(p12data)

             # Write CA certificate file
             with open(cafile_path, 'w') as cafile:
                 cafile.write(self.ca.certificate)

             # Define keytool commands
             keytool_cmd_import_ks = [
                 "keytool", "-importkeystore",
                 "-destkeystore", bksfile_path,
                 "-srckeystore", p12file_path,
                 "-srcstoretype", "PKCS12",
                 "-alias", self.certificate.name, # Alias should match the one in P12
                 "-storetype", "BKS",
                 "-provider", "org.bouncycastle.jce.provider.BouncyCastleProvider",
                 "-providerpath", bouncycastle_path,
                 "-srcstorepass", intermediate_p12_password,
                 "-deststorepass", bks_password, # Use the final BKS password
                 "-noprompt"
             ]

             keytool_cmd_import_ca = [
                 "keytool", "-importcert", # Use -importcert for adding trusted cert
                 "-trustcacerts",
                 "-alias", "ca", # Use a distinct alias for the CA cert
                 "-file", cafile_path,
                 "-keystore", bksfile_path, # Import into the BKS keystore created above
                 "-storetype", "BKS",
                 "-providerclass", "org.bouncycastle.jce.provider.BouncyCastleProvider", # Use providerclass for -importcert
                 "-providerpath", bouncycastle_path,
                 "-storepass", bks_password, # Password for the keystore
                 "-noprompt"
             ]

             # Execute keytool commands
             def run_keytool(cmd):
                 current_app.logger.debug(f"Running keytool command: {' '.join(cmd)}")
                 # Use run for better error handling
                 process = subprocess.run(cmd, capture_output=True, text=True, check=False) # Don't check=True initially
                 if process.returncode != 0:
                      error_msg = f"keytool command failed (exit code {process.returncode}): {' '.join(cmd)}\nStderr: {process.stderr}\nStdout: {process.stdout}"
                      current_app.logger.error(error_msg)
                      raise RuntimeError(error_msg)
                 current_app.logger.debug(f"keytool stdout: {process.stdout}")
                 current_app.logger.debug(f"keytool stderr: {process.stderr}")


             run_keytool(keytool_cmd_import_ks)
             run_keytool(keytool_cmd_import_ca)


             # Retrieve BKS data
             with open(bksfile_path, 'rb') as bksfile:
                 data = bksfile.read()

         finally:
              # Clean up temporary directory and its contents
              import shutil
              shutil.rmtree(tmpdir)


         return filename, data