#!/usr/bin/env python3
"""dojo-verify: Stop hook. A reply that claims success needs a passing check behind it.

When the assistant's final message claims success (tests pass, verified, fixed, deployed ...) and no recognized
check ran, and came back clean, after the last change made in this session, this hook blocks the stop once (mode
block), or just says so (mode warn). A session with no change in it is not judged. It reads the newest part of the
transcript, never runs anything, and fails open on every error.

Stdlib only, Python 3.9. The claim and check patterns live in patterns.json (the mod carries a copy in
patterns.ts; a test keeps them equal).
"""
import hashlib
import json
import os
import re
import shlex
import sys
import tempfile
import time

MAX_STDIN = 1024 * 1024
TAIL_BYTES = 2 * 1024 * 1024
BUDGET_SECONDS = 0.9
MAX_CLAIM_QUOTE = 60

HERE = os.path.dirname(os.path.abspath(__file__))
WS = " \t\r\n\f\v"
ENV_ASSIGN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
DURATION = re.compile(r"^\d+(?:\.\d+)?[smhd]?$")
TOKEN = re.compile(r"[\w']+", re.ASCII)

_PATTERNS = None


class Patterns(object):
    """patterns.json, compiled."""

    def __init__(self, raw):
        flags = re.IGNORECASE | re.ASCII
        edges = raw["claim_edges"]
        before, after = edges["before"], edges["after"]

        def claim(body):
            return re.compile(before + "(?:" + body + ")" + after, flags)

        self.strong = [claim(b) for b in raw["strong"]]
        self.weak = [claim(b) for b in raw["weak"]]
        self.weak_skip_words = set(raw["weak_skip_before"]["words"])
        self.weak_skip_window = int(raw["weak_skip_before"]["window"])
        self.attributive_words = set(raw["attributive"]["words"])
        self.attributive_before = set(raw["attributive"]["before"])
        self.negators = set(raw["negators"])
        self.negation_window = int(raw["negation_window"])
        self.negation_cut_words = set(raw["negation_cut_words"])
        self.negation_cut_chars = raw["negation_cut_chars"]
        self.negated_after = set(raw["negated_after"])
        self.future_before = set(raw["future_before"])
        self.future_window = int(raw["future_window"])
        self.future_phrases = set(tuple(x) for x in raw["future_phrases"])
        self.disclosure = [re.compile(b, flags) for b in raw["disclosure"]]
        self.frames = [re.compile(b, flags) for b in raw["disclosure_frames"]]
        hist = raw["history"]
        self.history_before = re.compile(hist["before"], flags)
        self.history_after = re.compile(hist["after"], flags)
        self.history_past_frame = re.compile(hist["past_frame"], flags)
        self.history_past_before = re.compile(hist["past_before"], flags)
        self.history_past_near = re.compile(hist["past_near"], flags)
        self.history_past_after = re.compile(hist["past_after"], flags)
        q = raw["question"]
        self.q_lead = re.compile(q["lead"], flags)
        self.q_mid = re.compile(q["mid"], flags)
        self.q_soft = re.compile(q["soft_boundary"], flags)
        self.q_hard = re.compile(q["hard_boundary"], flags)
        self.q_asserting = re.compile(q["asserting"], flags)
        self.clause_break = re.compile(raw["clause_break"], flags)
        lim = raw["limits"]
        self.raw_head = int(lim["raw_head"])
        self.raw_tail = int(lim["raw_tail"])
        self.sentence_head = int(lim["sentence_head"])
        self.sentence_tail = int(lim["sentence_tail"])
        self.sentences_head = int(lim["max_sentences_head"])
        self.sentences_tail = int(lim["max_sentences_tail"])
        self.failure = re.compile(raw["failure_markers"], re.ASCII)
        chk = raw["check"]
        self.check_any = set(chk["any"])
        self.check_sub = dict((k, [v.split() for v in vs]) for k, vs in chk["sub"].items())
        self.check_flag = dict((k, set(vs)) for k, vs in chk["flag"].items())
        self.aliases = dict(chk["aliases"])
        self.script_runners = set(chk["script_runners"])
        self.script_re = re.compile(chk["script_pattern"], re.ASCII)
        self.script_skip_first = set(chk["script_skip_first"])
        self.task_runners = set(chk["task_runners"])
        self.task_re = re.compile(chk["task_pattern"], re.ASCII)
        self.prefix_wrappers = set(chk["prefix_wrappers"])
        self.timeout_wrappers = set(chk["timeout_wrappers"])
        self.wrapper_pairs = [tuple(p) for p in chk["wrapper_pairs"]]
        self.shell_c = set(chk["shell_c"])
        self.python_re = re.compile(chk["python_re"], re.ASCII)
        self.errexit_re = re.compile(chk["errexit_re"], re.ASCII)
        self.pipefail_re = re.compile(chk["pipefail_re"], re.ASCII)
        self.browser_re = re.compile(chk["browser_tool_re"], re.IGNORECASE | re.ASCII)
        self.noop_flags = set(chk["noop_flags"])
        self.task_noop_flags = set(chk["task_noop_flags"])
        self.var_suffixes = list(chk["var_program_suffixes"])
        self.interpreters = set(chk["interpreters"])
        self.shell_reserved = set(chk["shell_reserved"])
        self.loop_words = set(chk["loop_words"])
        self.script_exts = set(chk["script_exts"])
        self.script_dirs = set(chk["script_dirs"])
        self.script_dir_name_re = re.compile(chk["script_dir_name_re"], re.IGNORECASE | re.ASCII)
        self.script_skip_dirs = set(chk["script_skip_dirs"])
        self.script_name_re = re.compile(chk["script_name_re"], re.IGNORECASE | re.ASCII)
        self.inline_interpreters = set(chk["inline_interpreters"])
        self.inline_code_flags = set(chk["inline_code_flags"])
        mut = raw["mutate"]
        self.mut_tools = set(mut["tools"])
        self.mut_programs = set(mut["programs"])
        self.mut_sub = dict((k, [v.split() for v in vs]) for k, vs in mut["sub"].items())
        self.mut_flag_prefix = dict((k, list(vs)) for k, vs in mut["flag_prefix"].items())
        self.sink_programs = set(mut["sink_programs"])
        self.null_targets = set(mut["null_targets"])
        self.dest_programs = set(mut["dest_programs"])
        self.xargs_value_flags = set(mut["xargs_value_flags"])
        self.temp_prefixes = list(mut["temp_prefixes"])
        self.refused_re = re.compile(mut["refused_markers"], re.IGNORECASE | re.ASCII)
        self.not_found_re = re.compile(mut["not_found_re"], re.IGNORECASE | re.ASCII)
        self.not_found_skip = set(mut["not_found_skip"])
        self.interp_write_re = re.compile(mut["interp_write_re"], re.ASCII)


