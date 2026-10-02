#!/usr/bin/env python3
"""prereg.py - write a pre-registration, record its digest, and check the digest later.

Three subcommands, stdlib only, Python 3.9 compatible, no network, no model calls:

  create PATH --title T [--hypothesis H --rule R --bar B --refutation X ...]
      Render templates/prereg.md into PATH. Never overwrites. Writes no hash.
  freeze PATH
      Refuse unless the file is complete, then write PATH.sha256 (never overwrites)
      holding the sha256 of everything above the marker line, and print the digest.
  verify PATH [--expect HEX]
      Recompute that digest and compare it with the sidecar, or with HEX when given.

The hashed region is every byte before the FIRST line that is exactly
    MEASUREMENTS BEGIN BELOW THIS LINE
and is not inside a fenced code block, after two normalisations only: a leading UTF-8
byte-order mark is dropped and CRLF becomes LF. Results appended below the marker, even
another copy of the marker, do not change the digest. Any change above it does.

What a match shows: the text above the marker is byte-for-byte what it was when the digest
was recorded. It does not show the text is true, who wrote it, or when. The sidecar can be
rewritten together with the document, and its timestamp is the local clock. For the digest
to mean anything, record it somewhere you cannot quietly rewrite before you run anything
(a commit, a message to your reviewer), then check with --expect.

Exit codes: 0 digests match / done; 1 digests differ, or the file was refused;
2 could not run (bad arguments, missing or unreadable file, unusable sidecar).

This is a command-line tool, not a hook. It reads no kill-switch variables.
"""
import argparse
import hashlib
import os
import re
import sys
import unicodedata
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

MARKER = "MEASUREMENTS BEGIN BELOW THIS LINE"
MARKER_B = MARKER.encode("ascii")
BOM = b"\xef\xbb\xbf"
MAX_BYTES = 8 * 1024 * 1024
SIDECAR_SUFFIX = ".sha256"

# Required sections: exact heading titles (after dropping a leading "N." and lowercasing).
REQUIRED_SECTIONS = [
    "what is decided",
    "incumbent, measured here",
    "references and confound",
    "decision rule",
    "numeric bars",
    "what would refute the option you want",
    "frozen grid",
    "baseline arm (without)",
    "held-out task author",
    "task where the protocol should lose",
]

# create flag name (dest) -> placeholder name in the template
PLACEHOLDERS = [
    ("title", "title"),
    ("hypothesis", "hypothesis"),
    ("incumbent", "incumbent"),
    ("references", "references"),
    ("rule", "rule"),
    ("bar", "bar"),
    ("refutation", "refutation"),
    ("grid", "grid"),
    ("baseline", "baseline"),
    ("held_out_author", "held_out_author"),
    ("should_lose", "should_lose"),
]

# Words that only stand in for content. A body is empty when, after markup and list numbering
# are set aside, every word left is one of these. The check is shallow on purpose: it catches
# placeholders, it does not judge whether what is written is any good.
PLACEHOLDER_WORDS = {
    "tbd", "tba", "tbc", "tk", "tkk", "todo", "fixme", "wip", "none", "nil", "null", "nothing",
    "unknown", "undecided", "pending", "placeholder", "na", "to", "be", "do", "determined", "decided",
    "announced", "confirmed", "fill", "in", "later", "here",
}
PLACEHOLDER_X_RX = re.compile(r"^x{2,}$")
# Dotted acronyms collapse to one token (T.B.D. -> TBD, N.A. -> NA) before list markers are read,
# so the first letter is not taken for a marker. N/A and "not applicable" collapse to NA too.
DOTTED_RX = re.compile(r"(?<![^\W\d_])[^\W\d_](?:\.[ \t]?[^\W\d_])+\.?(?![^\W\d_])", re.U)
NA_RX = re.compile(r"(?<![^\W_])n[ \t]*/[ \t]*a(?![^\W_])|(?<![^\W_])not[ \t]+applicable(?![^\W_])", re.I | re.U)
WORD_RX = re.compile(r"[^\W_]+", re.U)
TAG_RX = re.compile(r"</?[A-Za-z][^>\n]*>")
ENTITY_RX = re.compile(r"&(?:#[0-9]+|#[xX][0-9a-fA-F]+|[A-Za-z][A-Za-z0-9]*);")
# A list marker at the start of a line: 1.  1)  a)  iv.  (2)  with or without the space after it.
# Only list, quote, emphasis and bracket punctuation may come before it (not "\u2265 3."). A bare
# number marker is an empty list item; a letter marker needs text after it, so "A." stays content.
LEAD_MARKER_RX = re.compile(
    r"^[ \t>*+\-_~|`\"'()\[\]{}]*(?:[0-9]{1,3}[.):]+|(?:[A-Za-z]|[ivxlcIVXLC]{1,6})[.):]+(?=[ \t]*[^\s.):]))")

