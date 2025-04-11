"""
Safe Ruff Fixer: Applies only safe-to-auto-correct transformations.
Fixes:
- E712, E711: equality/inequality boolean comparisons
- E701: multiple statements per line
- E722: bare except
- W191: tab-to-spaces
"""

import re
from pathlib import Path

SOURCE_DIR = Path("ad2web")  # update to top-level if needed

def fix_lines(text):
    fixed = []
    for line in text.splitlines():
        orig = line

        # W191: Tabs to spaces
        line = line.replace('\t', '    ')

        # E712 / E711: True/False/None comparisons
        line = re.sub(r'\b==\s*True\b', '', line)
        line = re.sub(r'\b!=\s*None\b', ' is not None', line)
        line = re.sub(r'\b==\s*False\b', ' not', line)
        line = re.sub(r'\b!=\s*True\b', ' not', line)

        # E722: bare except ➝ except Exception:
        line = re.sub(r'^\s*except\s*:\s*$', 'except Exception:', line)

        # E701: if foo: bar() ➝ multiline
        if re.match(r'^\s*if .+:\s*[^#\s]', line) and ';' not in line:
            parts = line.split(':', 1)
            cond = parts[0] + ':'
            action = parts[1].strip()
            indent = ' ' * (len(line) - len(line.lstrip()))
            line = f"{cond}\n{indent}    {action}"

        fixed.append(line)
    return '\n'.join(fixed)

def process_py_files():
    for py_file in SOURCE_DIR.rglob("*.py"):
        code = py_file.read_text(encoding="utf-8")
        new_code = fix_lines(code)
        if code != new_code:
            bak_file = py_file.with_suffix(".py.bak")
            if bak_file.exists():
                print(f"Skipping {py_file}: backup already exists.")
                continue
            py_file.rename(bak_file)
            py_file.write_text(new_code, encoding="utf-8")
            print(f"Fixed: {py_file} (backup saved to {bak_file})")

if __name__ == "__main__":
    process_py_files()
