#!/usr/bin/env python3
"""suite_denylist.py: scan paths for denylisted terms without ever printing them.

Usage:
  suite_denylist.py [PATH ...] [--allow-missing] [--denylist FILE] [--internal-refs FILE]

Two local-only lists are read. List 1 is, in order: --denylist, $DOJO_DENYLIST, then
~/.config/dojo/stealth-denylist.txt. List 2 is, in order: --internal-refs,
$DOJO_INTERNAL_REFS, then ~/.config/dojo/internal-refs.txt. Format, one entry per line:
  i:<text>    case-insensitive substring
  w:<text>    case-sensitive whole word (not inside a longer word or hyphenated name)
  r:<regex>   Python regular expression, searched line by line (case-sensitive unless
              the pattern sets its own flags)
  #...        comment; blank lines are ignored
A line with any other prefix, an empty or whitespace-only term, a regex that does not
compile, or a regex that matches the empty string is skipped and only counted.

Output is `path:line: <REDACTED term #n>`, where n is the 1-based position among the
parsed terms of list 1 (list 2 prints `#2.n`). A term that appears in a file or
directory name is redacted in the printed path as well. A term is never printed,
including on error paths (an exception prints only its type name).

Before scanning, a positive control runs once per list: it writes a canary into a
temporary directory, scans that directory through the same walk, read and match code as
the real scan (using only that list's terms), and requires a hit. The canary is built
from the first `i:` entry of the list, else the first `w:` entry, else a string
synthesized from the first `r:` entry. If any control fails, or a list is missing,
empty, or has no usable entry, the run exits 2 and says so. `--allow-missing` turns only
a missing file into "SKIPPED": with both lists missing the run exits 0, with one missing
it scans with the other.

Skipped files (binary, over 4 MB, unreadable) are counted on a summary line; a count is
printed whenever it is not zero. Symlinks are never followed, but each one is scanned by
its own name and by its target string (the text git stores for it); a hit in the target
prints `(in the link target)`, and the number of links checked is printed on a summary line. UTF-16 files with a byte order
mark are decoded and scanned.

Exit codes: 0 clean, 1 hits, 2 could not run.
"""
from __future__ import annotations

import os
import re
import shutil
import sys
import tempfile
import warnings

DEFAULT_LIST = "~/.config/dojo/stealth-denylist.txt"
DEFAULT_REFS = "~/.config/dojo/internal-refs.txt"
MAX_BYTES = 4_000_000
SKIP_DIRS = (".git", "node_modules", "__pycache__")
REDACTED = "<REDACTED>"


class Terms(object):
    """Parsed terms of one list, or of several lists merged for the real scan."""

    def __init__(self, list_no=1):
        self.list_no = list_no
        self.items = []  # (tag, kind, term, compiled regex); tag is "n" or "L.n"
        self.malformed = 0

    def tag(self, n):
        return str(n) if self.list_no == 1 else "%d.%d" % (self.list_no, n)

    def redact(self, text):
        for _t, _k, _term, rx in self.items:
            text = rx.sub(REDACTED, text)
        return text

    def merge(self, other):
        self.items.extend(other.items)
        self.malformed += other.malformed


def parse_terms(raw, list_no=1):
    """Parse list bytes into Terms, the same way tools/denyscan.py does, plus BOM and
    CR stripping and rejection of empty, whitespace-only and match-everything terms."""
    out = Terms(list_no)
    text = raw.decode("utf-8", "replace")
    if text.startswith("﻿"):
        text = text[1:]
    for line in text.split("\n"):
        line = line.rstrip("\r")
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        kind, _sep, term = line.partition(":")
        if kind not in ("i", "w", "r") or not term.strip():
            out.malformed += 1
            continue
        try:
            if kind == "i":
                rx = re.compile(re.escape(term), re.I)
            elif kind == "w":
                rx = re.compile(r"(?<![\w-])" + re.escape(term) + r"(?![\w-])")
            else:
                rx = re.compile(term)
                if rx.search(""):
                    out.malformed += 1
                    continue
        except (re.error, RecursionError, OverflowError):
            out.malformed += 1
            continue
        out.items.append((out.tag(len(out.items) + 1), kind, term, rx))
    return out


def list_path(cli_value):
    return cli_value or os.environ.get("DOJO_DENYLIST") or os.path.expanduser(DEFAULT_LIST)


def refs_path(cli_value):
    return cli_value or os.environ.get("DOJO_INTERNAL_REFS") or os.path.expanduser(DEFAULT_REFS)


def match_line(line, terms):
    """Tags of the terms matching one line."""
    return [tag for tag, _k, _t, rx in terms.items if rx.search(line)]


def match_name(name, terms):
    return [tag for tag, _k, _t, rx in terms.items if rx.search(name)]


class Stats(object):
    def __init__(self):
        self.binary = 0
        self.oversize = 0
        self.unreadable = 0
        self.symlink = 0
        self.files = 0

    def skipped(self):
        return self.binary + self.oversize + self.unreadable


