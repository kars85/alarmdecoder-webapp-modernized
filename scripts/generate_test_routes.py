# scripts/generate_test_routes.py
import os
from flask import Flask
from ad2web.app import create_app

def extract_routes(app: Flask):
    routes = []
    for rule in app.url_map.iter_rules():
        if "GET" in rule.methods and not rule.rule.startswith("/static"):
            routes.append(rule.rule)
    return sorted(routes)

app, _ = create_app(config={"TESTING": True})
routes = extract_routes(app)

output_file = "tests/test_routes.py"
with open(output_file, "w") as f:
    f.write("import pytest\n")
    f.write("from ad2web.app import create_app\n\n")
    f.write(f"@pytest.mark.parametrize(\"route\", {routes})\n")
    f.write("def test_route_health(route):\n")
    f.write("    app, _ = create_app(config={\"TESTING\": True})\n")
    f.write("    client = app.test_client()\n")
    f.write("    response = client.get(route)\n")
    f.write("    assert response.status_code in [200, 302], f\"{route} failed with {response.status_code}\"\n")

print(f"✅ Generated {output_file} with {len(routes)} routes.")