def patterns():
    global _PATTERNS
    if _PATTERNS is None:
        with open(os.path.join(HERE, "patterns.json"), "r") as fh:
            _PATTERNS = Patterns(json.load(fh))
    return _PATTERNS


# ------------------------------------------------------------------------------------------------ claims

FENCE = re.compile(r"```.*?```", re.S)
STRAY_FENCE = re.compile(r"```[^\n]*")
INLINE_CODE = re.compile(r"`[^`\n]*`")


def normalize_text(text):
    """Drop code (closed fenced blocks, a stray fence line, inline spans) and straighten curly quotes."""
    text = FENCE.sub(" ", text)
    text = STRAY_FENCE.sub(" ", text)  # an unclosed fence hides only its own line, not the rest of the message
    text = INLINE_CODE.sub(" ", text)
    for src, dst in (("’", "'"), ("‘", "'"), ("“", '"'), ("”", '"')):
        text = text.replace(src, dst)
    return text


def split_sentences(text):
    """[(sentence, terminator)]: a sentence ends at a newline, or at '.', '!', '?' before whitespace or the end."""
    out = []
    cur = []
    n = len(text)
    i = 0
    while i < n:
        ch = text[i]
        if ch == "\n":
            out.append(("".join(cur), ""))
            cur = []
        elif ch in ".!?":
            j = i
            while j + 1 < n and text[j + 1] in ".!?":
                j += 1
            nxt = text[j + 1] if j + 1 < n else ""
            cur.append(text[i:j + 1])
            if nxt == "" or nxt in WS:
                out.append(("".join(cur), text[j]))
                cur = []
            i = j
        else:
            cur.append(ch)
        i += 1
    if cur:
        out.append(("".join(cur), ""))
    return out


def _guarded(sentence, match, tier, p):
    """True when this match is not a claim: negated, future or conditional, or 'how it works'."""
    prefix = sentence[:match.start()]
    cut = max(prefix.rfind(c) for c in p.negation_cut_chars)
    if cut >= 0:
        prefix = prefix[cut + 1:]
    words = TOKEN.findall(prefix.lower())
    for i in range(len(words) - 1, -1, -1):
        if words[i] in p.negation_cut_words:  # "No regressions and all tests pass": the 'no' belongs to the first clause
            words = words[i + 1:]
            break
    for w in words[-p.negation_window:]:
        if w in p.negators or w.endswith("n't"):
            return True
    near = words[-p.future_window:]
    for w in near:
        if w in p.future_before or w.endswith("'ll"):
            return True
    for i in range(len(near) - 1):
        if (near[i], near[i + 1]) in p.future_phrases:  # "yet to be deployed"
            return True
    if tier == "weak":
        for w in words[-p.weak_skip_window:]:
            if w in p.weak_skip_words:
                return True
    elif words and words[-1] in p.attributive_before and match.group(0).lower() in p.attributive_words:
        return True  # "a fixed seed", "the deployed copy": the word describes a noun, it does not claim anything
    after = re.match(r"\s*([\w']+)", sentence[match.end():], re.ASCII)
    if after and after.group(1).lower() in p.negated_after:
        return True
    return False


def _head_tail(text, head, tail):
    """text itself, or its first `head` and last `tail` characters when it is longer than both together."""
    if len(text) <= head + tail:
        return text
    return text[:head] + "\n" + text[-tail:]


def split_clauses(sentence, p):
    """[(start, end)] spans of the clauses of one sentence, cut at ';' and before 'but', 'and', 'though' ..."""
    spans = []
    start = 0
    for m in p.clause_break.finditer(sentence):
        spans.append((start, m.start()))
        start = m.end()
    spans.append((start, len(sentence)))
    return spans


def _is_history(pre, post, frame, p):
    """Is this first-person or passive frame telling how the bug came about, rather than the state of this work?

    A time marker around it ('previously', 'until now', 'in the original PR', 'ago') makes it a history. So does a
    cause, for a frame in the past tense ('never', "didn't", 'was not'): 'because' before it, 'since', 'as', 'when'
    right before it, or 'until', 'hence', 'which broke ...' after it. A frame about the present or about being
    unable ("I haven't run it", "I couldn't run it") has a reason, not a cause: 'Because Docker is down, I couldn't
    run the tests' is still a disclosure.
    """
    if p.history_before.search(pre) or p.history_after.search(post):
        return True
    if p.history_past_frame.search(frame):
        return bool(p.history_past_before.search(pre) or p.history_past_near.search(pre)
                    or p.history_past_after.search(post))
    return False


def _clause_discloses(text, p):
    """Does this clause say, explicitly, that the work is unverified, untested or was not run?

    'unverified' and 'untested' say it outright. A first-person frame ('I didn't run the tests', 'it hasn't been
    tested') says it too, unless the clause is telling a history: 'it failed because we never ran the migration',
    'we didn't test it before'. Those describe how the bug came about, not the state of this fix.
    """
    if any(rx.search(text) for rx in p.disclosure):
        return True
    for rx in p.frames:
        for m in rx.finditer(text):
            if _is_history(text[:m.start()], text[m.end():], m.group(0), p):
                continue
            return True
    return False


def _disclosed_clauses(sentence, p):
    """[bool] per clause: does it say, explicitly, that the work is unverified, untested or was not run?"""
    spans = split_clauses(sentence, p)
    return spans, [_clause_discloses(sentence[a:b], p) for a, b in spans]


def _question_claim_part(sentence, p):
    """What comes before the question in a sentence that ends in '?', or None when the sentence is all question.

    'Is it fixed?' and 'Should I deploy it?' are questions and claim nothing. 'Fixed it and all tests pass, want me
    to commit?' claims something and then asks: the claim part is what gets judged. The question starts at the first
    ',', ';', dash or conjunction that is followed by a question opener ('want me', 'should I', 'right'); failing
    that, the last ',', ';' or dash starts it. A question with none of those has no claim part.

    A sentence that opens with a question word can still assert something after a subordinator that takes the
    claim as given: 'Want me to commit now that all tests pass?', 'Should I push, since the build is green?'. The
    claim part is what follows it. ('Should be fixed now', with nothing after 'should' to ask about, is not a
    question opener.)
    """
    if p.q_lead.match(sentence):
        m = p.q_asserting.search(sentence)
        tail = sentence[m.end():] if m else ""
        return tail if tail.strip() else None
    cut = -1
    for m in p.q_soft.finditer(sentence):
        if p.q_mid.match(sentence[m.end():]):
            cut = m.start()
            break
    if cut < 0:
        for m in p.q_hard.finditer(sentence):
            cut = m.start()
    if cut <= 0:
        return None
    head = sentence[:cut]
    return head if head.strip() else None


