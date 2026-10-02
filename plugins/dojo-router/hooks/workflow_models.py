#!/usr/bin/env python3
"""dojo-router: PreToolUse hook for the Workflow tool.

Reads the workflow script (the file named by scriptPath when given, since the tool gives it
precedence, else the inline script) and checks that every agent() call sets a model in its
options object. Uses a small JavaScript tokenizer so agent( inside comments, strings and
plain template text is ignored, while code inside template ${...} is not.

The check is static and says so: a call whose options are not an object literal (a variable,
a ternary, a spread) is reported as unverifiable, never counted as pinned. Fails open on
anything unexpected: exit 0, no output.
"""
import hashlib
import os
import re
import stat
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import router_common as rc  # noqa: E402

MAX_SCRIPT_BYTES = 512 * 1024
MAX_LISTED = 20
# A regex literal that has not closed after this many characters is read as a division sign, and the
# whole script gets a fixed budget for such look-aheads, so hostile input cannot make the scan quadratic.
MAX_REGEX_LITERAL = 400
REGEX_SCAN_BUDGET = 100000

# Tokens: (kind, value, line). kinds: id num str tmpl regex punct
_ID_START = re.compile(r"[A-Za-z_$]")
_ID_REST = re.compile(r"[A-Za-z0-9_$]*")
_NUM = re.compile(r"[0-9][A-Za-z0-9_.]*")

_REGEX_AFTER_PUNCT = set("(,=:[!&|?{};+-*%<>~^")
_REGEX_AFTER_WORD = {
    "return", "typeof", "case", "do", "else", "in", "of", "void", "delete",
    "throw", "new", "await", "yield", "instanceof",
}


class Tokens(object):
    def __init__(self):
        self.items = []
        self.balanced = True


