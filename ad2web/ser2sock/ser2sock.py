import os
import psutil
import signal
from configparser import ConfigParser, DuplicateSectionError
import sh
from shutilwhich import which
from collections import OrderedDict


DEFAULT_SETTINGS = OrderedDict([
    ('daemonize', 1),
    ('device', ''),
    ('raw_device_mode', 1),
    ('baudrate', 19200),
    ('port', 10000),
    ('preserve_connections', 1),
    ('bind_ip', '0.0.0.0'),
    ('send_terminal_init', 0),
    ('device_open_delay', 5000),
    ('encrypted', '0'),
    ('ca_certificate', ''),
    ('ssl_certificate', ''),
    ('ssl_key', ''),
    ('ssl_crl', '/etc/ser2sock/ser2sock.crl'),
])


class NotFound(Exception):
    """Exception generated when ser2sock is not found."""
    pass


class HupFailed(Exception):
    """Exception generated when ser2sock fails to be hupped."""
    pass


def read_config(path):
    config = ConfigParser()
    config.read(path)
    return config


def save_config(path, config_values):
    config = read_config(path)
    try:
        config.add_section('ser2sock')
    except DuplicateSectionError:
        pass

    config_entries = OrderedDict(list(DEFAULT_SETTINGS.items()) + list(config_values.items()))

    for k, v in config_entries.items():
        config.set('ser2sock', k, str(v))

    with open(path, 'w', encoding='utf-8') as configfile:
        config.write(configfile)


def exists():
    return which('ser2sock') is not None


def start():
    try:
        sh.Command("ser2sock")('-d', _bg=True)
    except sh.CommandNotFound:
        raise NotFound('Could not locate ser2sock.')


def stop():
    for proc in psutil.process_iter(attrs=["name"]):
        if proc.info["name"] == 'ser2sock':
            try:
                proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                print(f"Could not kill ser2sock (PID {proc.pid}): {e}")


def hup():
    found = False

    for proc in psutil.process_iter(attrs=["name", "pid"]):
        if proc.info["name"] == 'ser2sock':
            try:
                proc.send_signal(signal.SIGHUP)
                found = True
            except OSError as err:
                raise HupFailed(f'Error attempting to hup ser2sock (PID {proc.info["pid"]}): {err}')

    if not found:
        start()


def update_config(path, *args, **kwargs):
    try:
        config = None
        if path:
            config_path = os.path.join(path, 'ser2sock.conf')
            config = read_config(config_path)

        config_values = {}
        if config and config.has_section('ser2sock'):
            config_values = dict(config.items('ser2sock'))

        if 'device_path' in kwargs:
            config_values['device'] = kwargs['device_path']
        if 'device_baudrate' in kwargs:
            config_values['baudrate'] = kwargs['device_baudrate']
        if 'device_port' in kwargs:
            config_values['port'] = kwargs['device_port']
        if 'use_ssl' in kwargs:
            config_values['encrypted'] = int(bool(kwargs.get('use_ssl')))

        if config_values.get('encrypted') == 1:
            cert_path = os.path.join(path, 'certs')
            os.makedirs(cert_path, mode=0o700, exist_ok=True)

            ca_cert = kwargs.get('ca_cert')
            server_cert = kwargs.get('server_cert')

            if ca_cert and server_cert:
                ca_cert.export(cert_path)
                server_cert.export(cert_path)

                config_values['ca_certificate'] = os.path.join(cert_path, f'{ca_cert.name}.pem')
                config_values['ssl_certificate'] = os.path.join(cert_path, f'{server_cert.name}.pem')
                config_values['ssl_key'] = os.path.join(cert_path, f'{server_cert.name}.key')

        if path:
            save_config(os.path.join(path, 'ser2sock.conf'), config_values)
            hup()

    except (OSError, IOError) as err:
        raise RuntimeError(f'Error updating ser2sock configuration: {err}')
