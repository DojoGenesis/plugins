#!/usr/bin/env python3
"""dojo-protocol SessionStart hook.

Injects PROTOCOL.md as additionalContext at session start. A readable ./DOJO.md
in the session's working directory replaces it. Kill switches: DOJO_OFF=1 and
DOJO_PROTOCOL_OFF=1 (only the exact value 1 turns anything off).

Fails open: any problem means exit 0 with no output. Never writes anything,
never touches the network, never runs a subprocess. Python 3.9, stdlib only.
"""
import json
import os
import stat
import sys

# Cap on the injected text. Very large hook context is moved to disk and the
# model sees only a preview, so keep the whole injection small. The cap is
# counted in UTF-16 code units because the engine measures JavaScript string
# length, which counts an emoji as two.
CAP_UNITS = 8000
MAX_DOJO_BYTES = 65536
MAX_STDIN_BYTES = 1048576

HEADER = "Project protocol from ./DOJO.md (dojo-protocol plugin):\n\n"
CUT_NOTE = "\n\n[./DOJO.md was cut here at the size cap. Read the file for the rest.]"

REPLACED_MSG = (
    "dojo-protocol: injected ./DOJO.md instead of the built-in protocol — "
    "this project's rules replace the ten defaults. "
    "Rename DOJO.md to use the defaults, or set DOJO_PROTOCOL_OFF=1 to inject nothing."
)
CUT_MSG = (
    "dojo-protocol: ./DOJO.md was cut at {cap:,} characters — "
    "the model only sees the first part. Shorten DOJO.md to fit under the cap."
)


def units(text):
    """Length as JavaScript counts it (UTF-16 code units)."""
    return len(text.encode("utf-16-le", "surrogatepass")) // 2


def head_by_units(text, budget):
    """Longest prefix of text whose UTF-16 length is <= budget."""
    used = 0
    for i, ch in enumerate(text):
        used += 2 if ord(ch) > 0xFFFF else 1
        if used > budget:
            return text[:i]
    return text


def switched_off():
    for name in ("DOJO_OFF", "DOJO_PROTOCOL_OFF"):
        if os.environ.get(name, "").strip() == "1":
            return True
    return False


def read_payload():
    raw = sys.stdin.buffer.read(MAX_STDIN_BYTES)
    data = json.loads(raw.decode("utf-8"))
    return data if isinstance(data, dict) else None


def usable_root(value):
    if isinstance(value, str) and value and os.path.isabs(value) and os.path.isdir(value):
        return value
    return None


def project_root(payload):
    # The payload's cwd wins; the env var is only a fallback for a missing or
    # unusable cwd. No walking up to a git root.
    return usable_root(payload.get("cwd")) or usable_root(os.environ.get("CLAUDE_PROJECT_DIR"))


def read_dojo_md(root):
    """Return (text, was_truncated) for ./DOJO.md, or None when it is unusable.

    Unusable: absent (the name must be exactly DOJO.md, in any filesystem),
    not a regular file (directory, FIFO, device), resolves
    outside the project root (a symlink to somewhere else), unreadable, empty,
    or whitespace only. A symlink that stays inside the root is accepted.
    """
    real_root = os.path.realpath(root)
    # Exact name only. On a case-insensitive filesystem open() would also find
    # dojo.md, so the directory listing decides.
    if "DOJO.md" not in os.listdir(real_root):
        return None
    real_path = os.path.realpath(os.path.join(real_root, "DOJO.md"))
    if os.path.commonpath([real_root, real_path]) != real_root or real_path == real_root:
        return None
    # O_NONBLOCK keeps open() from hanging on a FIFO swapped in after the check.
    fd = os.open(real_path, os.O_RDONLY | getattr(os, "O_NONBLOCK", 0))
    try:
        # Defense in depth: realpath plus the root check already keep devices
        # outside the project out, and a directory fails on read. This check
        # also covers a file swapped for a non-regular one after the checks.
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            return None
        chunks = []
        remaining = MAX_DOJO_BYTES + 1
        while remaining > 0:
            chunk = os.read(fd, min(remaining, 16384))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
    finally:
        os.close(fd)
    data = b"".join(chunks)
    cut = len(data) > MAX_DOJO_BYTES
    text = data[:MAX_DOJO_BYTES].decode("utf-8", "replace").replace("\x00", "").strip()
    if not text:
        return None
    return text, cut


def bounded_dojo_context(text, byte_cut):
    budget = CAP_UNITS - units(HEADER)
    if not byte_cut and units(text) <= budget:
        return HEADER + text, False
    body = head_by_units(text, budget - units(CUT_NOTE)).rstrip()
    return HEADER + body + CUT_NOTE, True


def protocol_text():
    root = os.environ.get("CLAUDE_PLUGIN_ROOT", "").strip()
    if not root:
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(root, "PROTOCOL.md"), "rb") as handle:
        text = handle.read(MAX_STDIN_BYTES).decode("utf-8", "replace")
    return text if text.strip() else None


def build_output(payload):
    root = project_root(payload)
    if root:
        try:
            found = read_dojo_md(root)
        except (OSError, ValueError):
            found = None
        if found:
            context, was_cut = bounded_dojo_context(found[0], found[1])
            output = {
                "hookSpecificOutput": {
                    "hookEventName": "SessionStart",
                    "additionalContext": context,
                },
            }
            # The context is injected on every source. The notice to the person
            # is shown once, at a fresh start, not again on resume, clear or compact.
            if payload.get("source") in (None, "startup"):
                message = REPLACED_MSG
                if was_cut:
                    message += "\n" + CUT_MSG.format(cap=CAP_UNITS)
                output = dict(systemMessage=message, **output)
            return output
    text = protocol_text()
    if text is None:
        return None
    return {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": text,
        }
    }


def main():
    try:
        if switched_off():
            return
        payload = read_payload()
        if payload is None:
            return
        output = build_output(payload)
        if output is None:
            return
        # ensure_ascii (the default) keeps stdout pure ASCII on any locale.
        sys.stdout.write(json.dumps(output) + "\n")
        sys.stdout.flush()
    except Exception:
        return


if __name__ == "__main__":
    main()
    sys.exit(0)
