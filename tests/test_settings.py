# tests/test_settings.py
from tests import TestCase

class TestSettings(TestCase):

    def create_app(self):
        from tests.test_utils import create_test_app
        return create_test_app()

    def setUp(self):
        super().setUp()
        self.login("admin", "123456")  # ensure admin is logged in

    def test_advanced(self):
        response = self.client.get("/settings/advanced")
        self.assert200(response)

    def test_configure_ethernet_device(self):
        response = self.client.get("/settings/network/test0")  # or 'eth0'
        self.assertIn(response.status_code, (200, 302))

    def test_configure_exports(self):
        response = self.client.get("/settings/configure_exports")
        self.assert200(response)

    def test_device_get(self):
        response = self.client.get("/settings/device")
        self.assert200(response)
        self.assertTemplateUsed("settings/device.html")

    def test_device_post_network(self):
        data = {
            "device_type": "network",
            "use_ssl": True,
            "device_path": "192.168.1.100",
        }
        response = self.client.post("/settings/device", data=data, follow_redirects=True)
        self.assert200(response)
        assert b"Device settings saved" in response.data

    def test_device_post_serial(self):
        data = {
            "device_type": "serial",
            "use_ssl": False,
            "device_path": "/dev/ttyUSB0",
        }
        response = self.client.post("/settings/device", data=data, follow_redirects=True)
        self.assert200(response)
        assert b"Device settings saved" in response.data

    def test_diagnostics(self):
        response = self.client.get("/settings/diagnostics")
        self.assert200(response)

    def test_git(self):
        response = self.client.get("/settings/git")
        self.assert200(response)

    def test_host(self):
        response = self.client.get("/settings/host")
        self.assert200(response)

    def test_hostname(self):
        response = self.client.get("/settings/hostname")
        self.assert200(response)

    def test_import(self):
        response = self.client.get("/settings/import")
        self.assert200(response)

    def test_index(self):
        response = self.client.get("/settings/")
        self.assert200(response)

    def test_layout(self):
        response = self.client.get("/settings/layout")
        self.assert200(response)

    def test_password(self):
        response = self.client.get("/settings/password")
        self.assert200(response)

    def test_port_forward(self):
        response = self.client.get("/settings/port_forward")
        self.assert200(response)

    def test_profile(self):
        response = self.client.get("/settings/profile")
        self.assert200(response)

    def test_system_email(self):
        response = self.client.get("/settings/system_email")
        self.assert200(response)

    def test_updater_config(self):
        response = self.client.get("/settings/updater_config")
        self.assert200(response)