def _excused(pos, spans, flags):
    """A disclosure excuses the claims in its own clause and in the clause beside it, and nothing further away."""
    for i, (a, b) in enumerate(spans):
        if pos < b or i == len(spans) - 1:
            return any(flags[max(0, i - 1):i + 2])
    return False


def detect_claim(text, mutated):
    """The first success claim in text, as {tier, word, sentence}, or None.

    A session with no change in it (mutated False: no edit, no write, no file-writing command) is never judged:
    there is nothing a check could have been run against. A question is not a claim, but a claim followed by a
    question in the same sentence ('Fixed it and all tests pass, want me to commit?') is still judged. A disclosure
    ('X is unverified', 'I did not run the tests') excuses the claims in its own clause and the clause beside it,
    within one sentence; every other negation applies per claim. Weak words (done, works, ...) are also skipped in 'how it works' phrasing. Only
    the start and the end of a very long message are read, so no input can make this slow.
    """
    if not mutated or not isinstance(text, str) or not text.strip():
        return None
    p = patterns()
    sentences = split_sentences(normalize_text(_head_tail(text, p.raw_head, p.raw_tail)))
    if len(sentences) > p.sentences_head + p.sentences_tail:
        sentences = sentences[:p.sentences_head] + sentences[-p.sentences_tail:]
    for sentence, term in sentences:
        if not sentence.strip():
            continue
        sentence = _head_tail(sentence, p.sentence_head, p.sentence_tail)
        if term == "?":
            sentence = _question_claim_part(sentence, p)
            if sentence is None:
                continue
        spans, flags = _disclosed_clauses(sentence, p)
        any_disclosure = any(flags)
        for tier, regs in (("strong", p.strong), ("weak", p.weak)):
            for rx in regs:
                for m in rx.finditer(sentence):
                    if any_disclosure and _excused(m.start(), spans, flags):
                        continue
                    if not _guarded(sentence, m, tier, p):
                        return {"tier": tier, "word": m.group(0), "sentence": sentence.strip()}
    return None


# ------------------------------------------------------------------------------------------------ checks


def split_segments(cmd):
    """Split a shell command into [[text, op_after]] at && || | ; & and newlines (quotes and $( ) respected)."""
    segs = []
    cur = []
    n = len(cmd)
    i = 0
    quote = None
    depth = 0

    def push(op):
        segs.append(["".join(cur).strip(), op])
        del cur[:]

    while i < n:
        c = cmd[i]
        nxt = cmd[i + 1] if i + 1 < n else ""
        if quote:
            cur.append(c)
            if c == "\\" and quote == '"' and nxt:
                cur.append(nxt)
                i += 1
            elif c == quote:
                quote = None
        elif c == "\\" and nxt:
            cur.append(c)
            cur.append(nxt)
            i += 1
        elif c == "'" or c == '"':
            quote = c
            cur.append(c)
        elif c == "#" and (not cur or cur[-1] in " \t"):
            while i + 1 < n and cmd[i + 1] != "\n":
                i += 1
        elif c == "$" and nxt == "(":
            depth += 1
            cur.append("$(")
            i += 1
        elif c == ")" and depth > 0:
            depth -= 1
            cur.append(c)
        elif depth > 0:
            cur.append(c)
        elif c == "\n":
            push("\n")
        elif c == ";":
            push(";")
        elif c == "&":
            if nxt == "&":
                push("&&")
                i += 1
            elif nxt == ">" or (cur and cur[-1] == ">"):
                cur.append(c)
            else:
                push("&")
        elif c == "|":
            if cur and cur[-1] == ">":
                cur.append(c)  # '>|' forces a redirect: it is not a pipe
            elif nxt == "|":
                push("||")
                i += 1
            elif nxt == "&":
                push("|")
                i += 1
            else:
                push("|")
        else:
            cur.append(c)
        i += 1
    push("")
    return [s for s in segs if s[0] != ""]


def _split_words(text):
    text = text.strip()
    while text.startswith("("):
        text = text[1:].lstrip()
    if text.count(")") > text.count("(") and "$(" not in text:
        text = text.rstrip(")").rstrip()
    try:
        return shlex.split(text, posix=True)
    except ValueError:
        return text.split()


def _strip_reserved(words):
    """The words once the shell keywords that open a compound command are off: do, then, else, elif, if, while, { ..."""
    reserved = patterns().shell_reserved
    k = 0
    while k < len(words) and words[k] in reserved:
        k += 1
    return words[k:]


def _tokens(text):
    return _strip_reserved(_split_words(text))


LOOP_VAR = re.compile(r"^\$(\w+)$|^\$\{(\w+)\}$")


def _loop_header(words, loops):
    """Remember what 'for x in a b c' iterates over, so a later '$x' can be read as one of those words."""
    if len(words) >= 3 and words[2] == "in" and re.match(r"^\w+$", words[1]):
        loops[words[1]] = words[3:]


def _loop_value(token, loops):
    """A loop variable that stands for a check script ('for t in tests/test_*.py; do python3 "$t"') is that script."""
    m = LOOP_VAR.match(token)
    if not m:
        return token
    for w in loops.get(m.group(1) or m.group(2), []):
        if _is_check_script(w):
            return w
    return token


def _base(token):
    return os.path.basename(token) if "/" in token else token


HEREDOC = re.compile(r"(?<!<)<<(-?)\s*(['\"]?)([A-Za-z_]\w*)\2")


def split_heredocs(cmd):
    """(the command without its heredoc bodies, [body, ...] in the order of their '<<' operators).

    A body is text for the program that reads it, not commands of this shell. What it is depends on that program:
    'cat > f <<EOF' writes text, 'bash <<EOF' runs it as commands, 'python3 - <<EOF' runs it as code.
    """
    if "<<" not in cmd:
        return cmd, []
    out = []
    bodies = []
    pending = []
    for line in cmd.split("\n"):
        if pending:
            delim, tabs, buf = pending[0]
            if (line.lstrip("\t") if tabs else line).strip() == delim:
                bodies.append("\n".join(buf))
                pending.pop(0)
            else:
                buf.append(line)
            continue
        out.append(line)
        for m in HEREDOC.finditer(line):
            pending.append((m.group(3), m.group(1) == "-", []))
    for _delim, _tabs, buf in pending:  # a heredoc that never closes still ran
        bodies.append("\n".join(buf))
    return "\n".join(out), bodies


