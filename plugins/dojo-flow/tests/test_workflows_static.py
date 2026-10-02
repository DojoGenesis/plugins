"""Static checks on the workflow files and the plugin's text: model rule, pure-literal meta, syntax, drift, vocabulary,
description budgets. Nothing here calls a model."""
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest

from wf_helpers import BUILD_JS, CONVERGE_JS, NODE, PLUGIN, SKIP_REASON, needs_node

FILES = {"build": BUILD_JS, "converge": CONVERGE_JS}
START = "==== DOJO-FLOW SHARED BLOCK START"
END = "==== DOJO-FLOW SHARED BLOCK END"
PROMISE = ("Parallel builds that stay independent: a contract gate, scouts on small models, builders in the middle, "
           "judges at the ends, and a scorecard that counts returns.")


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


# ---- a small JavaScript masker: comments, strings, template text and regex bodies become spaces -------------------

def mask_js(src):
    out = list(src)
    n = len(src)
    i = 0
    prev_sig = ""   # last significant (non-space, non-comment) character seen in code
    prev_word = ""  # last identifier, to tell `return /x/` from `a / b`

    def blank(a, b):
        for k in range(a, b):
            if out[k] != "\n":
                out[k] = " "

    def skip_template(j):
        # j points just after the opening backtick; returns index after the closing one. Expressions inside ${} are
        # code, so they are scanned by a nested pass.
        k = j
        while k < n:
            c = src[k]
            if c == "\\":
                blank(k, k + 2)
                k += 2
                continue
            if c == "`":
                return k + 1
            if c == "$" and k + 1 < n and src[k + 1] == "{":
                depth = 1
                m = k + 2
                while m < n and depth:
                    if src[m] == "{":
                        depth += 1
                    elif src[m] == "}":
                        depth -= 1
                    m += 1
                inner = mask_js(src[k + 2:m - 1])
                for t, ch in enumerate(inner):
                    out[k + 2 + t] = ch
                blank(k, k + 2)
                out[m - 1] = " "
                k = m
                continue
            blank(k, k + 1)
            k += 1
        return n

    while i < n:
        c = src[i]
        nxt = src[i + 1] if i + 1 < n else ""
        if c == "/" and nxt == "/":
            j = src.find("\n", i)
            j = n if j < 0 else j
            blank(i, j)
            i = j
            continue
        if c == "/" and nxt == "*":
            j = src.find("*/", i + 2)
            j = n if j < 0 else j + 2
            blank(i, j)
            i = j
            continue
        if c in "'\"":
            j = i + 1
            while j < n and src[j] != c:
                j += 2 if src[j] == "\\" else 1
            blank(i + 1, min(j, n))
            i = j + 1
            prev_sig, prev_word = c, ""
            continue
        if c == "`":
            i = skip_template(i + 1)
            prev_sig, prev_word = "`", ""
            continue
        if c == "/" and (prev_sig == "" or prev_sig in "(,=:[!&|?{};+-*%<>~^" or prev_word in ("return", "typeof", "case", "in", "of")):
            j = i + 1
            in_class = False
            while j < n and src[j] != "\n":
                ch = src[j]
                if ch == "\\":
                    j += 2
                    continue
                if ch == "[":
                    in_class = True
                elif ch == "]":
                    in_class = False
                elif ch == "/" and not in_class:
                    break
                j += 1
            blank(i + 1, min(j, n))
            i = j + 1
            prev_sig, prev_word = "/", ""
            continue
        if c.isalnum() or c in "_$":
            j = i
            while j < n and (src[j].isalnum() or src[j] in "_$"):
                j += 1
            prev_word = src[i:j]
            prev_sig = src[j - 1]
            i = j
            continue
        if not c.isspace():
            prev_sig, prev_word = c, ""
        i += 1
    return "".join(out)


def match_close(masked, open_idx):
    pairs = {"(": ")", "[": "]", "{": "}"}
    stack = []
    for k in range(open_idx, len(masked)):
        ch = masked[k]
        if ch in pairs:
            stack.append(pairs[ch])
        elif ch in ")]}":
            if not stack or stack.pop() != ch:
                return -1
            if not stack:
                return k
    return -1


def split_top(masked, start, end):
    """Split masked[start:end] at commas that sit at bracket depth 0."""
    parts, depth, last = [], 0, start
    for k in range(start, end):
        ch = masked[k]
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        elif ch == "," and depth == 0:
            parts.append(masked[last:k])
            last = k + 1
    parts.append(masked[last:end])
    return parts