def scan_file(path, terms, stats):
    """Hits in one file's contents as (line, term tag)."""
    try:
        with open(path, "rb") as fh:
            data = fh.read(MAX_BYTES + 1)
    except OSError:
        stats.unreadable += 1
        return []
    if len(data) > MAX_BYTES:
        stats.oversize += 1
        return []
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        text = data.decode("utf-16", "replace")
    elif b"\0" in data[:8192]:
        stats.binary += 1
        return []
    else:
        text = data.decode("utf-8", "replace")
    stats.files += 1
    hits = []
    for ln, line in enumerate(text.splitlines(), 1):
        for tag in match_line(line, terms):
            hits.append((ln, tag))
    return hits


def scan_link(path, name, terms, stats):
    """A symlink is checked by its own name and by its target string, never followed. Git
    stores the target string as the link's content, so that string is what would be committed."""
    stats.symlink += 1
    for tag in match_name(name, terms):
        yield path, 0, tag
    try:
        target = os.readlink(path)
    except OSError:
        stats.unreadable += 1
        return
    for line in target.splitlines() or [target]:
        for tag in match_line(line, terms):
            yield path, -1, tag


def scan_tree(root, terms, stats):
    """Yield (path, line, term tag); line 0 means the hit is in the file or directory name,
    line -1 means it is in a symlink's target string."""
    root_is_dir = os.path.isdir(root)
    if os.path.islink(root):
        for hit in scan_link(root, os.path.basename(os.path.normpath(root)), terms, stats):
            yield hit
        if not root_is_dir:
            return
    elif os.path.isfile(root):
        for tag in match_name(os.path.basename(root), terms):
            yield root, 0, tag
        for ln, tag in scan_file(root, terms, stats):
            yield root, ln, tag
        return
    for dirpath, dirs, files in os.walk(root, followlinks=False):
        keep = []
        for d in sorted(dirs):
            full = os.path.join(dirpath, d)
            if os.path.islink(full):
                for hit in scan_link(full, d, terms, stats):
                    yield hit
                continue
            if d in SKIP_DIRS:
                continue
            for tag in match_name(d, terms):
                yield full, 0, tag
            keep.append(d)
        dirs[:] = keep
        for f in sorted(files):
            full = os.path.join(dirpath, f)
            if os.path.islink(full):
                for hit in scan_link(full, f, terms, stats):
                    yield hit
                continue
            for tag in match_name(f, terms):
                yield full, 0, tag
            for ln, tag in scan_file(full, terms, stats):
                yield full, ln, tag


# ----------------------------------------------------------------------------
# Canary synthesis for the positive control
# ----------------------------------------------------------------------------

def _regex_parser():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            import re._parser as sp  # Python 3.11+
            return sp
        except ImportError:
            import sre_parse as sp
            return sp


def _gen_from(parsed, depth=0):
    """A string that the parsed regex should match. Raises ValueError when it cannot say."""
    if depth > 12:
        raise ValueError("too deep")
    out = []
    for op, av in parsed:
        name = str(op)
        if name == "LITERAL":
            out.append(chr(av))
        elif name == "NOT_LITERAL":
            out.append("\x01" if av != 1 else "\x02")
        elif name == "ANY":
            out.append("a")
        elif name == "IN":
            out.append(_gen_set(av))
        elif name in ("MAX_REPEAT", "MIN_REPEAT", "POSSESSIVE_REPEAT"):
            lo, hi, sub = av
            n = max(lo, 1)
            if isinstance(hi, int) and hi < n:
                n = hi
            out.append(_gen_from(sub, depth + 1) * n)
        elif name in ("SUBPATTERN", "ATOMIC_GROUP"):
            out.append(_gen_from(av[-1], depth + 1))
        elif name == "BRANCH":
            out.append(_gen_from(av[1][0], depth + 1))
        elif name == "CATEGORY":
            out.append(_gen_category(str(av)))
        elif name in ("AT", "ASSERT", "ASSERT_NOT"):
            continue
        else:
            raise ValueError("unsupported")
    return "".join(out)


def _gen_category(cat):
    if "NOT" in cat:
        return "-" if "WORD" in cat else "a"
    if "DIGIT" in cat:
        return "1"
    if "SPACE" in cat:
        return " "
    return "a"


def _gen_set(items):
    if any(str(o) == "NEGATE" for o, _a in items):
        chars = [chr(a) for o, a in items if str(o) == "LITERAL"]
        for cand in "\x01\x02\x03":
            if cand not in chars:
                return cand
        raise ValueError("unsupported")
    for op, av in items:
        name = str(op)
        if name == "LITERAL":
            return chr(av)
        if name == "RANGE":
            return chr(av[0])
        if name == "CATEGORY":
            return _gen_category(str(av))
    raise ValueError("unsupported")


def synth_from_regex(pattern):
    """A matching sample for a regex, or None when it cannot be synthesized."""
    try:
        sp = _regex_parser()
        sample = _gen_from(sp.parse(pattern))
        if sample and re.compile(pattern).search(sample):
            return sample
        padded = "x " + sample + " y"
        if sample and re.compile(pattern).search(padded):
            return sample
    except (ValueError, re.error, RecursionError, OverflowError, ImportError, AttributeError, TypeError):
        pass
    return None


