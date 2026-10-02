"""A small, conservative shell lexer for the dojo-gates guards.

This is not a shell parser. It splits a Bash command line into segments (the
pieces joined by ; && || | & newline and subshell boundaries), keeps each
word's unquoted text and the part a shell would still expand, drops heredoc
bodies, and recurses into $( ), backticks, `bash -c '...'` and `eval`.

Stdlib only, Python 3.9 safe.
"""
import os
import re


class ParseError(Exception):
    pass


class Word(object):
    """text: unquoted value. live: only what a shell would still expand
    (single-quoted parts and escaped dollars are left out). raw: source text."""

    __slots__ = ("text", "live", "raw")

    def __init__(self, text, live, raw):
        self.text = text
        self.live = live
        self.raw = raw

    def __repr__(self):  # pragma: no cover
        return "Word(%r)" % (self.text,)


class Seg(object):
    """stdin: the text of expanding heredoc bodies fed to this command (the part
    a shell would expand). opens/closes: how many `(` subshell groups start
    before this segment and how many end after it."""

    __slots__ = ("words", "op_before", "op_after", "nested", "depth", "stdin", "opens", "closes")

    def __init__(self, words, op_before="", op_after="", nested=False, depth=0):
        self.words = words
        self.op_before = op_before
        self.op_after = op_after
        self.nested = nested
        self.depth = depth
        self.stdin = ""
        self.opens = 0
        self.closes = 0


_PLAIN = re.compile(r"[^\s'\"\\$`|&;()<>#]+")
_HEREDOC_DELIM = re.compile(r"[^\s;&|()<>]+")
_MAX_NEST = 4
_STRONG = ("&&", "||", "|", "|&")


def _heredoc_op(s, i):
    """s[i:i+2] is '<<' (and not '<<<'). Returns (delim, strip, expand, end).
    delim is "" when no delimiter word follows. Raises ParseError for an
    unterminated quoted delimiter."""
    n = len(s)
    j = i + 2
    strip = False
    if j < n and s[j] == "-":
        strip = True
        j += 1
    while j < n and s[j] in " \t":
        j += 1
    if j < n and s[j] in "'\"":
        q = s[j]
        k = s.find(q, j + 1)
        if k < 0:
            raise ParseError("unterminated heredoc delimiter")
        return s[j + 1:k], strip, False, k + 1
    m = _HEREDOC_DELIM.match(s, j)
    if not m:
        return "", strip, True, j
    tok = m.group(0)
    expand = not ("\\" in tok or "'" in tok or '"' in tok)
    return re.sub(r"[\\'\"]", "", tok), strip, expand, m.end()


def _skip_heredoc_bodies(s, i, pending):
    """i is the start of the line after the one that named the heredocs.
    Returns the index just past the last terminating line."""
    n = len(s)
    for delim, strip in pending:
        while i < n:
            j = s.find("\n", i)
            line = s[i:(j if j >= 0 else n)]
            i = j + 1 if j >= 0 else n
            chk = line.rstrip("\r")
            if strip:
                chk = chk.lstrip("\t")
            if chk == delim:
                break
    return i


def _ansi_c_end(s, i):
    """s[i] is the opening quote of `$'...'`. Returns the index of the closing quote,
    or -1. A backslash escapes the next character, so `\\'` does not close it."""
    n = len(s)
    j = i + 1
    while j < n:
        if s[j] == "\\":
            j += 2
        elif s[j] == "'":
            return j
        else:
            j += 1
    return -1


_ANSI_ESC = {"n": "\n", "t": "\t", "r": "\r", "a": "\a", "b": "\b", "e": "\x1b", "E": "\x1b",
             "f": "\f", "v": "\v", "\\": "\\", "'": "'", '"': '"', "?": "?"}


def _ansi_c_text(body):
    """Decode the common escapes of `$'...'`; an unknown escape keeps its text."""
    out = []
    i = 0
    n = len(body)
    while i < n:
        c = body[i]
        if c == "\\" and i + 1 < n:
            d = body[i + 1]
            if d in _ANSI_ESC:
                out.append(_ANSI_ESC[d])
                i += 2
                continue
            m = re.match(r"x[0-9A-Fa-f]{1,2}|[0-7]{1,3}", body[i + 1:])
            if m:
                tok = m.group(0)
                out.append(chr(int(tok[1:], 16) if tok[0] == "x" else int(tok, 8)))
                i += 1 + len(tok)
                continue
        out.append(c)
        i += 1
    return "".join(out)


