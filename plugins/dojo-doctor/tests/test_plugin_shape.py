"""Static checks on the plugin itself: manifest, frontmatter limits, always-on budget, compile, public wording.

Private-reference scanning is not done here: it lives in the suite's central scanner, so no list of names is
kept in this plugin.
"""
import sys

sys.dont_write_bytecode = True

import ast
import json
import os
import py_compile
import re
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(HERE)
SYSTEM_PYTHON = "/usr/bin/python3"
PROMISE = (
    "Find the hooks and settings that fail or cost you silently: broken interpreters, "
    "noisy injections, always-on token weight, flags that are off."
)
SELF = os.path.abspath(__file__)


def plugin_files(suffixes=(".py", ".md", ".json")):
    for dirpath, dirnames, filenames in os.walk(PLUGIN):
        dirnames[:] = [d for d in dirnames if d not in ("__pycache__", ".git")]
        for fn in filenames:
            p = os.path.join(dirpath, fn)
            if fn.endswith(suffixes):
                yield p


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def split_frontmatter(text):
    assert text.startswith("---\n"), "no frontmatter"
    end = text.index("\n---", 4)
    return text[4:end], text[end + 4:].lstrip("\n")


def fm_value(fm, key):
    """Value of a one-line `key: value` entry; surrounding quotes removed."""
    m = re.search(r"(?m)^%s:\s*(.*)$" % re.escape(key), fm)
    assert m, "missing %s" % key
    v = m.group(1).strip()
    if v[:1] in ('"', "'") and v[-1:] == v[:1]:
        v = v[1:-1]
    return v


