# scaffold_tests.py

import os
import sys
from pathlib import Path

TEST_TEMPLATE = """
import pytest
from tests import TestCase

@pytest.mark.usefixtures("client")
class Test{ClassName}(TestCase):

    def create_app(self):
        from tests.test_utils import create_test_app
        return create_test_app()

{methods}
"""

TEST_METHOD = """
    def test_{name}(self):
        response = self.client.get("{route}")
        self.assert200(response)
"""

def kebab_to_camel(name):
    return ''.join(word.capitalize() for word in name.replace('.html', '').split('_'))

def main(module_name, template_path):
    test_file = Path(f"tests/test_{module_name}.py")
    if not test_file.exists():
        test_file.touch()

    methods = []
    for file in os.listdir(template_path):
        if not file.endswith(".html"):
            continue
        route = f"/{module_name}/{file.replace('.html', '')}" if file != "index.html" else f"/{module_name}/"
        method_name = file.replace('.html', '').replace('-', '_')
        methods.append(TEST_METHOD.format(name=method_name, route=route))

    class_name = kebab_to_camel(module_name)
    content = TEST_TEMPLATE.format(ClassName=class_name, methods="\n".join(methods))

    test_file.write_text(content)
    print(f"✅ Generated scaffold: {test_file}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python scaffold_tests.py <module_name> <template_path>")
        print("Example: python scaffold_tests.py settings ad2web/templates/settings/")
        sys.exit(1)

    module_name = sys.argv[1]
    template_path = sys.argv[2]
    main(module_name, template_path)