def _match_paren(s, i):
    """i is just after '('. Return the index of the matching ')' (or len(s)).
    Quotes, comments and heredoc bodies are skipped, so the standard
    `$(cat <<'EOF' ... EOF\n)` form closes where the shell closes it."""
    depth = 1
    n = len(s)
    j = i
    pending = []
    while j < n:
        c = s[j]
        if c == "\n" and pending:
            j = _skip_heredoc_bodies(s, j + 1, pending)
            pending = []
            continue
        if c == "$" and s.startswith("$'", j):
            k = _ansi_c_end(s, j + 1)
            j = n if k < 0 else k + 1
            continue
        if c == "'":
            k = s.find("'", j + 1)
            j = n if k < 0 else k + 1
            continue
        if c == '"':
            j += 1
            while j < n and s[j] != '"':
                if s[j] == "\\":
                    j += 2
                elif s[j] == "$" and s.startswith("$(", j):
                    j = _match_paren(s, j + 2) + 1
                elif s[j] == "`":
                    k = s.find("`", j + 1)
                    j = n if k < 0 else k + 1
                else:
                    j += 1
            j += 1
            continue
        if c == "\\":
            j += 2
            continue
        if c == "#" and (j == i or s[j - 1] in " \t\n;&|("):
            k = s.find("\n", j)
            j = n if k < 0 else k
            continue
        if c == "<" and s.startswith("<<", j):
            if s.startswith("<<<", j):
                j += 3
                continue
            try:
                delim, strip, _expand, end = _heredoc_op(s, j)
            except ParseError:
                j += 2
                continue
            if delim:
                pending.append((delim, strip))
            j = end
            continue
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return j
        j += 1
    return n


def _match_brace(s, i):
    depth = 1
    n = len(s)
    j = i
    while j < n:
        c = s[j]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return j
        j += 1
    return n


