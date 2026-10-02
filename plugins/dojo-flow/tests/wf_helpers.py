"""Shared helpers for the dojo-flow tests: paths, node discovery, and a runner for the Node stub harness."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(HERE)
WORKFLOWS = os.path.join(PLUGIN, "workflows")
BUILD_JS = os.path.join(WORKFLOWS, "build.js")
CONVERGE_JS = os.path.join(WORKFLOWS, "converge.js")
HARNESS = os.path.join(HERE, "harness.js")
DAG_OPS = os.path.join(PLUGIN, "scripts", "dag_ops.py")
CASES = os.path.join(HERE, "overlap_cases.json")


def find_node():
    """DOJO_NODE wins, then PATH. Never a hard-coded location."""
    env = os.environ.get("DOJO_NODE")
    if env:
        return env if os.path.isfile(env) or shutil.which(env) else None
    return shutil.which("node")


NODE = find_node()
SKIP_REASON = ("node was not found on PATH (set DOJO_NODE to a node binary). A stripped environment such as "
               "`env -i PATH=/usr/bin:/bin` hides a Homebrew or nvm node, so every test that drives the workflow "
               "scripts through the stub harness is SKIPPED, not passed")
if not NODE:
    sys.stderr.write("dojo-flow tests: " + SKIP_REASON + ".\n")
needs_node = unittest.skipUnless(NODE, SKIP_REASON)


def run_node(mode, workflow, payload):
    """Run the harness in `mode` with `payload` written to a temp JSON file. A crash is a test failure."""
    with tempfile.TemporaryDirectory(prefix="dojo-flow-test-") as tmp:
        path = os.path.join(tmp, "payload.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh)
        proc = subprocess.run([NODE, HARNESS, mode, workflow, path], stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, universal_newlines=True, timeout=120)
    if proc.returncode != 0:
        raise AssertionError("node harness crashed (exit %s): %s" % (proc.returncode, proc.stderr[-800:]))
    try:
        out = json.loads(proc.stdout)
    except ValueError:
        raise AssertionError("node harness printed unparseable output: %r" % proc.stdout[:300])
    if isinstance(out, dict) and out.get("harnessError"):
        raise AssertionError("harness error: " + out["harnessError"])
    return out


def run_workflow(workflow, args, responses, args_raw=None):
    scenario = {"responses": responses}
    if args_raw is not None:
        scenario["argsRaw"] = args_raw
    else:
        scenario["args"] = args
    return run_node("run", workflow, scenario)