def _unwrap(toks):
    """(program token, argument tokens) once env assignments and wrappers (env, time, timeout, uv run ...) are off."""
    p = patterns()
    k = 0
    while k < len(toks) and ENV_ASSIGN.match(toks[k]):
        k += 1
    toks = toks[k:]
    for _ in range(8):
        toks = _strip_reserved(toks)  # 'time { rm -rf build; }': the brace opens a group, it is not the program
        if not toks:
            return None
        prog = _base(toks[0])
        if prog in p.prefix_wrappers:
            toks = toks[1:]
            while toks and (toks[0].startswith("-") or ENV_ASSIGN.match(toks[0])):
                toks = toks[1:]
            continue
        if prog in p.timeout_wrappers:
            toks = toks[1:]
            while toks and toks[0].startswith("-"):
                toks = toks[1:]
            if toks and DURATION.match(toks[0]):
                toks = toks[1:]
            continue
        paired = False
        for first, second in p.wrapper_pairs:
            if prog == first and len(toks) > 1 and toks[1] == second:
                toks = toks[2:]
                while toks and toks[0].startswith("-"):
                    toks = toks[1:]
                paired = True
                break
        if paired:
            continue
        break
    else:
        return None
    if not toks:
        return None
    return toks[0], toks[1:]


def _program_name(raw):
    """The program a token names: its basename, an alias, or the tool a variable holds ($CLAUDE_BIN -> claude)."""
    p = patterns()
    b = _base(raw)
    if b.startswith("$"):
        name = re.sub(r"^\$\{?|\}$", "", b).lower()
        for suffix in p.var_suffixes:
            if name.endswith(suffix):
                name = name[:-len(suffix)]
                break
        b = name.replace("_", "-")
    return p.aliases.get(b, b)


def _is_check_script(path):
    """A test or check script by its name (test_x.py, a.test.js, scripts/test.sh, release-check.sh), or a runner
    in a tests folder (tests/*.py, tests/run.py).

    A folder alone doesn't make a script a check: tests/seed.py isn't one. And a script under a fixtures, helpers or
    data folder never is one: those make data for tests, they don't run them.
    """
    p = patterns()
    parts = path.replace("\\", "/").split("/")
    name = parts[-1]
    dot = name.rfind(".")
    if dot <= 0 or name[dot:].lower() not in p.script_exts:
        return False
    if any(d in p.script_skip_dirs for d in parts[:-1]):
        return False
    stem = name[:dot]
    if p.script_name_re.search(stem):
        return True
    return any(d in p.script_dirs for d in parts[:-1]) and bool(p.script_dir_name_re.search(stem))


def _script_arg_is_check(args):
    for a in args:
        if a.startswith("-"):
            continue
        return _is_check_script(a)
    return False


def _classify_check(raw, args):
    """('check', None), ('shell', inner_command) or None: is this program run a check?"""
    p = patterns()
    prog = _program_name(raw)
    if any(a in p.noop_flags for a in args):
        return None  # --version, --help, --collect-only ...: nothing was checked
    if "/" in raw and _is_check_script(raw):
        return ("check", None)  # ./scripts/test.sh
    if prog in p.shell_c:
        for idx, a in enumerate(args):
            if a.startswith("-") and not a.startswith("--") and a.endswith("c") and idx + 1 < len(args):
                return ("shell", args[idx + 1])
        return ("check", None) if _script_arg_is_check(args) else None  # bash scripts/release-check.sh
    if p.python_re.match(prog):
        if "-m" in args[:4]:
            idx = args.index("-m")
            if idx + 1 >= len(args):
                return None
            prog = p.aliases.get(_base(args[idx + 1]), _base(args[idx + 1]))
            args = args[idx + 2:]
            if any(a in p.noop_flags for a in args):
                return None
        else:
            return ("check", None) if _script_arg_is_check(args) else None  # python3 tests/test_x.py
    elif prog in p.interpreters and _script_arg_is_check(args):
        return ("check", None)  # node tests/x.test.js
    if prog in p.check_any:
        if prog == "tsc" and "--init" in args:
            return None
        return ("check", None)
    nonflag = [a for a in args if not a.startswith("-")]
    if prog in p.check_sub:
        for parts in p.check_sub[prog]:
            if nonflag[:len(parts)] == parts:
                return ("check", None)
    if prog in p.check_flag:
        for flag in p.check_flag[prog]:
            if flag in args:
                return ("check", None)
    if prog in p.script_runners:
        if not nonflag or nonflag[0] in p.script_skip_first:
            return None
        for a in nonflag[:4]:
            if a in ("run", "run-script", "exec"):
                continue
            if p.script_re.match(a):
                return ("check", None)
        for i, a in enumerate(args):
            if a.startswith("-") or a in ("run", "run-script", "exec"):
                continue
            # 'pnpm tsc --noEmit', 'yarn jest': the first real argument is a tool, so classify it as one
            sub = _classify(args[i:])
            return sub if sub is not None and sub[0] == "check" else None
        return None
    if prog in p.task_runners:
        if any(a in p.task_noop_flags for a in args):
            return None  # make -n test only prints what it would run
        for a in nonflag[:3]:
            if p.task_re.match(a):
                return ("check", None)
        return None
    return None


_PROJECT_ROOTS = []


def _set_project_root(cwd):
    """Remember the session's working directory: a project may itself live under the temp directory."""
    del _PROJECT_ROOTS[:]
    if isinstance(cwd, str) and cwd.strip():
        for c in (cwd, os.path.realpath(cwd)):
            c = c.rstrip("/")
            if c and c not in _PROJECT_ROOTS:
                _PROJECT_ROOTS.append(c)


def _is_temp(path):
    """True for a path in the temp directory that is outside the session's project: a scratch file."""
    for root in _PROJECT_ROOTS:
        if path == root or path.startswith(root + "/"):
            return False
    for prefix in patterns().temp_prefixes:
        if path.startswith(prefix) or path == prefix.rstrip("/"):
            return True
    return False


def _inline_code_writes(args):
    """True for 'python3 -c ...' or 'node -e ...' whose code writes, moves or removes files."""
    p = patterns()
    for i, a in enumerate(args):
        if a in p.inline_code_flags:
            return any(p.interp_write_re.search(x) for x in args[i + 1:])
    return False


