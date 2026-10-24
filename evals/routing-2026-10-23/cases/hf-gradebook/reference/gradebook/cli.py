"""Command line front end: python -m gradebook.cli [file.csv]"""

import sys

from gradebook import report

USAGE = "usage: python -m gradebook.cli [file.csv]"


def main(argv=None, stdin=None, stdout=None, stderr=None):
    argv = sys.argv[1:] if argv is None else argv
    stdin = sys.stdin if stdin is None else stdin
    stdout = sys.stdout if stdout is None else stdout
    stderr = sys.stderr if stderr is None else stderr
    if len(argv) > 1:
        stderr.write(USAGE + "\n")
        return 2
    try:
        if argv:
            with open(argv[0], encoding="utf-8", newline="") as handle:
                text = handle.read()
        else:
            text = stdin.read()
        output = report.render(report.parse_rows(text))
    except (OSError, ValueError) as exc:
        stderr.write(f"error: {exc}\n")
        return 2
    stdout.write(output + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
