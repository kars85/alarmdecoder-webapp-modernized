#!/usr/bin/env python3
import os
import subprocess
import openai
import sys
from pathlib import Path

# 1) Configure your key
openai.api_key = os.getenv("OPENAI_API_KEY")
if not openai.api_key:
    print("⛔️ Please set $OPENAI_API_KEY", file=sys.stderr)
    sys.exit(1)

# 2) Run pytest once to capture any failures
def run_pytest():
    p = subprocess.run(
        ["pytest", "--maxfail=1", "--disable-warnings", "--tb=short"],
        capture_output=True, text=True,
    )
    return p.returncode, p.stdout + p.stderr

# 3) Ask OpenAI to propose a patch
def propose_patch(error_log: str):
    prompt = f"""
I have a legacy Flask project under version control. When I run `pytest`, I get this single‐failure log:

Please propose a unified‑diff patch (git/patch format) that fixes *only* that failure, preserving all existing functionality. Output *only* the diff.
"""
    resp = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role":"user","content":prompt}],
        temperature=0,
    )
    # strip any markdown fences or commentary:
    patch = resp.choices[0].message.content
    # remove ```diff fences if present
    return patch.strip("```").strip()

# 4) Apply it via GNU patch
def apply_patch(patch_text: str):
    p = subprocess.Popen(["patch", "-p1"], stdin=subprocess.PIPE, text=True)
    out, err = p.communicate(patch_text)
    return p.returncode, out, err

def main():
    code, log = run_pytest()
    if code == 0:
        print("✅ All tests already passing.")
        return

    print("❌ Tests failed. Invoking OpenAI to propose a fix…")
    patch = propose_patch(log)
    if not patch:
        print("⛔️ Got no patch back!", file=sys.stderr)
        sys.exit(1)

    print("— Applying patch —\n")
    print(patch, "\n")
    rc, out, err = apply_patch(patch)
    if rc != 0:
        print("⛔️ Patch failed to apply:", err, file=sys.stderr)
        sys.exit(1)

    # 5) Re‑run pytest to verify
    rc2, newlog = run_pytest()
    if rc2 == 0:
        print("✅ Tests now pass!")
    else:
        print("❌ Still failing after patch:\n", newlog)
        sys.exit(1)

if __name__ == "__main__":
    main()