class _Lexer(object):
    def __init__(self, cmd, nested, depth):
        self.s = cmd
        self.n = len(cmd)
        self.i = 0
        self.nested = nested
        self.depth = depth
        self.segs = []
        self.extras = []
        self.words = []
        self.t = []
        self.l = []
        self.inw = False
        self.ws = 0
        self.last_op = ""
        self.pending = []
        self.opens = 0
        self.skip_close = 0

    # -- word and segment bookkeeping ------------------------------------
    def _begin(self, pos):
        if not self.inw:
            self.inw = True
            self.ws = pos

    def _end_word(self, pos):
        if not self.inw:
            return
        raw = self.s[self.ws:pos]
        text = "".join(self.t)
        live = "".join(self.l)
        self.t = []
        self.l = []
        self.inw = False
        if raw in ("{", "}"):
            return
        self.words.append(Word(text, live, raw))

    def _end_seg(self, op):
        if self.words:
            seg = Seg(self.words, self.last_op, op, self.nested, self.depth)
            seg.opens = self.opens
            self.opens = 0
            if op == ")":
                seg.closes = 1
            elif op == "(":
                self.skip_close += 1  # `name(` opens a function body, not a subshell
            self.segs.append(seg)
            self.words = []
            self.last_op = op
            return
        if op == "(":
            self.opens += 1
        elif op == ")" and self.segs:
            if self.skip_close:
                self.skip_close -= 1
            else:
                self.segs[-1].closes += 1
        if op in _STRONG:
            if self.segs and self.segs[-1].op_after in (")", "}", ";", "\n"):
                self.segs[-1].op_after = op
            self.last_op = op

    def _sub(self, inner):
        if self.depth < _MAX_NEST and inner.strip():
            self.extras.extend(tokenize_safe(inner, True, self.depth + 1))

    # -- quoted regions ---------------------------------------------------
    def _dq(self):
        s = self.s
        n = self.n
        i = self.i
        text = []
        live = []
        while i < n:
            c = s[i]
            if c == '"':
                self.i = i + 1
                return "".join(text), "".join(live)
            if c == "\\" and i + 1 < n:
                d = s[i + 1]
                if d in '$`"\\':
                    text.append(d)
                    if d != "$":
                        live.append(d)
                elif d != "\n":
                    text.append(c + d)
                    live.append(c + d)
                i += 2
                continue
            if c == "$" and i + 1 < n and s[i + 1] == "(":
                j = _match_paren(s, i + 2)
                self._sub(s[i + 2:j])
                text.append(s[i:j + 1])
                live.append(s[i:j + 1])
                i = j + 1
                continue
            if c == "$" and i + 1 < n and s[i + 1] == "{":
                j = _match_brace(s, i + 2)
                text.append(s[i:j + 1])
                live.append(s[i:j + 1])
                i = j + 1
                continue
            if c == "`":
                j = s.find("`", i + 1)
                if j < 0:
                    j = n
                self._sub(s[i + 1:j])
                text.append(s[i:j + 1])
                live.append(s[i:j + 1])
                i = j + 1
                continue
            text.append(c)
            live.append(c)
            i += 1
        raise ParseError("unterminated double quote")

    def _heredocs(self, i):
        s = self.s
        n = self.n
        for delim, strip, expand, owner in self.pending:
            body = []
            while i < n:
                j = s.find("\n", i)
                line = s[i:(j if j >= 0 else n)]
                i = j + 1 if j >= 0 else n
                chk = line.rstrip("\r")
                if strip:
                    chk = chk.lstrip("\t")
                if chk == delim:
                    break
                if expand:
                    body.append(line)
            if expand and body:
                blob = "\n".join(body)
                if owner < len(self.segs):
                    # what the shell would expand in the body; an escaped dollar stays literal
                    self.segs[owner].stdin += blob.replace("\\$", "") + "\n"
                k = 0
                while True:
                    k = blob.find("$(", k)
                    if k < 0:
                        break
                    j = _match_paren(blob, k + 2)
                    self._sub(blob[k + 2:j])
                    k = j + 1
                k = 0
                while True:
                    k = blob.find("`", k)
                    if k < 0:
                        break
                    j = blob.find("`", k + 1)
                    if j < 0:
                        j = len(blob)
                    self._sub(blob[k + 1:j])
                    k = j + 1
        self.pending = []
        return i

    def _redirect(self, i):
        """s[i] is '<' or '>'. Returns the new index."""
        s = self.s
        n = self.n
        c = s[i]
        if i + 1 < n and s[i + 1] == "(":
            # process substitution
            self._begin(i)
            j = _match_paren(s, i + 2)
            self._sub(s[i + 2:j])
            self.t.append(s[i:j + 1])
            self.l.append(s[i:j + 1])
            return j + 1
        if c == "<" and s.startswith("<<", i) and not s.startswith("<<<", i):
            self._end_word(i)
            delim, strip, expand, j = _heredoc_op(s, i)
            if delim:
                # the command this heredoc feeds becomes segs[len(self.segs)] when it ends
                self.pending.append((delim, strip, expand, len(self.segs)))
            return j
        # plain redirection operator, possibly with an fd prefix such as 2>
        pre = "".join(self.t)
        if self.inw and pre.isdigit() and self.ws + len(pre) == i:
            pass  # keep the digits as the operator's fd prefix
        else:
            self._end_word(i)
        self._begin(i)
        if c == "<" and s.startswith("<<<", i):
            # a here-string: one operator word; the next word is lexed normally
            op = "<<<"
            j = i + 3
        else:
            op = c
            j = i + 1
            if c == ">" and j < n and s[j] in ">|":
                op += s[j]
                j += 1
            if j < n and s[j] == "&":
                op += "&"
                j += 1
                while j < n and (s[j].isdigit() or s[j] == "-"):
                    op += s[j]
                    j += 1
        self.t.append(op)
        self.l.append(op)
        self._end_word(j)
        return j

    # -- main loop ----------------------------------------------------------
    def run(self):
        s = self.s
        n = self.n
        while self.i < n:
            i = self.i
            c = s[i]
            m = _PLAIN.match(s, i)
            if m:
                self._begin(i)
                chunk = m.group(0)
                self.t.append(chunk)
                self.l.append(chunk)
                self.i = m.end()
                continue
            if c in " \t\r\f\v":
                self._end_word(i)
                self.i = i + 1
                continue
            if c == "\n":
                self._end_word(i)
                self._end_seg("\n")
                self.i = i + 1
                if self.pending:
                    self.i = self._heredocs(self.i)
                continue
            if c == "\\":
                if i + 1 < n:
                    d = s[i + 1]
                    if d == "\n":
                        self.i = i + 2
                        continue
                    self._begin(i)
                    self.t.append(d)
                    if d != "$":
                        self.l.append(d)
                    self.i = i + 2
                else:
                    self.i = i + 1
                continue
            if c == "'":
                k = s.find("'", i + 1)
                if k < 0:
                    raise ParseError("unterminated single quote")
                self._begin(i)
                self.t.append(s[i + 1:k])
                self.i = k + 1
                continue
            if c == '"':
                self._begin(i)
                self.i = i + 1
                text, live = self._dq()
                self.t.append(text)
                self.l.append(live)
                continue
            if c == "$":
                nxt = s[i + 1] if i + 1 < n else ""
                if nxt == "'":
                    # ANSI-C quoting: a backslash escapes the next character, quote included
                    k = _ansi_c_end(s, i + 1)
                    if k < 0:
                        raise ParseError("unterminated ANSI-C quote")
                    self._begin(i)
                    self.t.append(_ansi_c_text(s[i + 2:k]))
                    self.i = k + 1
                    continue
                if nxt == "(":
                    self._begin(i)
                    j = _match_paren(s, i + 2)
                    self._sub(s[i + 2:j])
                    self.t.append(s[i:j + 1])
                    self.l.append(s[i:j + 1])
                    self.i = j + 1
                    continue
                if nxt == "{":
                    self._begin(i)
                    j = _match_brace(s, i + 2)
                    self.t.append(s[i:j + 1])
                    self.l.append(s[i:j + 1])
                    self.i = j + 1
                    continue
                self._begin(i)
                self.t.append("$")
                self.l.append("$")
                self.i = i + 1
                continue
            if c == "`":
                j = s.find("`", i + 1)
                if j < 0:
                    j = n
                self._begin(i)
                self._sub(s[i + 1:j])
                self.t.append(s[i:j + 1])
                self.l.append(s[i:j + 1])
                self.i = j + 1
                continue
            if c == "#":
                if self.inw:
                    self.t.append("#")
                    self.l.append("#")
                    self.i = i + 1
                else:
                    k = s.find("\n", i)
                    self.i = n if k < 0 else k
                continue
            if c == "|":
                self._end_word(i)
                if i + 1 < n and s[i + 1] == "|":
                    self._end_seg("||")
                    self.i = i + 2
                elif i + 1 < n and s[i + 1] == "&":
                    self._end_seg("|&")
                    self.i = i + 2
                else:
                    self._end_seg("|")
                    self.i = i + 1
                continue
            if c == "&":
                nxt = s[i + 1] if i + 1 < n else ""
                if nxt == "&":
                    self._end_word(i)
                    self._end_seg("&&")
                    self.i = i + 2
                elif nxt == ">":
                    self._end_word(i)
                    j = i + 2
                    if j < n and s[j] == ">":
                        j += 1
                    self._begin(i)
                    self.t.append(s[i:j])
                    self.l.append(s[i:j])
                    self._end_word(j)
                    self.i = j
                else:
                    self._end_word(i)
                    self._end_seg("&")
                    self.i = i + 1
                continue
            if c == ";":
                self._end_word(i)
                self._end_seg(";")
                self.i = i + 1
                continue
            if c in "()":
                self._end_word(i)
                self._end_seg(c)
                self.i = i + 1
                continue
            if c in "<>":
                self.i = self._redirect(i)
                continue
            # anything else is an ordinary character
            self._begin(i)
            self.t.append(c)
            self.l.append(c)
            self.i = i + 1
        self._end_word(n)
        self._end_seg("")
        return self.segs + self.extras