def _find_mutates(args, depth):
    """'find -delete', or 'find -exec <a program that changes files> ... \\;'."""
    for a in args:
        if a in ("-delete", "-fprint", "-fprint0", "-fprintf", "-fls"):
            return True
    i = 0
    while i < len(args):
        if args[i] in ("-exec", "-execdir", "-ok", "-okdir"):
            j = i + 1
            sub = []
            while j < len(args) and args[j] not in (";", "+"):
                sub.append(args[j])
                j += 1
            if _run_mutates(sub, depth):
                return True
            i = j
        i += 1
    return False


def _xargs_inner(args):
    """The command xargs runs: its arguments once its own options (and their values) are off."""
    p = patterns()
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--":
            i += 1
            break
        if not a.startswith("-"):
            break
        i += 2 if a in p.xargs_value_flags else 1
    return args[i:]


def _tar_extracts(args):
    """tar x..., tar -xzf, tar --extract: it unpacks into the working tree. Listing and creating don't."""
    for i, a in enumerate(args):
        if a in ("--extract", "--get") or a.startswith("--extract="):
            return True
        if a.startswith("--"):
            continue
        if re.match(r"^-[A-Za-z]*x[A-Za-z]*$", a) or (i == 0 and re.match(r"^[A-Za-z]*x[A-Za-z]*$", a)):
            return True
    return False


def _wget_writes(args):
    """wget saves a file unless it is told to print to stdout (-O -) or only to look (--spider)."""
    for i, a in enumerate(args):
        if a == "--spider" or re.match(r"^-[A-Za-z]*O-$", a):
            return False
        if re.match(r"^-[A-Za-z]*O$", a) and i + 1 < len(args) and args[i + 1] == "-":
            return False
    return True


def _mutates(raw, args, depth=0):
    """True when this program run changes files: mv, rm, sed -i, git checkout, npm install, a formatter ..."""
    p = patterns()
    prog = _program_name(raw)
    if (p.python_re.match(prog) or prog in p.inline_interpreters) and _inline_code_writes(args):
        return True
    if p.python_re.match(prog) and "-m" in args[:4]:
        idx = args.index("-m")
        if idx + 1 >= len(args):
            return False
        prog = _program_name(args[idx + 1])
        args = args[idx + 2:]
    nonflag = [a for a in args if not a.startswith("-")]
    if prog == "find":
        return _find_mutates(args, depth)
    if prog == "xargs":
        return _run_mutates(_xargs_inner(args), depth)
    if prog in ("awk", "gawk"):
        return any(a == "inplace" or a.endswith("=inplace") or a == "-iinplace" for a in args)
    if prog == "wget":
        return _wget_writes(args)
    if prog == "tar":
        return _tar_extracts(args)
    if prog in p.mut_programs:
        if nonflag and all(_is_temp(a) for a in nonflag):
            return False  # it only touches scratch files
        if prog in p.dest_programs and nonflag and _is_temp(nonflag[-1]):
            return False  # copies into the temp directory
        return True
    if prog in p.sink_programs:  # tee writes its file arguments; 'tee /dev/null' and a bare 'tee' write nothing
        return any(a not in p.null_targets and not _is_temp(a) for a in nonflag)
    for parts in p.mut_sub.get(prog, []):
        if nonflag[:len(parts)] == parts:
            return True
    for pref in p.mut_flag_prefix.get(prog, []):
        if any(a.startswith(pref) for a in args):
            return True
    return False


def _run_mutates(toks, depth):
    """Does running these tokens as a command change files? (the command after 'xargs' or 'find -exec')"""
    if not toks or depth > 3:
        return False
    kind = _classify(toks, depth + 1)
    if kind is None:
        return False
    if kind[0] == "mut":
        return True
    if kind[0] == "shell":
        return any(k == "mut" for k, _level, _phrase in command_events(kind[1], depth + 1))
    return False


def _classify(toks, depth=0):
    """('check', None), ('shell', inner_command), ('mut', None) or None for one segment's tokens."""
    u = _unwrap(toks)
    if u is None:
        return None
    raw, args = u
    kind = _classify_check(raw, args)
    if kind is not None:
        return kind
    return ("mut", None) if _mutates(raw, args, depth) else None


def _heredoc_kind(toks, body):
    """What a heredoc body is for the program that reads it: commands for a shell, code for an interpreter.

    'bash <<EOF' and 'sh -s <<EOF' run the body as commands. 'python3 - <<EOF' and 'node <<EOF' run it as code, and it
    counts as a change when that code writes files. For anything else ('cat > f <<EOF') the body is text.
    """
    p = patterns()
    u = _unwrap([t for t in toks if not t.startswith("<<")])
    if u is None:
        return None
    raw, args = u
    prog = _program_name(raw)
    if [a for a in args if not a.startswith("-")]:
        return None  # it runs a script file; the heredoc is only its input
    if prog in p.shell_c:
        if any(a.startswith("-") and not a.startswith("--") and a.endswith("c") for a in args):
            return None
        return ("shell", body)
    if (p.python_re.match(prog) or prog in p.inline_interpreters) and p.interp_write_re.search(body):
        return ("mut", None)
    return None


REDIRECT_FD = re.compile(r"\d*>&\d+")
REDIRECT_ERR = re.compile(r"(?<![\w])2>>?\s*[^\s;&|<>]+")
QUOTED = re.compile(r"'[^']*'|\"(?:\\.|[^\"\\])*\"")


def _stdout_silenced(text):
    """True when the segment sends its stdout to a file (> out.log, >/dev/null, &>x), so its output is not shown."""
    t = QUOTED.sub(" ", text)
    t = REDIRECT_FD.sub(" ", t)
    t = REDIRECT_ERR.sub(" ", t)
    return ">" in t


def _handler_phrase(text):
    """The literal an 'echo'/'printf' handler prints, or '' for any other handler."""
    toks = _tokens(text)
    if not toks or _base(toks[0]) not in ("echo", "printf"):
        return ""
    words = [t for t in toks[1:] if not t.startswith("-")]
    return " ".join(words).replace("\\n", " ").strip()


def _or_handler(segs, k):
    """(masked, phrase) for the '||' after segment k: 'exit 1' and 'false' keep the failure, anything else eats it."""
    nxt = _tokens(segs[k + 1][0])
    first = _base(nxt[0]) if nxt else ""
    if first in ("exit", "return"):
        return (len(nxt) > 1 and nxt[1] == "0", "")
    if first == "false":
        return (False, "")
    return (True, _handler_phrase(segs[k + 1][0]))