class ManifestTests(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads(read(os.path.join(PLUGIN, ".claude-plugin", "plugin.json")))

    def test_required_fields(self):
        m = self.manifest
        self.assertEqual(m["name"], "dojo-doctor")
        self.assertRegex(m["version"], r"^\d+\.\d+\.\d+$")
        self.assertEqual(m["version"], "0.1.0")
        self.assertEqual(m["author"], {"name": "Dojo Genesis", "email": "cruz@trespiesdesign.com"})
        self.assertEqual(m["homepage"], "https://dojogenesis.com/suite#dojo-doctor")
        self.assertEqual(m["repository"], "https://github.com/DojoGenesis/plugins")
        self.assertEqual(m["license"], "Apache-2.0")
        self.assertTrue(m["keywords"])

    def test_description_is_the_promise_verbatim_and_short(self):
        self.assertEqual(self.manifest["description"], PROMISE)
        self.assertLessEqual(len(self.manifest["description"]), 200)

    def test_no_hooks_and_no_mod_ship_in_this_plugin(self):
        self.assertFalse(os.path.exists(os.path.join(PLUGIN, "hooks")))
        self.assertNotIn("hooks", self.manifest)
        self.assertNotIn("userConfig", self.manifest)


class FrontmatterTests(unittest.TestCase):
    def setUp(self):
        self.skill = read(os.path.join(PLUGIN, "skills", "doctor", "SKILL.md"))
        self.command = read(os.path.join(PLUGIN, "commands", "check.md"))
        self.skill_fm, self.skill_body = split_frontmatter(self.skill)
        self.cmd_fm, self.cmd_body = split_frontmatter(self.command)

    def test_skill(self):
        desc = fm_value(self.skill_fm, "description")
        self.assertEqual(fm_value(self.skill_fm, "name"), "doctor")
        self.assertLessEqual(len(desc), 250)
        self.assertTrue(desc.startswith("Use when"), desc)
        self.assertLessEqual(len(self.skill_body.encode("utf-8")), 6 * 1024)

    def test_command(self):
        desc = fm_value(self.cmd_fm, "description")
        self.assertLessEqual(len(desc), 200)
        self.assertNotRegex(desc, r":(\s|$)", "keep a colon-space out of the description so no parser can misread it")
        self.assertNotIn('"', desc)
        self.assertEqual(fm_value(self.cmd_fm, "allowed-tools"), "Bash(python3:*)")
        self.assertIn("argument-hint", self.cmd_fm)

    def test_the_injected_line_is_the_script_call_without_typed_arguments(self):
        """$ARGUMENTS is substituted without shell escaping, so free text would break the shell line."""
        self.assertIn('!`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/doctor.py"`', self.cmd_body.splitlines())
        for line in self.cmd_body.splitlines():
            if line.startswith("!`"):
                self.assertNotIn("$ARGUMENTS", line)

    def test_frontmatter_values_with_a_colon_and_space_are_quoted(self):
        """An unquoted ': ' inside a value is invalid YAML (a nested mapping)."""
        for path in (
            os.path.join(PLUGIN, "commands", "check.md"),
            os.path.join(PLUGIN, "skills", "doctor", "SKILL.md"),
        ):
            fm, _ = split_frontmatter(read(path))
            for line in fm.splitlines():
                m = re.match(r"^([A-Za-z][A-Za-z0-9_-]*):\s+(.*)$", line)
                if not m:
                    continue
                value = m.group(2).strip()
                if value[:1] in ('"', "'", "[", "{", "|", ">"):
                    continue
                self.assertNotRegex(value, r":(\s|$)", "%s: unquoted ': ' in %s" % (os.path.basename(path), m.group(1)))

    def test_the_frontmatter_check_can_see_a_known_positive(self):
        value = "Check things: one, two."
        self.assertRegex(value, r":(\s|$)")

    def test_no_placeholder_paths_in_the_readme(self):
        """The release lint rejects a plugin-root path that continues with a placeholder; a generic
        path/to stand-in reads the same way, so the README uses a concrete invented name instead."""
        readme = read(os.path.join(PLUGIN, "README.md"))
        self.assertNotRegex(readme, r"\$\{CLAUDE_PLUGIN_ROOT\}/[^\s\"`]*[<*{]")
        self.assertNotIn("path/to", readme)

    def test_the_command_tells_the_model_about_empty_output(self):
        self.assertIn("empty", self.cmd_body)
        self.assertIn("Shell command failed", self.cmd_body)

    def test_always_on_description_budget(self):
        total = len(fm_value(self.skill_fm, "description")) + len(fm_value(self.cmd_fm, "description"))
        self.assertLess(total, 1000)

    def test_plugin_root_references_exist(self):
        for path in plugin_files((".md",)):
            for ref in re.findall(r"\$\{CLAUDE_PLUGIN_ROOT\}/([A-Za-z0-9_./\-]+)", read(path)):
                ref = ref.rstrip(".")
                if "<" in ref or ref.endswith("/"):
                    continue  # a placeholder such as hooks/<file>.py
                self.assertTrue(os.path.exists(os.path.join(PLUGIN, ref)), "%s -> %s" % (os.path.relpath(path, PLUGIN), ref))


class CodeShapeTests(unittest.TestCase):
    def python_files(self):
        return [p for p in plugin_files((".py",))]

    def test_every_python_file_compiles_under_the_system_python(self):
        interp = SYSTEM_PYTHON if os.path.exists(SYSTEM_PYTHON) else sys.executable
        with tempfile.TemporaryDirectory() as tmp:
            for i, path in enumerate(self.python_files()):
                out = os.path.join(tmp, "%d.pyc" % i)
                code = "import py_compile,sys; py_compile.compile(sys.argv[1], cfile=sys.argv[2], doraise=True)"
                r = subprocess.run([interp, "-c", code, path, out], capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, "%s: %s" % (path, r.stderr))

    def test_every_python_file_compiles_here_too(self):
        with tempfile.TemporaryDirectory() as tmp:
            for i, path in enumerate(self.python_files()):
                py_compile.compile(path, cfile=os.path.join(tmp, "h%d.pyc" % i), doraise=True)

    def test_doctor_is_one_standard_library_module_that_never_writes_bytecode(self):
        src = read(os.path.join(PLUGIN, "scripts", "doctor.py"))
        tree = ast.parse(src)
        allowed = set(
            "sys argparse calendar glob json os re shlex signal stat subprocess time collections".split()
        )
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    self.assertIn(a.name.split(".")[0], allowed)
            elif isinstance(node, ast.ImportFrom):
                self.assertIn((node.module or "").split(".")[0], allowed)
        self.assertIn("sys.dont_write_bytecode = True", src)

    def test_no_bare_python_invocation_anywhere_in_the_plugin_docs(self):
        pattern = re.compile(r"(?m)^\s*(?:[$>]\s*)?python\s|`python\s")
        for path in plugin_files((".md", ".json")):
            self.assertIsNone(pattern.search(read(path)), os.path.relpath(path, PLUGIN))


def build(*parts):
    return "".join(parts)


def banned_word_regex():
    words = [
        build("eco", "system"),
        build("plat", "form"),
        build("opti", "mize"),
        build("lever", "age"),
        build("power", "ful"),
        build("super", "charge"),
        build("seam", "less"),
        build("works out of the ", "box"),
        build("che", "ap"),
        build("che", "aper"),
    ]
    return re.compile(r"(?i)\b(?:%s)\b|save\s+\d+\s*%%" % "|".join(re.escape(w) for w in words))


class HygieneTests(unittest.TestCase):
    def scanned(self):
        return [p for p in plugin_files() if os.path.abspath(p) != SELF]

    def test_the_scans_can_see_a_known_positive(self):
        """Silence is not a finding: prove the pattern matches synthetic bad text before trusting a clean run."""
        self.assertTrue(banned_word_regex().search("a " + build("Power", "ful") + " tool"))
        self.assertTrue(banned_word_regex().search("save 40% now"))
        self.assertIsNone(banned_word_regex().search("a plain sentence about hooks"))

    def test_no_banned_public_words(self):
        rx = banned_word_regex()
        for path in self.scanned():
            self.assertIsNone(rx.search(read(path)), "%s uses a banned word" % os.path.relpath(path, PLUGIN))

    def test_the_readme_has_the_required_statements(self):
        readme = read(os.path.join(PLUGIN, "README.md"))
        self.assertIn(PROMISE, readme)
        self.assertIn("/plugin marketplace add DojoGenesis/plugins", readme)
        self.assertIn("/plugin install dojo-doctor@dojo-genesis", readme)
        self.assertIn("Tested with", readme)
        self.assertIn("2.1.286", readme)
        self.assertIn("Kill switches", readme)
        self.assertIn("None: nothing runs unless you call it.", readme)
        self.assertIn("estimate", readme)


if __name__ == "__main__":
    unittest.main()