def tokenize(cmd, nested=False, depth=0):
    """Return a list of Seg. Raises ParseError on an unterminated quote."""
    return _Lexer(cmd, nested, depth).run()


def crude_segments(cmd, nested=False, depth=0):
    """Fallback when the lexer gives up: split on separators, drop quote
    characters. Keeps deny patterns reachable instead of failing open."""
    segs = []
    for part in re.split(r"[;&|\n()`]+", cmd):
        words = []
        for tok in part.split():
            t = tok.strip("'\"")
            if t:
                words.append(Word(t, t, tok))
        if words:
            segs.append(Seg(words, "", "", nested, depth))
    return segs


def tokenize_safe(cmd, nested=False, depth=0):
    try:
        return tokenize(cmd, nested, depth)
    except ParseError:
        return crude_segments(cmd, nested, depth)
    except Exception:
        return crude_segments(cmd, nested, depth)


# -- wrappers and verbs ------------------------------------------------------

_ASSIGN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*\+?=")
_KEYWORDS = frozenset(
    ["if", "then", "else", "elif", "fi", "while", "until", "do", "done", "!", "{", "}"]
)
_SHELLS = frozenset(["bash", "sh", "zsh", "dash", "ksh"])
_GIT_ENV = re.compile(r"^(GIT_DIR|GIT_WORK_TREE)=(.*)$")
_REDIR_OP = re.compile(r"^\d*(?:<<<|&>>|&>|>>|>\||<|>)(&(?:\d+|-)?)?$")
# wrappers that run the rest of their arguments, with the options that take a value
_RUNNERS = {
    "xargs": (
        "-I", "-n", "-P", "-L", "-s", "-d", "-E", "-a", "-J", "-R", "-S",
        "--max-args", "--max-procs", "--delimiter", "--arg-file", "--max-lines", "--max-chars",
        "--eof", "--process-slot-var",
    ),
    "watch": ("-n", "--interval"),
    "caffeinate": ("-t", "-w"),
    "arch": ("-arch", "-e", "-d"),
}


