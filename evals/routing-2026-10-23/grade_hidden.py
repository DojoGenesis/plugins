#!/usr/bin/env python3
"""Hidden acceptance tests for the routing eval (PREREG-2026-10-23-routing.md).

The agent never sees these tests: they live outside the plugin directories and are not scaffolded.
After a run, the work directory the eval kept is copied to a temporary directory, the case's
hidden/test_hidden.py is copied into its root, and `python -m unittest test_hidden` runs there.

    grade_hidden.py grade <case-hidden-dir> <work-dir>
        PASS (exit 0), FAIL (exit 1), or COULD NOT RUN (exit 2). A run over 120 s is a FAIL.
    grade_hidden.py selfcheck <case-hidden-dir> <scaffold.sh>
        Known-bad and known-good check: the scaffold as written must FAIL and the scaffold with
        reference/ laid over it must PASS. Exit 0 when both hold, 1 when either doesn't.

<case-hidden-dir> holds hidden/test_hidden.py and reference/. Standard library only.
"""
import os
import shutil
import subprocess
import sys
import tempfile

TIMEOUT_S = 120
IGNORE = shutil.ignore_patterns(".git", "__pycache__", "test_hidden.py")


def run_hidden(case_dir, work_dir):
    """Return (verdict, detail): verdict is 'PASS', 'FAIL' or 'COULD NOT RUN'."""
    test = os.path.join(case_dir, "hidden", "test_hidden.py")
    if not os.path.isfile(test):
        return "COULD NOT RUN", "no hidden/test_hidden.py in " + case_dir
    if not os.path.isdir(work_dir):
        return "COULD NOT RUN", "no work directory at " + work_dir
    with tempfile.TemporaryDirectory(prefix="routing-hidden-", ignore_cleanup_errors=True) as tmp:
        root = os.path.join(tmp, "w")
        shutil.copytree(work_dir, root, ignore=IGNORE, symlinks=False)
        shutil.copyfile(test, os.path.join(root, "test_hidden.py"))
        # -E and -s keep the operator's PYTHON* variables and user site out; the work directory
        # itself must stay importable, so -I (which drops it from sys.path) is not used.
        cmd = [sys.executable, "-E", "-s", "-m", "unittest", "test_hidden", "-q"]
        try:
            p = subprocess.run(cmd, cwd=root, capture_output=True, text=True, timeout=TIMEOUT_S)
        except subprocess.TimeoutExpired:
            return "FAIL", "timed out after %d s" % TIMEOUT_S
        tail = (p.stdout + p.stderr).strip().splitlines()[-3:]
        return ("PASS" if p.returncode == 0 else "FAIL"), " | ".join(tail)


def scaffold_into(scaffold, dest):
    os.makedirs(dest)
    bash = shutil.which("bash") or "bash"
    p = subprocess.run([bash, os.path.abspath(scaffold)], cwd=dest, capture_output=True, text=True, timeout=120)
    if p.returncode != 0:
        raise RuntimeError("scaffold exited %d: %s" % (p.returncode, (p.stderr or p.stdout).strip()[-300:]))


def selfcheck(case_dir, scaffold):
    ok = True
    with tempfile.TemporaryDirectory(prefix="routing-selfcheck-", ignore_cleanup_errors=True) as tmp:
        bad = os.path.join(tmp, "bad")
        scaffold_into(scaffold, bad)
        v, d = run_hidden(case_dir, bad)
        print("known-bad (scaffold as written): %s  %s" % (v, d))
        ok = ok and v == "FAIL"
        good = os.path.join(tmp, "good")
        scaffold_into(scaffold, good)
        ref = os.path.join(case_dir, "reference")
        if not os.path.isdir(ref):
            print("known-good: COULD NOT RUN  no reference/ directory")
            return False
        shutil.copytree(ref, good, dirs_exist_ok=True)
        v, d = run_hidden(case_dir, good)
        print("known-good (reference laid over): %s  %s" % (v, d))
        ok = ok and v == "PASS"
    return ok


def main(argv):
    if len(argv) != 4 or argv[1] not in ("grade", "selfcheck"):
        print(__doc__.strip(), file=sys.stderr)
        return 2
    if argv[1] == "grade":
        v, d = run_hidden(argv[2], argv[3])
        print("%s  %s" % (v, d))
        return {"PASS": 0, "FAIL": 1}.get(v, 2)
    try:
        return 0 if selfcheck(argv[2], argv[3]) else 1
    except Exception as e:  # a scaffold that won't run is a broken case, not a failing one
        print("COULD NOT RUN  %s" % e)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
