"""Command line front end: python -m pkgcheck.cli SPEC VERSION [VERSION ...]"""

import sys

from pkgcheck import constraints

USAGE = "usage: python -m pkgcheck.cli SPEC VERSION [VERSION ...]"


def main(argv=None, stdout=None, stderr=None):
    argv = sys.argv[1:] if argv is None else argv
    stdout = sys.stdout if stdout is None else stdout
    stderr = sys.stderr if stderr is None else stderr
    if len(argv) < 2:
        stderr.write(USAGE + "\n")
        return 2
    try:
        best = constraints.newest(argv[1:], argv[0])
    except ValueError as exc:
        stderr.write(f"error: {exc}\n")
        return 2
    if best is None:
        stdout.write("none\n")
        return 1
    stdout.write(best + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
