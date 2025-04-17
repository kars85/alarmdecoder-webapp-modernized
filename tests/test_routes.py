import pytest
from ad2web.app import create_app

@pytest.mark.parametrize("route", [
    "/", "/1/avatar/image.png", "/1/history", "/1/profile",
    "/admin/", "/admin/user/1", "/admin/user/create", "/admin/user/remove/1", "/admin/users", "/admin/users/failed_logins",
    "/cameras/", "/cameras/camera_list", "/cameras/create_camera", "/cameras/edit_camera/1", "/cameras/remove_camera/1",
    "/help", "/keypad/", "/keypad/button_index", "/keypad/create_button", "/keypad/edit/1", "/keypad/legacy", "/keypad/remove/1", "/keypad/specials",
    "/license", "/log/", "/log/alarmdecoder", "/log/alarmdecoder/get_data/1", "/log/delete", "/log/live", "/log/retrieve_events_paging_data",
    "/login", "/logout", "/reset_password", "/settings/", "/settings/advanced",
    "/settings/certificates/", "/settings/certificates/1", "/settings/certificates/1/download/json", "/settings/certificates/1/revoke",
    "/settings/certificates/generate", "/settings/certificates/generateCA", "/settings/certificates/revokeCA",
    "/settings/configure_exports", "/settings/configure_system_email", "/settings/configure_updater", "/settings/device", "/settings/diagnostics",
    "/settings/disable_forward", "/settings/export", "/settings/exports", "/settings/get_ethernet_info/test0",
    "/settings/get_imports_list", "/settings/git", "/settings/host", "/settings/hostname", "/settings/import", "/settings/network/test0",
    "/settings/notifications/", "/settings/notifications/1/copy", "/settings/notifications/1/edit", "/settings/notifications/1/remove",
    "/settings/notifications/1/review", "/settings/notifications/1/toggle", "/settings/notifications/1/zones",
    "/settings/notifications/create", "/settings/notifications/create/custom", "/settings/notifications/messages", "/settings/notifications/messages/edit/1",
    "/settings/password", "/settings/port_forward", "/settings/profile", "/settings/reboot", "/settings/shutdown",
    "/settings/zones/", "/settings/zones/create", "/settings/zones/edit/1", "/settings/zones/import", "/settings/zones/remove/1",
    "/setup/", "/setup/account", "/setup/complete", "/setup/device", "/setup/local", "/setup/network", "/setup/sslclient", "/setup/sslserver",
    "/setup/test", "/setup/type", "/signup", "/update/", "/update/check_for_updates", "/update/checkavailable", "/update/firmware", "/update/update_firmware"
])
def test_route_health(route):
    app, _ = create_app(config={"TESTING": True})
    client = app.test_client()
    response = client.get(route)
    assert response.status_code in [200, 302, 403], f"{route} failed with {response.status_code}"