def base(text):
    return os.path.basename(text) if "/" in text else text


def redirect_arity(text):
    """None when `text` is not a redirection operator word. 0 when the operator
    carries its own target (`2>&1`, `>&2`), 1 when the next word is the target."""
    m = _REDIR_OP.match(text)
    if not m:
        return None
    tail = m.group(1)
    return 0 if tail and len(tail) > 1 else 1


_BARE_VAR = re.compile(r"^\$(?:[A-Za-z_][A-Za-z0-9_]*|\{[A-Za-z_][A-Za-z0-9_]*\})$")


def _may_vanish(raw):
    """True for an unquoted word that is exactly one command substitution or one
    plain variable: the shell drops it when it expands to nothing."""
    if raw.startswith("$(") and raw.endswith(")") and _match_paren(raw, 2) == len(raw) - 1:
        return True
    if len(raw) > 1 and raw[0] == "`" and raw[-1] == "`" and "`" not in raw[1:-1]:
        return True
    return bool(_BARE_VAR.match(raw))


def unwrap(words, stop_at=()):
    """Drop leading VAR=val, sudo/env/command/time/nice/timeout wrappers and
    shell keywords. Returns the words from the real verb on. A query such as
    `command -v x` returns an empty list."""
    i = 0
    n = len(words)
    while i < n:
        t = words[i].text
        b = base(t)
        if b in stop_at:
            break
        if i + 1 < n and _may_vanish(words[i].raw):
            # an unquoted `$(true)` or `$EMPTY` in command position can expand to nothing,
            # and the shell then runs the next word as the verb
            i += 1
            continue
        ar = redirect_arity(t)
        if ar is not None:
            # a redirection written before the verb: `2>&1 git add -A`, `< f cat`
            i += 1
            if ar and i < n and redirect_arity(words[i].text) is None:
                i += 1
            continue
        if _ASSIGN.match(t):
            i += 1
            continue
        if t in _KEYWORDS:
            i += 1
            continue
        if t == "function":
            i += 2  # the keyword and the function's name
            continue
        if t == "coproc":
            i += 1
            continue
        if b in _RUNNERS:
            vals = _RUNNERS[b]
            i += 1
            while i < n and words[i].text.startswith("-") and len(words[i].text) > 1:
                o = words[i].text
                i += 1
                if o == "--":
                    break
                if o in vals and i < n:
                    i += 1
            continue
        if b in ("sudo", "doas"):
            i += 1
            while i < n and words[i].text.startswith("-"):
                o = words[i].text
                i += 1
                if o == "--":
                    break
                if o in ("-u", "-g", "-h", "-p", "-C", "-U", "-r", "-t", "-D", "-R", "-T") and i < n:
                    i += 1
            continue
        if b == "env":
            i += 1
            while i < n:
                o = words[i].text
                if o == "--":
                    i += 1
                    break
                if o.startswith("-") and len(o) > 1:
                    i += 1
                    if o in ("-u", "-C", "-S", "--unset", "--chdir") and i < n:
                        i += 1
                elif _ASSIGN.match(o):
                    i += 1
                else:
                    break
            continue
        if b in ("nice", "ionice"):
            i += 1
            while i < n and words[i].text.startswith("-"):
                o = words[i].text
                i += 1
                if o in ("-n", "-c", "-p") and i < n:
                    i += 1
            continue
        if b in ("time", "nohup", "exec", "setsid", "stdbuf"):
            i += 1
            while i < n and words[i].text.startswith("-"):
                i += 1
            continue
        if b in ("command", "builtin"):
            i += 1
            if i < n and words[i].text in ("-v", "-V"):
                return []
            if i < n and words[i].text == "-p":
                i += 1
            continue
        if b in ("timeout", "gtimeout"):
            i += 1
            while i < n and words[i].text.startswith("-"):
                o = words[i].text
                i += 1
                if o in ("-k", "-s") and i < n:
                    i += 1
            if i < n:
                i += 1  # the duration
            continue
        break
    return words[i:]