def lint_agent_calls(src):
    """Return a list of problems with real agent( call sites: every one needs an options object with a model key."""
    masked = mask_js(src)
    problems = []
    for m in re.finditer(r"(?<![\w$.])agent\s*\(", masked):
        open_idx = masked.index("(", m.start())
        close = match_close(masked, open_idx)
        line = src.count("\n", 0, m.start()) + 1
        if close < 0:
            problems.append("line %d: unbalanced agent call" % line)
            continue
        args = split_top(masked, open_idx + 1, close)
        if len(args) < 2 or not args[1].strip().startswith("{"):
            problems.append("line %d: agent call has no options object" % line)
            continue
        body = args[1].strip()
        inner_start = open_idx + 1 + len(args[0]) + 1 + (len(args[1]) - len(args[1].lstrip())) + 1
        fields = split_top(masked, inner_start, inner_start + len(body) - 2)
        keyed = set()
        for f in fields:
            f = f.strip()
            if not f:
                continue
            if f.startswith("..."):
                problems.append("line %d: options use a spread" % line)
                continue
            km = re.match(r"([A-Za-z_$][\w$]*)\s*:", f)
            if km:
                keyed.add(km.group(1))
            elif re.match(r"^[A-Za-z_$][\w$]*$", f):
                problems.append("line %d: shorthand option %s" % (line, f))
        if "model" not in keyed:
            problems.append("line %d: agent call has no model: key" % line)
    return problems


# ---- a mini parser for a pure-literal object -------------------------------------------------------------------

class NotLiteral(Exception):
    pass


def parse_literal(text, i=0):
    """Parse a JS literal made only of objects, arrays, plain quoted strings, numbers, true/false/null.
    Returns (value, next index)."""
    def skip(j):
        while j < len(text):
            if text[j].isspace():
                j += 1
            elif text.startswith("//", j):
                j = text.find("\n", j)
                j = len(text) if j < 0 else j
            elif text.startswith("/*", j):
                j = text.find("*/", j) + 2
            else:
                break
        return j

    def value(j):
        j = skip(j)
        c = text[j]
        if c == "{":
            obj, j = {}, skip(j + 1)
            while text[j] != "}":
                if text.startswith("...", j):
                    raise NotLiteral("spread")
                if text[j] == "[":
                    raise NotLiteral("computed key")
                if text[j] in "'\"":
                    key, j = string(j)
                else:
                    km = re.match(r"[A-Za-z_$][\w$]*", text[j:])
                    if not km:
                        raise NotLiteral("bad key at %d" % j)
                    key, j = km.group(0), j + km.end()
                j = skip(j)
                if text[j] != ":":
                    raise NotLiteral("expected a colon (shorthand or method?) at %d" % j)
                obj[key], j = value(j + 1)
                j = skip(j)
                if text[j] == ",":
                    j = skip(j + 1)
                elif text[j] != "}":
                    raise NotLiteral("expected , or } at %d (%r)" % (j, text[j]))
            return obj, j + 1
        if c == "[":
            arr, j = [], skip(j + 1)
            while text[j] != "]":
                v, j = value(j)
                arr.append(v)
                j = skip(j)
                if text[j] == ",":
                    j = skip(j + 1)
                elif text[j] != "]":
                    raise NotLiteral("expected , or ] at %d" % j)
            return arr, j + 1
        if c in "'\"":
            s, j = string(j)
            j2 = skip(j)
            if j2 < len(text) and text[j2] in "+":
                raise NotLiteral("string concatenation")
            return s, j
        if c == "`":
            raise NotLiteral("template literal")
        nm = re.match(r"-?\d+(\.\d+)?", text[j:])
        if nm:
            return float(nm.group(0)), j + nm.end()
        for word, val in (("true", True), ("false", False), ("null", None)):
            if text.startswith(word, j) and not re.match(r"[\w$]", text[j + len(word):j + len(word) + 1] or " "):
                return val, j + len(word)
        raise NotLiteral("not a literal at %d (%r)" % (j, text[j:j + 12]))

    def string(j):
        q = text[j]
        k = j + 1
        buf = []
        while text[k] != q:
            if text[k] == "\\":
                buf.append(text[k + 1])
                k += 2
            else:
                buf.append(text[k])
                k += 1
        return "".join(buf), k + 1

    return value(i)


def meta_of(src):
    m = re.search(r"export const meta\s*=\s*", src)
    if not m:
        raise NotLiteral("no export const meta")
    value, _ = parse_literal(src, m.end())
    return value


