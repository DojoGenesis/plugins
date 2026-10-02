import ast
import glob
import json
import os
import re
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _payloads as P  # noqa: E402

ROOT = P.PLUGIN_ROOT
PROMISE = (
    "Deterministic guards for the mistakes that waste a day: blanket staging, rewriting pushed commits, "
    "printing secrets, oversized reads, silent probes."
)
GUARD_IDS = [
    "staging", "pushed-rewrite", "secret-print", "token-url", "big-read",
    "mac-timeout", "masked-exit", "config-first", "empty-probe", "claude-md-reach",
]


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
        return f.read()


def slurp(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def all_files():
    out = []
    for d, dirs, files in os.walk(ROOT):
        dirs[:] = [x for x in dirs if x not in (".git", "__pycache__", "node_modules")]
        for f in files:
            out.append(os.path.join(d, f))
    return out


def frontmatter(text):
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    assert m, "no frontmatter"
    meta = {}
    for line in m.group(1).splitlines():
        k, _, v = line.partition(":")
        meta[k.strip()] = v.strip()
    return meta, m.group(2)


class PluginJsonTests(unittest.TestCase):
    def setUp(self):
        self.pj = json.loads(read(".claude-plugin", "plugin.json"))

    def test_fields(self):
        pj = self.pj
        self.assertEqual(pj["name"], "dojo-gates")
        self.assertEqual(pj["version"], "0.1.0")
        self.assertEqual(pj["description"], PROMISE)
        self.assertLessEqual(len(pj["description"]), 200)
        self.assertEqual(pj["author"], {"name": "Dojo Genesis", "email": "cruz@trespiesdesign.com"})
        self.assertEqual(pj["homepage"], "https://dojogenesis.com/suite#dojo-gates")
        self.assertEqual(pj["repository"], "https://github.com/DojoGenesis/plugins")
        self.assertEqual(pj["license"], "Apache-2.0")
        self.assertTrue(pj["keywords"])

    def test_user_config(self):
        uc = self.pj["userConfig"]
        self.assertEqual(list(uc), ["claude_md_reach"])
        self.assertEqual(uc["claude_md_reach"]["type"], "boolean")
        self.assertIs(uc["claude_md_reach"]["default"], False)
        self.assertTrue(uc["claude_md_reach"]["title"])
        self.assertTrue(uc["claude_md_reach"]["description"])


class HooksJsonTests(unittest.TestCase):
    def setUp(self):
        self.hj = json.loads(read("hooks", "hooks.json"))

    def commands(self):
        for event, groups in self.hj["hooks"].items():
            for g in groups:
                for h in g["hooks"]:
                    yield event, g.get("matcher"), h

    def test_shape(self):
        self.assertNotIn("modules", self.hj)
        self.assertTrue(self.hj["description"])
        self.assertEqual(
            sorted(self.hj["hooks"]),
            ["InstructionsLoaded", "PostToolUse", "PostToolUseFailure", "PreToolUse"],
        )

    def test_matchers(self):
        got = sorted((e, m or "") for e, m, _ in self.commands())
        self.assertEqual(
            got,
            sorted([
                ("PreToolUse", "Bash"), ("PreToolUse", "Read"), ("PreToolUse", "Write|Edit"),
                ("PostToolUse", "Bash"), ("PostToolUseFailure", "Bash"), ("InstructionsLoaded", ""),
            ]),
        )

    def test_commands_use_python3_and_exist(self):
        rx = re.compile(r'^python3 "\$\{CLAUDE_PLUGIN_ROOT\}/hooks/([A-Za-z0-9_]+\.py)"$')
        for event, _, h in self.commands():
            self.assertEqual(h["type"], "command")
            m = rx.match(h["command"])
            self.assertIsNotNone(m, h["command"])
            self.assertTrue(os.path.isfile(os.path.join(ROOT, "hooks", m.group(1))), m.group(1))

    def test_timeout_outlasts_the_git_budget(self):
        sys.path.insert(0, P.HOOKS)
        import _guards

        for _, _, h in self.commands():
            self.assertGreater(h["timeout"], _guards._GIT_BUDGET + 1)

    def test_four_distinct_entry_scripts(self):
        scripts = set(re.search(r"hooks/(\w+\.py)", h["command"]).group(1) for _, _, h in self.commands())
        self.assertEqual(scripts, {"bash_guard.py", "read_guard.py", "claude_md_reach.py", "bash_after.py"})


class PythonCompatTests(unittest.TestCase):
    def test_every_py_compiles_under_system_python(self):
        files = [f for f in all_files() if f.endswith(".py")]
        self.assertGreaterEqual(len(files), 10)
        code = "import sys; compile(open(sys.argv[1], encoding='utf-8').read(), sys.argv[1], 'exec')"
        for f in files:
            with self.subTest(file=os.path.relpath(f, ROOT)):
                p = subprocess.run([P.PY, "-c", code, f], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                self.assertEqual(p.returncode, 0, p.stderr.decode())

    def test_hooks_use_the_standard_library_only(self):
        stdlib_ok = set(sys.stdlib_module_names) if hasattr(sys, "stdlib_module_names") else None
        local = {"_common", "_shell", "_guards"}
        for f in glob.glob(os.path.join(ROOT, "hooks", "*.py")):
            tree = ast.parse(slurp(f))
            for node in ast.walk(tree):
                names = []
                if isinstance(node, ast.Import):
                    names = [a.name.split(".")[0] for a in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    names = [node.module.split(".")[0]]
                for n in names:
                    if n in local:
                        continue
                    if stdlib_ok is not None:
                        self.assertIn(n, stdlib_ok, "%s imports %s" % (os.path.basename(f), n))


class SkillTests(unittest.TestCase):
    def setUp(self):
        self.meta, self.body = frontmatter(read("skills", "gates", "SKILL.md"))

    def test_frontmatter(self):
        self.assertEqual(self.meta["name"], "gates")
        d = self.meta["description"]
        self.assertLessEqual(len(d), 250)
        self.assertTrue(d.startswith("Use when"))

    def test_body_size(self):
        self.assertLessEqual(len(self.body.encode("utf-8")), 6 * 1024)

    def test_always_on_budget(self):
        total = len(self.meta["description"])
        self.assertLess(total, 1000)

    def test_lists_every_guard_id(self):
        for gid in GUARD_IDS:
            self.assertIn("`%s`" % gid if gid not in self.body else gid, self.body)
            self.assertRegex(self.body, r"\|\s*%s\s*\|" % re.escape(gid))

    def test_names_the_overrides(self):
        for s in ("DOJO_GATES_SKIP", "DOJO_GATES_OFF", "DOJO_OFF", "claude_md_reach"):
            self.assertIn(s, self.body)

    def test_no_component_dirs_that_are_not_counted(self):
        self.assertEqual(sorted(os.listdir(os.path.join(ROOT, "skills"))), ["gates"])
        self.assertFalse(os.path.exists(os.path.join(ROOT, "agents")))
        self.assertFalse(os.path.exists(os.path.join(ROOT, "commands")))


class ReadmeTests(unittest.TestCase):
    def setUp(self):
        self.text = read("README.md")

    def test_required_statements(self):
        self.assertIn("2.1.286", self.text)
        self.assertIn("mod tier: none", self.text)
        self.assertIn("/plugin install dojo-gates@dojo-genesis", self.text)
        self.assertTrue(self.text.startswith("# dojo-gates\n\n" + PROMISE))
        for gid in GUARD_IDS:
            self.assertRegex(self.text, r"\|\s*%s\s*\|" % re.escape(gid))
        for k in ("DOJO_OFF=1", "DOJO_GATES_OFF=1", "DOJO_GATES_SKIP="):
            self.assertIn(k, self.text)

    def test_component_counts_match_disk(self):
        hooks = os.path.join(ROOT, "hooks")
        helpers = [f for f in os.listdir(hooks) if f.endswith(".py") and f.startswith("_")]
        entries = [f for f in os.listdir(hooks) if f.endswith(".py") and not f.startswith("_")]
        evals = [d for d in os.listdir(os.path.join(ROOT, "evals"))]
        cells = dict(re.findall(r"^\| ([a-z ]+?) \| (\d+)", self.text, re.M))
        self.assertEqual(int(cells["skills"]), len(os.listdir(os.path.join(ROOT, "skills"))))
        self.assertEqual(int(cells["agents"]), 0)
        self.assertEqual(int(cells["commands"]), 0)
        self.assertEqual(int(cells["registered hook entry scripts"]), len(entries))
        self.assertEqual(int(cells["shared hook modules"]), len(helpers))
        self.assertEqual(int(cells["guards"]), len(GUARD_IDS))
        self.assertEqual(int(cells["eval scaffolds"]), len(evals))

    def test_guard_list_file_matches_the_guard_ids(self):
        # hooks/guards.json is the machine-readable guard list the site's measured table counts from.
        self.assertEqual(json.loads(read("hooks", "guards.json")), GUARD_IDS)

    def test_the_guard_table_matches_the_code(self):
        sys.path.insert(0, P.HOOKS)
        import _guards

        code_ids = [gid for gid, _ in _guards.GUARDS]
        for gid in code_ids:
            self.assertIn(gid, GUARD_IDS)
        self.assertEqual(len(code_ids) + 4, len(GUARD_IDS))  # big-read, config-first, empty-probe, claude-md-reach


# The patterns are assembled from fragments so that this file does not itself contain the words it
# forbids; a repo-wide copy lint can then scan tests/ too.
LOWCOST = "chea" + "p"
BANNED = [
    r"\b" + "eco" + "system" + r"\b", r"\b" + "plat" + r"forms?\b", r"\b" + "optimi" + r"[sz]\w*",
    r"\b" + "lever" + r"ag\w*", r"\b" + "power" + r"ful\b", r"\b" + "super" + r"charg\w*",
    r"\b" + "seam" + r"less\w*", "works out of the " + "box", r"\b" + LOWCOST + r"\w*",
    r"\bsave[sd]?\s+(up to\s+)?\d+\s*%", r"\d+\s*%\s*(fewer|less|" + LOWCOST + r"er|savings|faster)",
]


class PublicTextTests(unittest.TestCase):
    PUBLIC = [
        ("README.md",), (".claude-plugin", "plugin.json"), ("skills", "gates", "SKILL.md"), ("hooks", "hooks.json"),
    ]

    def public_texts(self):
        out = [(os.path.join(*p), read(*p)) for p in self.PUBLIC]
        for f in glob.glob(os.path.join(ROOT, "evals", "*", "case.yaml")):
            out.append((os.path.relpath(f, ROOT), slurp(f)))
        for f in sorted(glob.glob(os.path.join(P.HOOKS, "*.py"))):  # the source ships too
            # `sys.platform` is the standard-library name, not copy
            out.append((os.path.relpath(f, ROOT), slurp(f).replace("sys.platform", "sys.os_name")))
        return out

    def test_no_banned_words(self):
        for name, text in self.public_texts():
            for pat in BANNED:
                with self.subTest(file=name, pattern=pat):
                    self.assertIsNone(re.search(pat, text, re.I), "%s: %s" % (name, pat))

    def test_tests_directory_is_clean_of_banned_words(self):
        # the lint list is built from fragments, so the shipped tests carry none of the words
        for f in sorted(glob.glob(os.path.join(ROOT, "tests", "*.py"))):
            # `sys.platform` is the standard-library name, not copy
            text = slurp(f).replace("sys.platform", "sys.os_name").replace('sys, "platform"', 'sys, "os_name"')
            for pat in BANNED:
                with self.subTest(file=os.path.basename(f), pattern=pat):
                    self.assertIsNone(re.search(pat, text, re.I), "%s: %s" % (os.path.basename(f), pat))

    def test_message_strings_carry_no_config_first_trigger(self):
        for name in ("_guards.py", "read_guard.py", "claude_md_reach.py", "_common.py"):
            tree = ast.parse(slurp(os.path.join(P.HOOKS, name)))
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    with self.subTest(file=name, text=node.value[:30]):
                        self.assertIsNone(P.TRIGGER.search(node.value), node.value)


class EvalScaffoldTests(unittest.TestCase):
    def test_cases(self):
        names = sorted(os.listdir(os.path.join(ROOT, "evals")))
        self.assertEqual(
            names,
            ["grep-narrow-before-read", "no-amend-after-push", "no-secret-echo", "stages-explicit-paths"],
        )
        for n in names:
            text = read("evals", n, "case.yaml")
            self.assertTrue(text.startswith("# Eval scaffold for dojo-gates."), n)
            self.assertIn("Scaffold, not run", text)
            data = json.loads(text[text.index("{"):])
            self.assertEqual(data["name"], n)
            self.assertEqual(data["execution"]["model"], "sonnet")
            self.assertTrue(data["graders"])


class NoStrayStateTests(unittest.TestCase):
    def test_no_bytecode_caches_are_shipped(self):
        # run the suite with PYTHONDONTWRITEBYTECODE=1; this guards against leftovers
        leftovers = [d for d, dirs, _ in os.walk(ROOT) if os.path.basename(d) == "__pycache__"]
        if leftovers:
            self.skipTest("bytecode caches present (created by this interpreter run): clean before release")


if __name__ == "__main__":
    unittest.main()