def tokenize(src):
    """Turn JavaScript source into a flat token list. Never raises on odd input; sets balanced=False instead.

    Template literals are expanded: each ${ expr } becomes ( expr ) so a call inside it is still seen.
    """
    out = Tokens()
    items = out.items
    n = len(src)
    i = 0
    line = 1
    stack = []  # 'b' for a code brace, 't' for a template expression brace
    budget = [REGEX_SCAN_BUDGET]

    def prev_kind():
        return items[-1] if items else None

    def regex_allowed():
        last = prev_kind()
        if last is None:
            return True
        kind, value = last[0], last[1]
        if kind == "punct":
            return value in _REGEX_AFTER_PUNCT or value == "}"
        if kind == "id":
            return value in _REGEX_AFTER_WORD
        return False  # after a number, string, template, regex: division

    def scan_template(pos, ln):
        """Scan template text from pos until the closing backtick or a ${ ; returns (pos, ln, entered_expr)."""
        while pos < n:
            ch = src[pos]
            if ch == "\\":
                if pos + 1 < n and src[pos + 1] == "\n":
                    ln += 1
                pos += 2
                continue
            if ch == "\n":
                ln += 1
            if ch == "`":
                return pos + 1, ln, False
            if ch == "$" and pos + 1 < n and src[pos + 1] == "{":
                return pos + 2, ln, True
            pos += 1
        out.balanced = False
        return n, ln, False

    while i < n:
        ch = src[i]
        if ch == "\n":
            line += 1
            i += 1
            continue
        if ch in " \t\r\f\v":
            i += 1
            continue
        if ch == "/" and i + 1 < n and src[i + 1] == "/":
            while i < n and src[i] != "\n":
                i += 1
            continue
        if ch == "/" and i + 1 < n and src[i + 1] == "*":
            end = src.find("*/", i + 2)
            if end < 0:
                out.balanced = False
                break
            line += src.count("\n", i, end)
            i = end + 2
            continue
        if ch in "'\"":
            quote = ch
            j = i + 1
            buf = []
            closed = False
            while j < n:
                c = src[j]
                if c == "\\" and j + 1 < n:
                    if src[j + 1] == "\n":
                        line += 1
                    buf.append(src[j + 1])
                    j += 2
                    continue
                if c == quote:
                    closed = True
                    j += 1
                    break
                if c == "\n":
                    break  # a string cannot span a line
                buf.append(c)
                j += 1
            if not closed:
                out.balanced = False
            items.append(("str", "".join(buf), line))
            i = j
            continue
        if ch == "`":
            items.append(("tmpl", "", line))
            i, line, entered = scan_template(i + 1, line)
            if entered:
                items.append(("punct", "(", line))
                stack.append("t")
            continue
        if ch == "/":
            if regex_allowed():
                if budget[0] <= 0:
                    out.balanced = False  # out of look-ahead budget: read the rest as division
                else:
                    j = i + 1
                    in_class = False
                    ok = False
                    limit = min(n, i + MAX_REGEX_LITERAL)
                    while j < limit:
                        c = src[j]
                        if c == "\n":
                            break
                        if c == "\\":
                            j += 2
                            continue
                        if c == "[":
                            in_class = True
                        elif c == "]":
                            in_class = False
                        elif c == "/" and not in_class:
                            ok = True
                            break
                        j += 1
                    budget[0] -= max(j - i, 1)
                    if ok:
                        j += 1
                        while j < n and (src[j].isalpha()):
                            j += 1
                        items.append(("regex", "", line))
                        i = j
                        continue
            items.append(("punct", "/", line))
            i += 1
            continue
        if _ID_START.match(ch):
            m = _ID_REST.match(src, i + 1)
            end = m.end()
            items.append(("id", src[i:end], line))
            i = end
            continue
        if "0" <= ch <= "9":
            m = _NUM.match(src, i)
            items.append(("num", m.group(0), line))
            i = m.end()
            continue
        if ch == "." and src.startswith("...", i):
            items.append(("punct", "...", line))
            i += 3
            continue
        if ch == "?" and src.startswith("?.", i) and not (i + 2 < n and src[i + 2].isdigit()):
            items.append(("punct", "?.", line))
            i += 2
            continue
        if ch == "{":
            stack.append("b")
            items.append(("punct", "{", line))
            i += 1
            continue
        if ch == "}":
            if stack and stack[-1] == "t":
                stack.pop()
                items.append(("punct", ")", line))
                i, line, entered = scan_template(i + 1, line)
                if entered:
                    items.append(("punct", "(", line))
                    stack.append("t")
                continue
            if stack:
                stack.pop()
            items.append(("punct", "}", line))
            i += 1
            continue
        items.append(("punct", ch, line))
        i += 1

    if stack:
        out.balanced = False
    return out


_OPEN = {"(": ")", "[": "]", "{": "}"}
_CLOSE = set(_OPEN.values())

# An identifier before `agent` that declares or shadows the name: not a use of the workflow function.
_DECLARATIONS = {"function", "const", "let", "var", "class"}
_INDIRECT_METHODS = {"call", "apply", "bind"}
# `agent` written after one of these punctuation marks is a value being passed or stored.
_VALUE_PREV = {"=", ",", "(", "?", ":", "[", "|", "&", "!", "{"}


def _bracket_map(items):
    """One pass over the tokens: pair each opening bracket with its close, once, in linear time.

    Returns (match, parent). match maps an opening index to (close index, [top-level comma indexes]);
    an opener that never closes properly has no entry. parent[k] is the index of the innermost opener
    around token k, or -1. A closer that does not match the innermost opener leaves every opener
    around it unmatched, which is what a bracket-by-bracket scan would have reported.
    """
    match = {}
    parent = [-1] * len(items)
    stack = []  # (open index, expected closer, commas)
    for k, tok in enumerate(items):
        if stack:
            parent[k] = stack[-1][0]
        if tok[0] != "punct":
            continue
        value = tok[1]
        if value in _OPEN:
            stack.append((k, _OPEN[value], []))
        elif value in _CLOSE:
            if not stack:
                continue
            if stack[-1][1] != value:
                stack = []
                continue
            open_index, _expected, commas = stack.pop()
            match[open_index] = (k, commas)
            parent[k] = stack[-1][0] if stack else -1
        elif value == "," and stack:
            stack[-1][2].append(k)
    return match, parent