# A task-list checkbox ("- [x] ...") is markup, so its x is not a word.
CHECKBOX_RX = re.compile(r"^[ \t>*+\-]*(?:[0-9]{1,3}[.)][ \t]+)?\[[ xX]\](?=[ \t]|$)")

PLACEHOLDER_RX = re.compile(r"\{\{[^{}\n]*\}\}")
# CommonMark: the info string of a backtick fence cannot contain a backtick, so a prose line
# such as "```inline``` text" does not open a fence. Tilde fences have no such rule.
FENCE_OPEN_RX = re.compile(r"^ {0,3}(?:(`{3,})(?![^\n]*`)|(~{3,}))")
FENCE_CLOSE_RX = re.compile(r"^ {0,3}(`{3,}|~{3,})[ \t]*$")
HEADING_RX = re.compile(r"^ {0,3}#{1,6}[ \t]+(.*?)[ \t#]*$")


class Refused(Exception):
    """Content or state the tool will not act on. Exit 1."""


class CannotRun(Exception):
    """Input the tool cannot use at all. Exit 2."""


def say(msg: str, stream=None) -> None:
    (stream or sys.stdout).write("dojo-settle: " + msg + "\n")


# ----------------------------------------------------------------------------
# canonical form, region, digest
# ----------------------------------------------------------------------------

def canonical(raw: bytes) -> bytes:
    """Drop a leading UTF-8 BOM and turn CRLF into LF. Nothing else."""
    if raw.startswith(BOM):
        raw = raw[len(BOM):]
    return raw.replace(b"\r\n", b"\n")


def iter_lines(text: str):
    """Yield (offset, line, in_fence) for each line of text split on LF.

    in_fence is True for lines inside a fenced code block and for the fence lines
    themselves. One predicate serves both the split and every count, so a marker
    look-alike can never move the hashed boundary.
    """
    pos = 0
    fence = None  # (char, length)
    for line in text.split("\n"):
        in_fence = fence is not None
        if fence is None:
            m = FENCE_OPEN_RX.match(line)
            if m:
                run = m.group(1) or m.group(2)
                fence = (run[0], len(run))
                in_fence = True
        else:
            m = FENCE_CLOSE_RX.match(line)
            if m and m.group(1)[0] == fence[0] and len(m.group(1)) >= fence[1]:
                fence = None
        yield pos, line, in_fence
        pos += len(line) + 1


def marker_offset(canon: bytes) -> Optional[int]:
    """Byte offset of the first marker line, or None. Bytes map 1:1 through latin-1."""
    text = canon.decode("latin-1")
    for pos, line, in_fence in iter_lines(text):
        if not in_fence and line == MARKER:
            return pos
    return None


def region_of(raw: bytes) -> Optional[bytes]:
    canon = canonical(raw)
    off = marker_offset(canon)
    if off is None:
        return None
    return canon[:off]


def digest_of(region: bytes) -> str:
    return hashlib.sha256(region).hexdigest()


# ----------------------------------------------------------------------------
# file helpers
# ----------------------------------------------------------------------------