def wrapped_for_check(src):
    body = re.sub(r"^export const meta = ", "const meta = ", src, flags=re.M)
    return "(async function (agent, parallel, pipeline, phase, log, args, budget) {\n" + body + "\n})\n"


class ModelRuleTests(unittest.TestCase):
    def test_every_real_agent_call_sets_a_model(self):
        for name, path in FILES.items():
            self.assertEqual(lint_agent_calls(read(path)), [], name)

    def test_the_naive_count_agrees(self):
        # Simpler linters count `agent(` and `model:` anywhere. This only works because the literal `agent(` appears at
        # real call sites only (no comments, prompts or log text), `model:` appears only in the options object of
        # those calls, and helper definitions do not use the name. The check excludes helpers like `async function`
        # because none are named agent.
        for name, path in FILES.items():
            src = read(path)
            self.assertEqual(src.count("agent("), src.count("model:"), name)
            self.assertGreaterEqual(src.count("agent("), 1, name)

    def test_there_is_one_call_site_and_it_sits_inside_the_counting_wrapper(self):
        for name, path in FILES.items():
            src = read(path)
            self.assertEqual(src.count("agent("), 1, name)
            call = src.index("agent(")
            wrapper = src.index("async function spawn(")
            end_of_runner = src.index("function snapshot()")
            self.assertTrue(wrapper < call < end_of_runner, name)

    def test_no_schema_property_is_named_model(self):
        for name, path in FILES.items():
            self.assertIsNone(re.search(r"\bmodel\s*:\s*\{\s*type", read(path)), name)

    def test_the_lint_catches_the_adversarial_fixtures(self):
        bad = {
            "prompt text says model: opus but the options have none":
                "await agent('please use model: opus', { label: 'x', schema: S })",
            "spread options": "await agent(p, { ...o })",
            "shorthand model": "const model = 'opus'; await agent(p, { label: 'x', model })",
            "no options at all": "await agent(p)",
            "model only inside a template": "await agent(`model: opus`, { label: 'x' })",
            "model only in a comment": "await agent(p, { label: 'x' /* model: opus */ })",
        }
        for why, src in bad.items():
            self.assertNotEqual(lint_agent_calls(src), [], why)

    def test_the_lint_accepts_hard_cases(self):
        good = [
            "await agent('it\\'s (tricky) )) text', { label: 'x', model: 'haiku', schema: S })",
            "await agent(\"a ) b ( c\", { label: f(1, 2), phase: 'P', model: pick[0], effort: e })",
            "// agent( in a comment\nconst s = 'agent( in a string'\nawait agent(p, { model: m })",
            "await agent(a + `x ${f(')')}`, { model: m, schema: { type: 'object' } })",
        ]
        for src in good:
            self.assertEqual(lint_agent_calls(src), [], src)

    def test_the_mask_survives_regex_literals(self):
        src = "const r = /['\"`]agent\\(/g\nawait agent(p, { model: m })"
        self.assertEqual(lint_agent_calls(src), [])


class MetaTests(unittest.TestCase):
    def test_meta_is_a_pure_literal_with_the_right_names(self):
        want = {"build": "build", "converge": "converge"}
        for name, path in FILES.items():
            meta = meta_of(read(path))
            self.assertEqual(meta["name"], want[name])
            self.assertTrue(meta["description"])
            self.assertTrue(meta["phases"])
            for ph in meta["phases"]:
                self.assertIn("title", ph)
                self.assertNotIn("model", ph, "put the tier in detail text, not in a model field")

    def test_phase_titles_match_the_script(self):
        for name, path in FILES.items():
            src = read(path)
            titles = [p["title"] for p in meta_of(src)["phases"]]
            masked_head = src[src.index("export const meta"):]
            body = src[src.index("\n}\n", src.index("export const meta")) + 3:]
            called = re.findall(r"phase\('([^']+)'\)", body)
            for c in called:
                self.assertIn(c, titles, "%s: phase('%s') has no meta entry" % (name, c))
            for t in titles:
                self.assertIn("'" + t + "'", body, "%s: meta phase %s is never used in the script" % (name, t))

    def test_the_parser_rejects_impure_meta(self):
        bad = {
            "template literal": "export const meta = { name: `x`, description: 'd' }",
            "variable": "export const meta = { name: NAME, description: 'd' }",
            "function call": "export const meta = { name: String('x'), description: 'd' }",
            "spread": "export const meta = { ...base, name: 'x' }",
            "computed key": "export const meta = { ['na' + 'me']: 'x' }",
            "concatenation": "export const meta = { name: 'a' + 'b', description: 'd' }",
            "shorthand": "export const meta = { name, description: 'd' }",
        }
        for why, src in bad.items():
            with self.assertRaises(NotLiteral, msg=why):
                meta_of(src)

    def test_the_parser_accepts_a_good_one(self):
        good = "export const meta = { name: 'x', description: 'd', phases: [{ title: 'A', detail: 'b' },], }"
        self.assertEqual(meta_of(good)["phases"][0]["title"], "A")