def _arg_ranges(match, open_index):
    """Token ranges (start, end) of the arguments or entries of the bracket at open_index; None when it never closed.

    A trailing comma does not add an empty argument, and an empty pair of brackets has none.
    """
    found = match.get(open_index)
    if found is None:
        return None
    close, commas = found
    bounds = [open_index] + commas + [close]
    ranges = [(bounds[i] + 1, bounds[i + 1]) for i in range(len(bounds) - 1)]
    if ranges and ranges[-1][0] >= ranges[-1][1]:
        ranges.pop()
    return ranges


def _object_entries(items, match, start, end):
    """If items[start:end] is exactly one object literal, return its entry ranges; else None."""
    if end - start < 2 or items[start][:2] != ("punct", "{"):
        return None
    found = match.get(start)
    if found is None or found[0] != end - 1:
        return None
    return _arg_ranges(match, start)


def _is_inherit(token):
    return token[0] == "str" and token[1].strip().lower() in ("", "inherit")


def _classify_options(items, entries):
    """Inspect an options object literal. Returns dict(status, label).

    status is pinned, plugin, missing or unverifiable. An empty or 'inherit' model is no pin (the
    same rule the Agent hook uses). A model written as a method or getter is unverifiable.
    """
    model = None  # None = no model key seen; else 'pinned' | 'missing'
    uncertain = False  # a spread, computed key or model method somewhere
    uncertain_after_model = False
    label = None
    plugin_agent = False
    for start, end in entries:
        size = end - start
        if size <= 0:
            continue
        first = items[start]
        if first[:2] == ("punct", "..."):
            uncertain = uncertain_after_model = True
            continue
        if first[:2] == ("punct", "["):
            uncertain = uncertain_after_model = True
            continue
        if first[0] == "id" and size >= 2 and items[start + 1][:2] == ("punct", "(") and first[1] == "model":
            uncertain = uncertain_after_model = True  # model() { ... }
            continue
        if (first[0] == "id" and first[1] in ("get", "set", "async") and size >= 3
                and items[start + 1][:2] == ("id", "model") and items[start + 2][:2] == ("punct", "(")):
            uncertain = uncertain_after_model = True  # get model() { ... }
            continue
        if size == 1 and first[0] == "id":
            if first[1] == "model":
                model = "pinned"  # shorthand { model }: the value is a variable we cannot see into
                uncertain_after_model = False
            continue
        if size >= 3 and first[0] in ("id", "str", "num") and items[start + 1][:2] == ("punct", ":"):
            key = first[1]
            count = size - 2
            value = items[start + 2]
            if key == "model":
                uncertain_after_model = False
                if count == 1 and value[0] == "id" and value[1] in ("undefined", "null"):
                    model = "missing"
                elif count == 1 and _is_inherit(value):
                    model = "missing"
                elif count == 2 and value[:2] == ("id", "void"):
                    model = "missing"  # void 0
                else:
                    model = "pinned"
            elif key == "agentType" and count == 1 and value[0] == "str" and ":" in value[1]:
                plugin_agent = True
            elif key == "label" and count == 1 and value[0] == "str":
                label = value[1]
    if model == "pinned":
        status = "pinned"
    elif plugin_agent:
        status = "plugin"
    elif model == "missing" and not uncertain_after_model:
        status = "missing"
    elif uncertain:
        status = "unverifiable"
    else:
        status = "missing"
    return {"status": status, "label": label}