def _masked(segs, idx, pipefail, errexit):
    """(masked, handler_phrase): masked is True when the command's exit status would not reflect segment idx.

    '|| true', '| tail', '; more' mask it, and so does 'CHECK && A || B' (a failed check falls through to B).
    The phrase is what an echo handler prints, so a visible handler line is not mistaken for the check's output.
    """
    if idx == len(segs) - 1:
        return (False, "")
    op = segs[idx][1]
    if op == "&&":
        for k in range(idx, len(segs) - 1):
            op_k = segs[k][1]
            if op_k in (";", "\n", "&"):
                return (False, "")
            if op_k == "||":
                return _or_handler(segs, k)
        return (False, "")
    if op == "|":
        return (not pipefail, "")
    if op == "||":
        return _or_handler(segs, idx)
    if op == ";" or op == "\n":
        return (not errexit, "")
    return (False, "")


REDIRECT_OUT = re.compile(r"(?:&>>?|\d*>>?\|?)\s*([^\s;&|<>]+)")
MARK = "\x01"
MARKED = re.compile(MARK + r"(\d+)" + MARK)


def _writes_redirect(text):
    """True when the segment redirects output into a file (> f, >> f, &> f), not /dev/null, a descriptor or a temp file."""
    p = patterns()
    quoted = []

    def keep(m):
        quoted.append(m.group(0))
        return MARK + str(len(quoted) - 1) + MARK

    t = QUOTED.sub(keep, text)
    t = REDIRECT_FD.sub(" ", t)
    for m in REDIRECT_OUT.finditer(t):
        target = MARKED.sub(lambda mm: quoted[int(mm.group(1))][1:-1], m.group(1))
        if target.startswith("(") or target in p.null_targets or target.startswith("/dev/fd/") or _is_temp(target):
            continue
        return True
    return False


def _not_found(toks, unwrapped, missing):
    """Did the shell say it could not find the program of this segment, or a wrapper in front of it ('npx tsc')?"""
    prog, args = unwrapped
    wrappers = toks[:len(toks) - len(args) - 1]
    return _base(prog) in missing or any(_base(w) in missing for w in wrappers)


def _branch_masks(segs, seg_words):
    """{segment index: handler phrase} for the segments in a 'then' branch that has an 'else' or 'elif' after it.

    'if [ -d tests ]; then pytest -q; else echo "no tests dir"; fi' runs only one branch. When the output is the
    else branch's echo, the check in the then branch never ran, so it is masked the way '|| echo' masks one, and the
    echo is its handler phrase.
    """
    reserved = patterns().shell_reserved
    out = {}
    stack = []  # one frame per open 'if': [state, indexes of the segments in its then branches, else still unread]
    for idx, (text, _op) in enumerate(segs):
        words = seg_words[idx]
        if stack and stack[-1][0] == "else" and stack[-1][2] and words and words[0] not in reserved:
            for i in stack[-1][1]:  # 'else' alone on its line: the echo is the next segment
                out[i] = _handler_phrase(text)
            stack[-1][2] = False
        for w in words:
            if w not in reserved:
                break
            if w == "if":
                stack.append(["cond", [], False])
            elif w == "then" and stack:
                stack[-1][0] = "then"
            elif w == "elif" and stack:
                for i in stack[-1][1]:
                    out.setdefault(i, "")  # a later branch may be the one that ran
                stack[-1][0] = "cond"
            elif w == "else" and stack:
                phrase = _handler_phrase(text)
                for i in stack[-1][1]:
                    out[i] = phrase
                stack[-1][0] = "else"
                stack[-1][2] = len(words) == 1
        if words and words[0] == "fi":
            if stack:
                stack.pop()
        elif stack and stack[-1][0] == "then":
            stack[-1][1].append(idx)
    return out


def command_events(cmd, depth=0, missing=None):
    """[(kind, level, phrase)] in the order they happen in cmd: kind 'check' or 'mut' (the command changes files).

    `missing` is the set of program names the shell said it could not find. A segment that runs one of them never
    started, and neither did the segments after it in the same '&&' chain; what ran before it did run.

    For a check, level 0: its exit status counts. 1: masked, so it counts only with visible, clean output. 2: masked
    and its stdout goes to a file, so nothing it printed is visible and it cannot count. A file-writing segment
    downstream of a check in the same pipe (pytest | tee out.log) captures that check's output and is not a change.
    """
    if depth > 3 or not isinstance(cmd, str):
        return []
    p = patterns()
    cmd, bodies = split_heredocs(cmd)
    segs = split_segments(cmd)
    pipefail = bool(p.pipefail_re.search(cmd))
    errexit = bool(p.errexit_re.search(cmd))
    found = []
    chain_check = False
    prev_op = ""
    loops = {}
    blocked = False
    seg_words = [_split_words(text) for text, _op in segs]
    branches = _branch_masks(segs, seg_words)
    for idx, (text, op) in enumerate(segs):
        piped = prev_op == "|"
        prev_op = op
        if not piped:
            chain_check = False
        words = seg_words[idx]
        if words and words[0] in p.loop_words:
            _loop_header(words, loops)
            continue
        toks = [_loop_value(t, loops) for t in _strip_reserved(words)] if loops else _strip_reserved(words)
        heredoc = None
        for _m in HEREDOC.finditer(text):
            body = bodies.pop(0) if bodies else ""
            if heredoc is None:
                heredoc = _heredoc_kind(toks, body)
        started = True
        if missing:
            u = _unwrap(toks)
            started = not (blocked or (u is not None and _not_found(toks, u, missing)))
            blocked = (not started) and op == "&&"
        if started:
            kind = _classify(toks, depth)
            if kind is None:
                kind = heredoc
        else:
            kind = None  # it never started; only its output redirect (the shell opens it first) can have written
        if kind is None and _writes_redirect(text):
            kind = ("mut", None)
        if kind is None:
            continue
        if kind[0] == "mut":
            if not (piped and chain_check):
                found.append(("mut", 0, ""))
            continue
        chain_check = True
        if op == "&":
            continue
        masked, phrase = _masked(segs, idx, pipefail, errexit)
        if idx in branches:  # in a then branch with an else after it: the other branch may be what ran
            masked, phrase = True, branches[idx] or phrase
        level = (2 if _stdout_silenced(text) else 1) if masked else 0
        if kind[0] == "check":
            found.append(("check", level, phrase))
        else:
            for inner_kind, inner_level, inner_phrase in command_events(kind[1], depth + 1, missing):
                if inner_kind == "check" and level > inner_level:
                    inner_level, inner_phrase = level, phrase
                found.append((inner_kind, inner_level, inner_phrase))
    return found


def _check_counts(level, phrase, output):
    """Does a check of this level count, given the output the command showed?"""
    if level == 0:
        return True
    if level == 1:
        return bool(output.strip()) and not (phrase and phrase.lower() in output.lower())
    return False