class NondeterminismTests(unittest.TestCase):
    def test_no_clock_or_randomness(self):
        for name, path in FILES.items():
            masked = mask_js(read(path))
            self.assertNotIn("Date.now", masked, name)
            self.assertNotIn("Math.random", masked, name)
            self.assertIsNone(re.search(r"new\s+Date\s*\(\s*\)", masked), name)


class SyntaxAndDriftTests(unittest.TestCase):
    @needs_node
    def test_node_check_on_a_wrapped_temp_copy(self):
        for name, path in FILES.items():
            with tempfile.TemporaryDirectory(prefix="dojo-flow-check-") as tmp:
                copy = os.path.join(tmp, name + ".js")
                with open(copy, "w", encoding="utf-8") as fh:
                    fh.write(wrapped_for_check(read(path)))
                self.assertTrue(copy.startswith(tempfile.gettempdir()) or copy.startswith(os.path.realpath(tempfile.gettempdir())))
                proc = subprocess.run([NODE, "--check", copy], stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
                self.assertEqual(proc.returncode, 0, "%s: %s" % (name, proc.stderr))
            self.assertFalse(os.path.exists(tmp), "the temp copy was not removed")

    def test_the_check_would_fail_on_a_syntax_error(self):
        if not NODE:
            self.skipTest(SKIP_REASON)
        with tempfile.TemporaryDirectory(prefix="dojo-flow-check-") as tmp:
            copy = os.path.join(tmp, "bad.js")
            with open(copy, "w", encoding="utf-8") as fh:
                fh.write(wrapped_for_check("export const meta = {}\nconst x = (1 + ;\n"))
            proc = subprocess.run([NODE, "--check", copy], stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            self.assertNotEqual(proc.returncode, 0)

    def test_the_shared_block_is_identical_in_both_files(self):
        blocks = []
        for path in FILES.values():
            src = read(path)
            self.assertEqual(src.count(START), 1)
            self.assertEqual(src.count(END), 1)
            blocks.append(src[src.index(START):src.index(END)])
        self.assertEqual(blocks[0], blocks[1])
        self.assertGreater(len(blocks[0]), 2000)


class VocabularyTests(unittest.TestCase):
    def test_banned_public_words_are_absent(self):
        # Built from fragments so the literals never appear on disk.
        words = ["ecosys" + "tem", "opti" + "mize", "lever" + "age", "power" + "ful", "super" + "charge", "seam" + "less",
                 "che" + "ap", "plat" + "form", "out of the " + "box"]
        savings = re.compile(r"\bsave\s+\d+\s*%", re.I)
        hits = []
        for root, dirs, files in os.walk(PLUGIN):
            dirs[:] = [d for d in dirs if d not in (".git", "__pycache__", "node_modules")]
            for f in files:
                if f.endswith((".pyc",)):
                    continue
                path = os.path.join(root, f)
                try:
                    text = read(path).lower()
                except (UnicodeDecodeError, OSError):
                    continue
                for w in words:
                    if w in text:
                        hits.append("%s contains a banned word (#%d)" % (os.path.relpath(path, PLUGIN), words.index(w)))
                if savings.search(text):
                    hits.append("%s promises a saving" % os.path.relpath(path, PLUGIN))
        self.assertEqual(hits, [])

    def test_no_full_model_ids_in_public_text(self):
        pat = re.compile(r"claude-(opus|sonnet|haiku|fable)-\d")
        for root, dirs, files in os.walk(PLUGIN):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for f in files:
                if f.endswith(".pyc"):
                    continue
                self.assertIsNone(pat.search(read(os.path.join(root, f))), f)

    def test_no_numbers_from_origin_stories_or_cost_claims(self):
        text = read(os.path.join(PLUGIN, "README.md")) + read(os.path.join(PLUGIN, "skills", "dag-plan", "SKILL.md"))
        self.assertIsNone(re.search(r"\$\s?\d", text))
        self.assertIsNone(re.search(r"\d+\s*(%|percent)", text))


def frontmatter(path):
    text = read(path)
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    if not m:
        raise AssertionError("no frontmatter in " + path)
    fields = {}
    for line in m.group(1).splitlines():
        km = re.match(r"^([A-Za-z-]+):\s*(.*)$", line)
        if not km:
            raise AssertionError("unparseable frontmatter line in %s: %r" % (path, line))
        v = km.group(2).strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in "'\"":
            v = v[1:-1]
        fields[km.group(1)] = v
    return fields, m.group(2)


class ManifestTests(unittest.TestCase):
    def test_plugin_json(self):
        with open(os.path.join(PLUGIN, ".claude-plugin", "plugin.json"), encoding="utf-8") as fh:
            pj = json.load(fh)
        self.assertEqual(pj["name"], "dojo-flow")
        self.assertEqual(pj["version"], "0.1.0")
        self.assertEqual(pj["description"], PROMISE)
        self.assertLessEqual(len(pj["description"]), 200)
        self.assertEqual(pj["author"], {"name": "Dojo Genesis", "email": "cruz@trespiesdesign.com"})
        self.assertEqual(pj["homepage"], "https://dojogenesis.com/suite#dojo-flow")
        self.assertEqual(pj["repository"], "https://github.com/DojoGenesis/plugins")
        self.assertEqual(pj["license"], "Apache-2.0")
        self.assertNotIn("hooks", pj)

    def test_no_hooks_and_no_agents_are_shipped(self):
        self.assertFalse(os.path.exists(os.path.join(PLUGIN, "hooks")))
        self.assertFalse(os.path.exists(os.path.join(PLUGIN, "agents")))

    def test_description_budgets(self):
        total = 0
        for cmd in ("build", "converge"):
            fields, body = frontmatter(os.path.join(PLUGIN, "commands", cmd + ".md"))
            self.assertLessEqual(len(fields["description"]), 200, cmd)
            self.assertIn("allowed-tools", fields)
            self.assertNotIn("Workflow", fields["allowed-tools"], "leave Workflow out so Claude Code asks before a run")
            self.assertNotIn("Write", fields["allowed-tools"])
            self.assertNotRegex(fields["allowed-tools"], r"(^|,\s*)Bash(\s*,|\s*$)")
            total += len(fields["description"])
            self.assertIn("Workflow tool", body)
            self.assertIn("scriptPath", body)
            self.assertIn("${CLAUDE_PLUGIN_ROOT}/workflows/%s.js" % cmd, body)
        fields, body = frontmatter(os.path.join(PLUGIN, "skills", "dag-plan", "SKILL.md"))
        self.assertEqual(fields["name"], "dag-plan")
        self.assertLessEqual(len(fields["description"]), 250)
        self.assertRegex(fields["description"], r"^(Use when|[A-Z][a-z]+ )")
        self.assertLessEqual(len(body.encode("utf-8")), 6 * 1024)
        total += len(fields["description"])
        self.assertLess(total, 1000)

    def test_build_command_does_not_promise_ordering_the_workflow_lacks(self):
        body = read(os.path.join(PLUGIN, "commands", "build.md"))
        src = read(BUILD_JS)
        self.assertNotIn("accept the chain", body)
        self.assertNotRegex(body, r"merge them or order them")
        self.assertIn("does not order tracks", body)
        # build.js never reads deps, so it must not ask the contract subagent for them or accept them in a schema
        self.assertNotRegex(src, r"\bdeps\b")

    def test_readme_carries_the_required_statements(self):
        text = read(os.path.join(PLUGIN, "README.md"))
        self.assertIn("/plugin install dojo-flow@dojo-genesis", text)
        self.assertIn("Tested with Claude Code 2.1.286", text)
        self.assertIn("all three tiers", text)
        self.assertIn("reported by subagents", text)
        self.assertIn("not yet measured", text.lower())

    def test_python_files_compile_under_the_system_python(self):
        py = "/usr/bin/python3"
        if not os.path.exists(py):
            self.skipTest("no /usr/bin/python3 on this machine")
        for folder in ("scripts", "tests"):
            for f in os.listdir(os.path.join(PLUGIN, folder)):
                if f.endswith(".py"):
                    proc = subprocess.run([py, "-m", "py_compile", os.path.join(PLUGIN, folder, f)], stdout=subprocess.PIPE,
                                          stderr=subprocess.PIPE, universal_newlines=True, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
                    self.assertEqual(proc.returncode, 0, "%s: %s" % (f, proc.stderr))


if __name__ == "__main__":
    unittest.main()