def _is_indirect_reference(items, match, parent, idx):
    """True when the `agent` identifier at idx is used as a value (aliased, passed on, called through
    .call/.apply/.bind or parenthesised) rather than called directly. Declarations, property keys,
    arrow parameters and destructuring patterns are not uses."""
    prev = items[idx - 1] if idx > 0 else None
    nxt = items[idx + 1] if idx + 1 < len(items) else None
    after = items[idx + 2] if idx + 2 < len(items) else None
    if prev is not None:
        if prev[0] == "punct" and prev[1] in (".", "?."):
            return False  # x.agent: a member of something else
        if prev[0] == "id" and prev[1] in _DECLARATIONS:
            return False
        if prev[0] == "id" and prev[1] == "typeof":
            return False  # typeof agent: a type test, not a use
    if nxt is not None and nxt[0] == "punct":
        if nxt[1] in (".", "?.") and after is not None and after[0] == "id" and after[1] in _INDIRECT_METHODS:
            return True
        if nxt[1] in (".", "?.") and after is not None and after[0] == "id":
            return False  # agent.length and similar: a read of a property, the function is not passed on
        if nxt[1] == ":" and prev is not None and prev[0] == "punct" and prev[1] in ("{", ","):
            return False  # { agent: ... } is a key
        if nxt[1] == "=" and after is not None and after[:2] == ("punct", ">"):
            return False  # agent => ...: a parameter
    p = parent[idx]
    if p >= 0 and p in match:
        close = match[p][0]
        follower = items[close + 1] if close + 1 < len(items) else None
        follower2 = items[close + 2] if close + 2 < len(items) else None
        if items[p][1] == "(" and follower is not None and follower[:2] == ("punct", "=") \
                and follower2 is not None and follower2[:2] == ("punct", ">"):
            return False  # (agent, x) => ...: parameters
        if items[p][1] == "(" and p >= 1 and (
                items[p - 1][:2] == ("id", "function")
                or (p >= 2 and items[p - 1][0] == "id" and items[p - 2][:2] == ("id", "function"))):
            return False  # function f(agent) {...}: parameters
        if items[p][1] == "{" and follower is not None and (
                follower[:2] == ("punct", "=") or follower[:2] in (("id", "of"), ("id", "in"), ("id", "from"))):
            return False  # const { agent } = ... and import { agent } from ...: patterns, not uses
    if prev is not None and (
            (prev[0] == "punct" and prev[1] in _VALUE_PREV)
            or (prev[0] == "id" and prev[1] in _REGEX_AFTER_WORD)):
        return True
    return False


def _bracket_agent_call(items, idx):
    """globalThis['agent'](...) and similar: the string 'agent' between [ ] right before a call."""
    return (idx > 0 and idx + 2 < len(items)
            and items[idx - 1][:2] == ("punct", "[")
            and items[idx + 1][:2] == ("punct", "]")
            and items[idx + 2][:2] == ("punct", "("))


def check_source(src):
    """Count agent() call sites.

    Returns a dict: calls, pinned, plugin, missing (list), unverifiable (list), indirect (list),
    balanced. `indirect` lists uses of agent that are not direct calls, which cannot be checked.
    """
    toks = tokenize(src)
    items = toks.items
    match, parent = _bracket_map(items)
    result = {"calls": 0, "pinned": 0, "plugin": 0, "missing": [], "unverifiable": [], "indirect": [],
              "balanced": toks.balanced}
    for idx, (kind, value, line) in enumerate(items):
        if kind == "str" and value == "agent" and _bracket_agent_call(items, idx):
            result["indirect"].append({"line": line, "label": None})
            continue
        if kind != "id" or value != "agent":
            continue
        if idx > 0:
            prev = items[idx - 1]
            if prev[0] == "punct" and prev[1] in (".", "?."):
                continue
            if prev[0] == "id" and prev[1] == "function":
                continue
        j = idx + 1
        if j < len(items) and items[j][:2] == ("punct", "?."):
            j += 1
        if j >= len(items) or items[j][:2] != ("punct", "("):
            if _is_indirect_reference(items, match, parent, idx):
                result["indirect"].append({"line": line, "label": None})
            continue
        result["calls"] += 1
        args = _arg_ranges(match, j)
        if args is None:
            result["unverifiable"].append({"line": line, "label": None})
            continue
        if any(end > start and items[start][:2] == ("punct", "...") for start, end in args):
            result["unverifiable"].append({"line": line, "label": None})
            continue
        if len(args) < 2:
            result["missing"].append({"line": line, "label": None})
            continue
        entries = _object_entries(items, match, args[1][0], args[1][1])
        if entries is None:
            result["unverifiable"].append({"line": line, "label": None})
            continue
        info = _classify_options(items, entries)
        record = {"line": line, "label": info["label"]}
        if info["status"] == "pinned":
            result["pinned"] += 1
        elif info["status"] == "plugin":
            result["plugin"] += 1
        elif info["status"] == "missing":
            result["missing"].append(record)
        else:
            result["unverifiable"].append(record)
    return result