def read_file(path: str) -> bytes:
    if os.path.isdir(path):
        raise CannotRun("the path is a directory, not a file")
    try:
        size = os.path.getsize(path)
    except OSError:
        raise CannotRun("cannot read the file (missing or no permission)")
    if size > MAX_BYTES:
        raise CannotRun("file is larger than the %d MB limit" % (MAX_BYTES // (1024 * 1024)))
    try:
        with open(path, "rb") as f:
            return f.read()
    except OSError:
        raise CannotRun("cannot read the file (missing or no permission)")


def template_path() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(os.path.dirname(here), "templates", "prereg.md")


# ----------------------------------------------------------------------------
# content checks used by freeze
# ----------------------------------------------------------------------------

def normalise_title(title: str) -> str:
    t = re.sub(r"^\d+\.\s*", "", title.strip().lower())
    return t.rstrip(":").strip()


def sections(region_text: str) -> Dict[str, List[str]]:
    """Map normalised heading title -> list of section bodies (text between that heading
    and the next heading of any level). Headings inside fenced blocks are ignored."""
    found = {}  # type: Dict[str, List[str]]
    current = None  # type: Optional[str]
    body = []  # type: List[str]

    def close():
        if current is not None:
            found.setdefault(current, []).append("\n".join(body))

    for _pos, line, in_fence in iter_lines(region_text):
        m = None if in_fence else HEADING_RX.match(line)
        if m:
            close()
            current = normalise_title(m.group(1))
            body = []
        elif current is not None:
            body.append(line)
    close()
    return found


def strip_comments(text: str) -> Tuple[str, bool]:
    """Remove HTML comments the way a renderer would see them. Returns (text, unclosed).

    Fenced code blocks and inline code spans are left alone, so a quoted `<!--` hides nothing.
    A comment that is opened and never closed runs to the end of the text (unclosed is True),
    which is also what a renderer does with the rest of the page.
    """
    out = []  # type: List[str]
    in_comment = False
    fence = None  # type: Optional[Tuple[str, int]]
    for line in text.split("\n"):
        i = 0
        kept = []  # type: List[str]
        if in_comment:
            j = line.find("-->")
            if j < 0:
                out.append("")
                continue
            in_comment = False
            i = j + 3
        elif fence is not None:
            m = FENCE_CLOSE_RX.match(line)
            if m and m.group(1)[0] == fence[0] and len(m.group(1)) >= fence[1]:
                fence = None
            out.append(line)
            continue
        else:
            m = FENCE_OPEN_RX.match(line)
            if m:
                run = m.group(1) or m.group(2)
                fence = (run[0], len(run))
                out.append(line)
                continue
        n = len(line)
        while i < n:
            c = line[i]
            if c == "`":
                k = i
                while k < n and line[k] == "`":
                    k += 1
                run = line[i:k]
                close = re.compile(r"(?<!`)" + re.escape(run) + r"(?!`)").search(line, k)
                end = close.end() if close else k
                kept.append(line[i:end])
                i = end
            elif line.startswith("<!--", i):
                j = line.find("-->", i + 2)
                if j < 0:
                    in_comment = True
                    break
                i = j + 3
            else:
                kept.append(c)
                i += 1
        out.append("".join(kept))
    return "\n".join(out), in_comment


def content_words(body: str) -> List[str]:
    """The words of a section body once comments, markup, entities, invisible characters and
    leading list numbering are set aside."""
    text, _unclosed = strip_comments(body)
    text = unicodedata.normalize("NFKC", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Cf")
    text = ENTITY_RX.sub(" ", TAG_RX.sub(" ", text))
    text = NA_RX.sub("na", DOTTED_RX.sub(lambda m: re.sub(r"[. \t]", "", m.group(0)), text))
    words = []  # type: List[str]
    for ln in text.splitlines():
        ln = CHECKBOX_RX.sub("", ln, count=1)
        ln = LEAD_MARKER_RX.sub("", ln, count=1)
        words.extend(w.lower() for w in WORD_RX.findall(ln))
    return words


def is_empty_body(body: str) -> bool:
    """True when nothing is written, or only placeholder words are: TBD, TODO, TK, XXX, n/a,
    none, '...', '??', with or without numbering, brackets, quotes, emphasis, a trailing '?'
    or a table pipe. Shallow by design: it never judges whether real-looking text is any good."""
    seen_placeholder = False
    for w in content_words(body):
        if w in PLACEHOLDER_WORDS or PLACEHOLDER_X_RX.match(w):
            seen_placeholder = True
        elif not w.isdigit():
            return False
    # Bare digits next to a placeholder (TBD 2, 1 TBD) are numbering; digits alone are content.
    words_present = bool(content_words(body))
    return seen_placeholder or not words_present


def unfilled_placeholders(text: str) -> bool:
    """True when a {{placeholder}} sits in prose above the marker. HTML comments and
    fenced code blocks may quote a template without being refused."""
    stripped, _unclosed = strip_comments(text)
    outside = "\n".join(line for _pos, line, in_fence in iter_lines(stripped) if not in_fence)
    return bool(PLACEHOLDER_RX.search(outside))


def check_complete(region: bytes) -> None:
    text = region.decode("utf-8", "replace")
    # HTML comments are not prose: a heading or body that only exists inside one does not count.
    stripped, unclosed = strip_comments(text)
    if unclosed:
        raise Refused("an HTML comment is opened above the marker and never closed, so everything after it is hidden; close it with --> or remove it")
    if unfilled_placeholders(text):
        raise Refused("an unfilled {{placeholder}} is still above the marker; fill or delete it")
    found = sections(stripped)
    for key in REQUIRED_SECTIONS:
        bodies = found.get(key)
        if not bodies:
            raise Refused("the section '%s' is missing" % key)
        for b in bodies:
            if is_empty_body(b):
                raise Refused("the section '%s' is empty, or only holds placeholders such as none, n/a, TBD, TODO, TK, XXX or ..." % key)


# ----------------------------------------------------------------------------
# subcommands
# ----------------------------------------------------------------------------

def cmd_create(args) -> int:
    path = args.path
    parent = os.path.dirname(os.path.abspath(path))
    if not os.path.isdir(parent):
        raise CannotRun("the parent directory does not exist")
    try:
        with open(template_path(), "r", encoding="utf-8", newline="") as f:
            template = f.read().replace("\r\n", "\n")
    except OSError:
        raise CannotRun("cannot read templates/prereg.md next to this script")
    values = {}
    for dest, name in PLACEHOLDERS:
        v = getattr(args, dest)
        if v is None:
            continue
        v = v.replace("\r\n", "\n").strip("\n")
        for _pos, line, in_fence in iter_lines(v):
            if line == MARKER:
                raise Refused("a value contains the marker line; remove it")
        values[name] = v
    if not values.get("title", "").strip():
        raise Refused("--title is required and cannot be blank")

    def sub(m):
        name = m.group(1).strip()
        return values.get(name, m.group(0))

    rendered = re.sub(r"\{\{([^{}\n]*)\}\}", sub, template)
    try:
        with open(path, "x", encoding="utf-8", newline="\n") as f:
            f.write(rendered)
    except FileExistsError:
        raise Refused("the file already exists; create never overwrites (write a v2 file and cite v1's digest)")
    except OSError:
        raise CannotRun("cannot write the file")
    left = len(PLACEHOLDER_RX.findall(strip_comments(rendered)[0]))
    say("created %s. %d placeholder(s) still to fill before freeze will accept it." % (path, left))
    return 0


def cmd_freeze(args) -> int:
    path = args.path
    raw = read_file(path)
    sidecar = path + SIDECAR_SUFFIX
    if os.path.lexists(sidecar):
        raise Refused("a digest is already recorded for this file; freeze never overwrites (write a v2 file and cite v1's digest)")
    region = region_of(raw)
    if region is None:
        raise Refused("no marker line found outside a code block; add a line that is exactly: " + MARKER)
    check_complete(region)
    digest = digest_of(region)
    nbytes = len(region)
    nlines = region.count(b"\n")
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    body = (
        "dojo-settle prereg digest\n"
        "sha256: %s\n"
        "bytes: %d\n"
        "lines: %d\n"
        "file: %s\n"
        "recorded_at_utc_local_clock: %s\n"
        "region: bytes before the first marker line; BOM dropped, CRLF as LF\n"
        "note: this sidecar can be rewritten along with the document; record the sha256 elsewhere\n"
    ) % (digest, nbytes, nlines, os.path.basename(path), stamp)
    try:
        with open(sidecar, "x", encoding="utf-8", newline="\n") as f:
            f.write(body)
    except FileExistsError:
        raise Refused("a digest is already recorded for this file; freeze never overwrites")
    except OSError:
        raise CannotRun("cannot write the digest file")
    say("recorded sha256 %s (%d bytes, %d lines above the marker)." % (digest, nbytes, nlines))
    say("Before you run anything, copy that digest somewhere you can't quietly rewrite: a commit message, or a note to your reviewer.")
    say("Later: prereg.py verify %s --expect <that digest>" % path)
    return 0


HEX64_RX = re.compile(r"^[0-9a-fA-F]{64}$")


def read_sidecar(path: str) -> str:
    sidecar = path + SIDECAR_SUFFIX
    if not os.path.exists(sidecar):
        raise CannotRun("no digest file next to it and no --expect given")
    raw = read_file(sidecar)
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise CannotRun("the digest file is not text")
    values = []
    for line in text.splitlines():
        if line.startswith("sha256:"):
            values.append(line.split(":", 1)[1].strip())
    if len(values) != 1:
        raise CannotRun("the digest file does not hold exactly one sha256 line")
    if not HEX64_RX.match(values[0]):
        raise CannotRun("the digest in the digest file is not 64 hex characters")
    return values[0].lower()


def cmd_verify(args) -> int:
    path = args.path
    raw = read_file(path)
    if args.expect is not None:
        if not HEX64_RX.match(args.expect.strip()):
            raise CannotRun("--expect must be 64 hex characters")
        recorded = args.expect.strip().lower()
        source = "the digest you passed with --expect"
    else:
        recorded = read_sidecar(path)
        source = "the recorded digest in the digest file"
    region = region_of(raw)
    if region is None:
        say("digest differs: no marker line found outside a code block, so the region can't be recomputed.", sys.stdout)
        return 1
    digest = digest_of(region)
    if digest == recorded:
        say("digest matches %s (sha256 %s). This shows the text above the marker is unchanged since that digest was recorded; it does not show the text is true." % (source, digest))
        return 0
    say("digest differs from %s. Recomputed sha256 %s; recorded %s. The text above the marker is not what it was." % (source, digest, recorded))
    return 1


# ----------------------------------------------------------------------------
# entry point
# ----------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="prereg.py",
        description="Write a pre-registration, record its digest, check the digest later.",
        epilog="Exit codes: 0 match/done, 1 differs or refused, 2 could not run.",
    )
    sub = p.add_subparsers(dest="cmd")
    sub.required = True

    c = sub.add_parser("create", help="render the template into a new file (never overwrites)")
    c.add_argument("path")
    c.add_argument("--title", required=True)
    for dest, _name in PLACEHOLDERS:
        if dest == "title":
            continue
        c.add_argument("--" + dest.replace("_", "-"), dest=dest, default=None)
    c.set_defaults(fn=cmd_create)

    f = sub.add_parser("freeze", help="record the digest of everything above the marker")
    f.add_argument("path")
    f.set_defaults(fn=cmd_freeze)

    v = sub.add_parser("verify", help="recompute the digest and compare")
    v.add_argument("path")
    v.add_argument("--expect", default=None, help="64-hex digest recorded outside the file")
    v.set_defaults(fn=cmd_verify)
    return p


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else 2
        return code
    try:
        return args.fn(args)
    except Refused as e:
        say("refused: %s." % e, sys.stderr)
        return 1
    except CannotRun as e:
        say("could not run: %s." % e, sys.stderr)
        return 2
    except Exception as e:  # never a traceback, never file text
        say("could not run: unexpected %s." % type(e).__name__, sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