def canary_for(terms):
    """The canary text for one list, or None when the list gives no way to build one."""
    for want in ("i", "w"):
        for _tag, kind, term, _rx in terms.items:
            if kind == want:
                return term
    for _tag, kind, term, _rx in terms.items:
        if kind == "r":
            sample = synth_from_regex(term)
            if sample is not None:
                return sample
    return None


def run_control(terms):
    """True when a canary built from this list is found by the real scan path."""
    canary = canary_for(terms)
    if canary is None:
        return False
    tmp = tempfile.mkdtemp(prefix="suite-denylist-control-")
    try:
        with open(os.path.join(tmp, "canary.txt"), "w", encoding="utf-8") as fh:
            fh.write(canary + "\nx " + canary + " y\n")
        stats = Stats()
        # count content hits only: a name hit would let a blind content scan pass the control
        return any(ln > 0 for _p, ln, _t in scan_tree(tmp, terms, stats))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _out(msg):
    sys.stdout.write(msg + "\n")
    sys.stdout.flush()


def parse_args(argv):
    paths, allow_missing, deny, refs, i = [], False, None, None, 0
    while i < len(argv):
        a = argv[i]
        if a in ("-h", "--help"):
            sys.stdout.write(__doc__)
            return None
        if a == "--allow-missing":
            allow_missing = True
        elif a == "--denylist":
            i += 1
            if i >= len(argv):
                raise ValueError("--denylist needs a file")
            deny = argv[i]
        elif a.startswith("--denylist="):
            deny = a.split("=", 1)[1]
        elif a == "--internal-refs":
            i += 1
            if i >= len(argv):
                raise ValueError("--internal-refs needs a file")
            refs = argv[i]
        elif a.startswith("--internal-refs="):
            refs = a.split("=", 1)[1]
        elif a.startswith("-") and a != "-":
            raise ValueError("unknown option")
        else:
            paths.append(a)
        i += 1
    return paths, allow_missing, deny, refs


def _load_list(path, list_no):
    """(Terms, state) where state is ok, missing or unreadable."""
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
    except FileNotFoundError:
        return None, "missing"
    except OSError:
        return None, "unreadable"
    return parse_terms(raw, list_no), "ok"


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    all_terms = Terms()
    try:
        parsed = parse_args(argv)
        if parsed is None:
            return 0
        paths, allow_missing, deny, refs = parsed
        specs = [(1, list_path(deny), "denylist"), (2, refs_path(refs), "internal-refs list")]
        lists = []
        skipped_lists = []
        for list_no, path, label in specs:
            terms, state = _load_list(path, list_no)
            if state == "missing":
                if allow_missing:
                    skipped_lists.append(label)
                    continue
                _out("suite_denylist: %s missing; could not run" % label)
                return 2
            if state == "unreadable":
                _out("suite_denylist: %s unreadable; could not run" % label)
                return 2
            if not terms.items:
                _out("suite_denylist: %s has no usable entries; could not run" % label)
                return 2
            if canary_for(terms) is None:
                _out("suite_denylist: %s has no entry a positive control can be built from; could not run" % label)
                return 2
            lists.append((label, terms))
        if not lists:
            _out("suite_denylist: SKIPPED (no denylist)")
            return 0
        for label, terms in lists:
            if not run_control(terms):
                _out("suite_denylist: positive control failed for the %s; could not run" % label)
                return 2
        for label in skipped_lists:
            _out("suite_denylist: SKIPPED the %s (missing)" % label)
        for _label, terms in lists:
            all_terms.merge(terms)
        targets = paths or ["."]
        for t in targets:
            if not os.path.lexists(t):
                _out("suite_denylist: no such path: %s; could not run" % all_terms.redact(t))
                return 2
        stats = Stats()
        hits = 0
        for t in targets:
            for p, ln, tag in scan_tree(t, all_terms, stats):
                hits += 1
                shown = all_terms.redact(p)
                if ln > 0:
                    _out("%s:%d: <REDACTED term #%s>" % (shown, ln, tag))
                elif ln < 0:
                    _out("%s: <REDACTED term #%s> (in the link target)" % (shown, tag))
                else:
                    _out("%s: <REDACTED term #%s> (in the name)" % (shown, tag))
        if stats.skipped():
            _out("suite_denylist: skipped %d file(s) (binary %d, over 4 MB %d, unreadable %d)"
                 % (stats.skipped(), stats.binary, stats.oversize, stats.unreadable))
        if stats.symlink:
            _out("suite_denylist: checked %d symlink(s) by name and target string; link contents are not followed" % stats.symlink)
        if all_terms.malformed:
            _out("suite_denylist: ignored %d malformed list line(s)" % all_terms.malformed)
        _out("suite_denylist: %d hit(s); control ok (%d list%s)" % (hits, len(lists), "" if len(lists) == 1 else "s"))
        return 1 if hits else 0
    except Exception as e:  # never print the message: it could carry a path or a term
        _out("suite_denylist: error: %s; could not run" % type(e).__name__)
        return 2


if __name__ == "__main__":
    sys.exit(main())