def _describe(records):
    parts = []
    for rec in records[:MAX_LISTED]:
        text = "line %d" % rec["line"]
        if rec.get("label"):
            text += " [label %s]" % rc.safe_label(rec["label"], 40)
        parts.append(text)
    if len(records) > MAX_LISTED:
        parts.append("and %d more" % (len(records) - MAX_LISTED))
    return ", ".join(parts)


def _read_script(tool_input, cwd):
    """Return source text, or None when there is nothing readable to check."""
    path = tool_input.get("scriptPath")
    if isinstance(path, str) and path.strip():
        # scriptPath takes precedence over script in the tool itself, so it decides here too.
        if not os.path.isabs(path):
            base = cwd if isinstance(cwd, str) and cwd.strip() else os.getcwd()
            path = os.path.join(base, path)
        try:
            info = os.stat(path)
            if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_SCRIPT_BYTES:
                return None  # a FIFO would block open() forever; too big is not worth the latency
            with open(path, "rb") as handle:
                data = handle.read(MAX_SCRIPT_BYTES + 1)
        except Exception:
            return None
        if len(data) > MAX_SCRIPT_BYTES:
            return None
        return data.decode("utf-8", "replace")
    script = tool_input.get("script")
    if isinstance(script, str):
        data = script.encode("utf-8", "replace")
        if len(data) > MAX_SCRIPT_BYTES:
            return None
        return script
    return None


def _plural(count, word):
    return "%d %s%s" % (count, word, "" if count == 1 else "s")


def build_text(res, blocking):
    calls = res["calls"]
    pinned = res["pinned"] + res["plugin"]
    missing = res["missing"]
    unverifiable = res["unverifiable"]
    indirect = res["indirect"]
    head = "dojo-router: this workflow has %s and %d set a model" % (_plural(calls, "agent() call"), pinned)
    bits = []
    if missing:
        bits.append("%d set none (%s)" % (len(missing), _describe(missing)))
    if unverifiable:
        bits.append(
            "%d pass options that are not an object literal, so they cannot be checked here (%s)"
            % (len(unverifiable), _describe(unverifiable))
        )
    if indirect:
        bits.append(
            "%s used agent as a value instead of calling it, so those calls cannot be checked here (%s)"
            % (_plural(len(indirect), "reference"), _describe(indirect))
        )
    if not res["balanced"]:
        bits.append("the script did not parse cleanly, so the count may be incomplete")
    body = "; ".join(bits)
    if blocking:
        return (
            "%s — %s. A call with no model runs on your session's model, so this was blocked. "
            "Add model: 'haiku' (look things up), 'sonnet' (build or review) or 'opus' (judge) to "
            "the options of each listed agent() call, then run the workflow again. "
            "Allow it with DOJO_ROUTER_OFF=1 or mode warn." % (head, body)
        )
    return (
        "%s — %s. A call with no model runs on your session's model. Add model: 'haiku', "
        "'sonnet' or 'opus' to each agent() options object. "
        "Turn off with DOJO_ROUTER_OFF=1 or mode off." % (head, body)
    )


def main():
    payload = rc.read_payload()
    if payload is None or rc.killed():
        return
    mode = rc.get_mode()
    if mode == "off":
        return
    if payload.get("tool_name") != "Workflow":
        return
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return
    src = _read_script(tool_input, payload.get("cwd"))
    if src is None:
        return
    res = check_source(src)
    if not res["balanced"] and res["calls"] == 0 and not res["indirect"] and "agent" not in src:
        return  # nothing here looks like a dispatch
    if not res["missing"] and not res["unverifiable"] and not res["indirect"] and res["balanced"]:
        return
    if mode == "block" and res["missing"]:
        rc.emit_deny(build_text(res, True))
        return
    digest = hashlib.sha256(src.encode("utf-8", "replace")).hexdigest()
    if rc.first_time(payload.get("session_id"), "workflow:" + digest):
        rc.emit_warn(build_text(res, False))


if __name__ == "__main__":
    rc.run(main)