def is_evidence(cmd, output):
    """A command that ran a check, with output that shows no failure.

    A check whose exit status is masked (|| true, | tail, ; more commands) counts only when its output is
    visible and clean, and when the visible text is not just the failure handler's own echo.
    """
    output = output if isinstance(output, str) else ""
    if patterns().failure.search(output[:200000]):
        return False
    return any(kind == "check" and _check_counts(level, phrase, output)
               for kind, level, phrase in command_events(cmd))


# ------------------------------------------------------------------------------------------------ transcript


def read_tail(path):
    size = os.path.getsize(path)
    cut = size > TAIL_BYTES
    with open(path, "rb") as fh:
        if cut:
            fh.seek(size - TAIL_BYTES)
        data = fh.read(TAIL_BYTES if cut else size)
    if cut:
        nl = data.find(b"\n")
        data = data[nl + 1:] if nl >= 0 else b""
    return data


def parse_entries(data, deadline):
    entries = []
    for line in data.split(b"\n"):
        if time.time() > deadline:
            return None
        if not line.strip():
            continue
        try:
            obj = json.loads(line.decode("utf-8", "replace"))
        except Exception:
            continue
        if isinstance(obj, dict):
            entries.append(obj)
    return entries


def _blocks(entry):
    msg = entry.get("message")
    content = msg.get("content") if isinstance(msg, dict) else None
    if isinstance(content, list):
        return [b for b in content if isinstance(b, dict)]
    return []


def _content(entry):
    msg = entry.get("message")
    return msg.get("content") if isinstance(msg, dict) else None