def verb(seg, stop_at=()):
    w = unwrap(seg.words, stop_at)
    return base(w[0].text) if w else ""


def parse_git(words):
    """words start at the `git` word. Returns (subcommand, rest, dirs, ambient).
    dirs: -C values in order. ambient: [(kind, value)] for --git-dir/--work-tree."""
    i = 1
    n = len(words)
    dirs = []
    ambient = []
    while i < n:
        t = words[i].text
        if t == "-C":
            if i + 1 < n:
                dirs.append(words[i + 1].text)
            i += 2
        elif t in ("-c", "--namespace", "--super-prefix", "--config-env"):
            i += 2
        elif t in ("--git-dir", "--work-tree"):
            ambient.append((t[2:], words[i + 1].text if i + 1 < n else ""))
            i += 2
        elif t.startswith("--git-dir=") or t.startswith("--work-tree="):
            name, _, val = t[2:].partition("=")
            ambient.append((name, val))
            i += 1
        elif t.startswith("-"):
            i += 1
        else:
            break
    if i >= n:
        return "", [], dirs, ambient
    return words[i].text, words[i + 1:], dirs, ambient


def git_of(seg):
    """If the segment runs git, return parse_git's tuple, else None."""
    w = unwrap(seg.words)
    if w and base(w[0].text) == "git":
        sub, rest, dirs, ambient = parse_git(w)
        ambient = list(ambient)
        for x in seg.words[:len(seg.words) - len(w)]:
            m = _GIT_ENV.match(x.text)
            if m:
                ambient.append(("git-dir" if m.group(1) == "GIT_DIR" else "work-tree", m.group(2)))
        return sub, rest, dirs, ambient
    return None


def shell_string(seg):
    """The command string of `bash -c '...'` / `eval ...`, or None."""
    w = unwrap(seg.words)
    if not w:
        return None
    b = base(w[0].text)
    if b == "eval":
        rest = [x.text for x in w[1:]]
        return " ".join(rest) if rest else None
    if b in _SHELLS:
        i = 1
        while i < len(w):
            t = w[i].text
            if t.startswith("-") and not t.startswith("--") and "c" in t[1:]:
                return w[i + 1].text if i + 1 < len(w) else None
            if not t.startswith("-"):
                return None
            i += 1
    return None


def exec_commands(seg):
    """The commands `find ... -exec CMD ... ;` (also -execdir, -ok, -okdir) would run."""
    w = unwrap(seg.words)
    if not w or base(w[0].text) != "find":
        return []
    out = []
    i = 1
    n = len(w)
    while i < n:
        if w[i].text in ("-exec", "-execdir", "-ok", "-okdir"):
            j = i + 1
            cur = []
            while j < n and w[j].text not in (";", "+"):
                cur.append(w[j])
                j += 1
            if cur:
                out.append(cur)
            i = j
        i += 1
    return out


def all_segments(cmd, max_segments=400):
    """Tokenize cmd and expand `bash -c` / `eval` strings one level at a time."""
    segs = tokenize_safe(cmd)
    i = 0
    while i < len(segs) and len(segs) < max_segments:
        seg = segs[i]
        i += 1
        if seg.depth >= _MAX_NEST:
            continue
        inner = shell_string(seg)
        if inner:
            segs.extend(tokenize_safe(inner, True, seg.depth + 1))
        for words in exec_commands(seg):
            segs.append(Seg(words, "", "", True, seg.depth + 1))
    return segs