def _text_of(content):
    """Plain text of a message content: a string, or the text blocks joined."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for b in content:
            if isinstance(b, dict) and b.get("type") == "text" and isinstance(b.get("text"), str):
                parts.append(b["text"])
        return "\n".join(parts)
    return ""


def _result_text(block):
    c = block.get("content")
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        return "\n".join(b.get("text", "") for b in c if isinstance(b, dict) and isinstance(b.get("text"), str))
    return ""


def _is_compact(entry):
    if entry.get("isCompactSummary") is True:
        return True
    if entry.get("type") == "system" and entry.get("subtype") == "compact_boundary":
        return True
    if entry.get("type") == "user":
        return _text_of(_content(entry)).lstrip().startswith("This session is being continued")
    return False


def _origin_kind(entry):
    origin = entry.get("origin")
    if isinstance(origin, dict):
        kind = origin.get("kind")
        return kind if isinstance(kind, str) else None
    if isinstance(origin, str):
        return origin
    return None


def _is_prompt(entry):
    """A real human prompt: not a tool result, meta entry, notification, peer message or local command echo."""
    if entry.get("type") != "user" or entry.get("isMeta") is True or entry.get("isSidechain") is True:
        return False
    kind = _origin_kind(entry)
    if kind is not None and kind != "human":
        return False
    content = _content(entry)
    if isinstance(content, list):
        if any(b.get("type") == "tool_result" for b in content if isinstance(b, dict)):
            return False
        has_image = any(b.get("type") == "image" for b in content if isinstance(b, dict))
    else:
        has_image = False
    text = _text_of(content).strip()
    if text.startswith(("<local-command-", "<task-notification", "[Request interrupted")):
        return False
    return bool(text) or has_image


def _missing_programs(text, p):
    """The program names a shell reported as 'command not found' (bash, zsh and dash word it differently).

    bash: 'bash: pytest: command not found'. zsh: 'zsh:1: command not found: pytest', '(eval):1: command not found:
    rm'. dash: 'sh: 1: npx: not found'. A shell's own name and a line number are not the program.
    """
    names = set()
    for m in p.not_found_re.finditer(text):
        name = (m.group(1) or m.group(2) or m.group(3) or "").strip("'\"`")
        if not name or name.isdigit() or name.lower() in p.not_found_skip:
            continue
        names.add(_base(name))
    return names


def _use_events(use, results, bg_done):
    """What one main-thread tool call did, in order: 'mut' (it changed files) and 'ok' (a check came back clean)."""
    p = patterns()
    name = use.get("name")
    inp = use.get("input") if isinstance(use.get("input"), dict) else {}
    res = results.get(use.get("id"))
    if name in p.mut_tools:
        if res is not None and res["error"]:
            return []  # the edit was refused: nothing changed
        path = inp.get("file_path") if isinstance(inp.get("file_path"), str) else inp.get("notebook_path")
        return [] if isinstance(path, str) and _is_temp(path) else ["mut"]  # a scratch file is not the project
    if name == "Bash":
        cmd = inp.get("command")
        out = []
        if inp.get("run_in_background") is True:
            events = command_events(cmd) if isinstance(cmd, str) else []
            finished = bg_done.get(use.get("id")) is True  # only a completion notice with exit code 0 counts
            for kind, level, phrase in events:
                if kind == "mut":
                    out.append("mut")
                elif finished and _check_counts(level, phrase, ""):
                    out.append("ok")
            return out
        # A command that exited non-zero still ran: whatever it wrote is on disk. Only a command that never started
        # changed nothing: one the engine refused (a hook, a permission prompt), or a program the shell could not
        # find. That is judged per segment: in 'sed -i ... && pytest' with 'pytest: command not found', the sed ran.
        short_error = res is not None and res["error"] and len(res["text"]) <= 400
        refused = short_error and bool(p.refused_re.search(res["text"]))
        missing = _missing_programs(res["text"], p) if short_error else set()
        events = command_events(cmd, 0, missing) if isinstance(cmd, str) else []
        clean = (res is not None and not res["error"] and not res["interrupted"]
                 and not res["text"].startswith("Exit code")
                 and not p.failure.search(res["text"][:200000]))
        for kind, level, phrase in events:
            if kind == "mut":
                if not refused:
                    out.append("mut")
            elif clean and _check_counts(level, phrase, res["text"]):
                out.append("ok")
        return out
    if isinstance(name, str) and p.browser_re.search(name):
        if res is not None and not res["error"] and not res["interrupted"]:
            return ["ok"]
    return []


def analyze(path, payload):
    """The facts about the session so far, or None when the transcript cannot answer (fail open).

    The scan is bounded (the newest part of the file, under a time budget) and newest first: it looks for the last
    change the main thread made, and for a clean check after it. A session with no change in view is not judged.
    A compaction summary ends the view: what came before it was summarised away.
    """
    _set_project_root(payload.get("cwd") if isinstance(payload, dict) else None)
    deadline = time.time() + BUDGET_SECONDS
    entries = parse_entries(read_tail(path), deadline)
    if not entries:
        return None

    start = 0
    for idx in range(len(entries) - 1, -1, -1):
        e = entries[idx]
        if e.get("isSidechain") is not True and _is_compact(e):
            start = idx + 1
            break
    view = entries[start:]
    if not view:
        return None

    boundary = -1
    for idx in range(len(view) - 1, -1, -1):
        e = view[idx]
        if e.get("isSidechain") is not True and _is_prompt(e):
            boundary = idx
            break

    uses = []
    results = {}
    bg_done = {}
    texts = []
    for idx, e in enumerate(view):
        if e.get("isSidechain") is True:
            continue
        kind = e.get("type")
        if kind == "assistant":
            for b in _blocks(e):
                if b.get("type") == "tool_use":
                    uses.append(b)
                elif idx > boundary and b.get("type") == "text" and isinstance(b.get("text"), str):
                    texts.append(b["text"])
        elif kind == "user":
            blocks = _blocks(e)
            trs = [b for b in blocks if b.get("type") == "tool_result" and isinstance(b.get("tool_use_id"), str)]
            if trs:
                tur = e.get("toolUseResult")
                interrupted = isinstance(tur, dict) and tur.get("interrupted") is True and len(trs) == 1
                for b in trs:
                    results[b["tool_use_id"]] = {
                        "error": bool(b.get("is_error")),
                        "text": _result_text(b),
                        "interrupted": interrupted,
                    }
            else:
                text = _text_of(_content(e))
                if _origin_kind(e) == "task-notification" or text.lstrip().startswith("<task-notification"):
                    ids = re.findall(r"<tool-use-id>([^<]+)</tool-use-id>", text)
                    code = re.search(r"completed \(exit code (\d+)\)", text)
                    if ids and code:
                        bg_done[ids[0].strip()] = code.group(1) == "0"

    mutated = False
    evidence = False
    for use in reversed(uses):
        for ev in reversed(_use_events(use, results, bg_done)):
            if ev == "mut":
                mutated = True
                break
            evidence = True
        if mutated:
            break

    last = payload.get("last_assistant_message")
    final_text = last if isinstance(last, str) else (texts[-1] if texts else "")
    boundary_id = ""
    if boundary >= 0:
        bid = view[boundary].get("uuid")
        boundary_id = bid if isinstance(bid, str) else ""
    return {"final_text": final_text, "mutated": mutated, "evidence": evidence, "boundary_id": boundary_id}


# ------------------------------------------------------------------------------------------------ hook


def _truthy(value):
    return isinstance(value, str) and value.strip().lower() in ("1", "true", "yes")


def killed():
    """Kill switches, in order: DOJO_OFF (whole suite), then DOJO_VERIFY_OFF (this plugin)."""
    return _truthy(os.environ.get("DOJO_OFF")) or _truthy(os.environ.get("DOJO_VERIFY_OFF"))


def get_mode():
    raw = os.environ.get("CLAUDE_PLUGIN_OPTION_MODE")
    mode = raw.strip().lower() if isinstance(raw, str) else ""
    return mode if mode in ("block", "warn", "off") else "block"


def read_stdin():
    """Stdin bytes, or None when it is larger than MAX_STDIN (drained so the sender does not hit a broken pipe)."""
    try:
        buf = sys.stdin.buffer.read(MAX_STDIN + 1)
        if len(buf) <= MAX_STDIN:
            return buf
        drained = 0
        while drained < 16 * MAX_STDIN:
            chunk = sys.stdin.buffer.read(65536)
            if not chunk:
                break
            drained += len(chunk)
    except Exception:
        pass
    return None


def _quote(sentence):
    s = re.sub(r"[\x00-\x1f\x7f\s]+", " ", sentence).strip().replace('"', "'")
    if len(s) > MAX_CLAIM_QUOTE:
        s = s[:MAX_CLAIM_QUOTE - 3].rstrip() + "..."
    return s


def _state_dir():
    base = os.environ.get("CLAUDE_PLUGIN_DATA") or tempfile.gettempdir()
    return os.path.join(base, "dojo-verify")


def _marker_path(payload, final_text, boundary_id):
    sid = re.sub(r"[^A-Za-z0-9_-]", "", str(payload.get("session_id") or ""))[:64] or "nosession"
    digest = hashlib.sha1((final_text + "\x00" + boundary_id).encode("utf-8", "replace")).hexdigest()[:16]
    return os.path.join(_state_dir(), "%s-%s.blocked" % (sid, digest))


def _already_blocked(path):
    return os.path.exists(path)


def _remember_block(path):
    try:
        d = os.path.dirname(path)
        if not os.path.isdir(d):
            os.mkdir(d)
        with open(path, "w") as fh:
            fh.write("1")
    except Exception:
        pass


def evaluate(payload, mode):
    """The hook's stdout object for this payload, or None to stay silent."""
    if payload.get("stop_hook_active") is True:
        return None
    if payload.get("agent_id"):
        return None  # a subagent's stop: the main thread's claim is what this plugin judges
    path = payload.get("transcript_path")
    if not isinstance(path, str) or not path or not os.path.isfile(path):
        return None
    info = analyze(path, payload)
    if info is None:
        return None
    claim = detect_claim(info["final_text"], info["mutated"])
    if claim is None or info["evidence"]:
        return None
    quote = _quote(claim["sentence"])
    marker = _marker_path(payload, info["final_text"], info["boundary_id"])
    if mode == "warn":
        return {
            "systemMessage": (
                'dojo-verify: the reply says "%s" but no passing check ran after the last change in this session '
                "— a claim without a passing check is unverified. Not blocking (mode=warn); set mode to block to "
                "enforce it, or DOJO_VERIFY_OFF=1 to turn it off." % quote
            )
        }
    if _already_blocked(marker):
        return None
    _remember_block(marker)
    return {
        "decision": "block",
        "reason": (
            'dojo-verify: the reply says "%s" but no passing check ran after the last change in this session — a '
            "claim without a passing check is unverified. Run the check now and show its result, or say plainly "
            "that it is unverified in the same sentence as the claim. (Turn off: DOJO_VERIFY_OFF=1 or mode=warn.)" % quote
        ),
    }


def run():
    raw = read_stdin()
    if raw is None:
        return None
    if killed():
        return None
    mode = get_mode()
    if mode == "off":
        return None
    try:
        payload = json.loads(raw.decode("utf-8", "replace"))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    return evaluate(payload, mode)


def main():
    out = None
    try:
        out = run()
    except Exception:
        out = None  # fail open
    if out is not None:
        try:
            sys.stdout.write(json.dumps(out))
            sys.stdout.flush()
        except Exception:
            pass
    sys.exit(0)


if __name__ == "__main__":
    main()
