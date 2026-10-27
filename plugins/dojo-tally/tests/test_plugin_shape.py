"""Static checks on dojo-tally as shipped: manifest, wiring, the JSX trap, the engine's own prefix, public-text hygiene.

The behaviour itself is tested with the Claude Code kit (tests/*.test.ts*, `claude plugin test`)."""
import glob
import json
import os
import re
import unittest

from _helpers import PLUGIN_ROOT

NAME = 'dojo-tally'
KILL_SWITCH = 'DOJO_TALLY_OFF'
MODULES = ['register.ts']
COMMANDS = ['/tally', '/tally refute', '/refute']
# The classic command shipped as the fallback: it runs only when the mod is not loaded, and the mod answers it
# under its plugin-qualified name when it is.
FALLBACK = 'tally'
# The promise exactly as the manifest and the README word it.
PROMISE = 'Count returns, not dispatches: when a fan-out settles, the model hears what came back (returned, failed, silent, unchecked), and /tally refute sends a report to a judge.'
USER_CONFIG = ['judge_model', 'min_wave', 'settle_note']


def read(*parts):
    with open(os.path.join(PLUGIN_ROOT, *parts), encoding="utf-8") as handle:
        return handle.read()


def hooks_sources():
    return sorted(glob.glob(os.path.join(PLUGIN_ROOT, "hooks", "*.ts*")))


class Manifest(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads(read(".claude-plugin", "plugin.json"))

    def test_description_is_the_promise_and_within_budget(self):
        self.assertEqual(self.manifest["description"], PROMISE)
        self.assertLessEqual(len(PROMISE), 200)

    def test_required_fields(self):
        m = self.manifest
        self.assertEqual(m["name"], NAME)
        self.assertEqual(m["version"], "0.1.2")
        self.assertEqual(m["author"], {"name": "Dojo Genesis", "email": "cruz@trespiesdesign.com"})
        self.assertEqual(m["homepage"], "https://dojogenesis.com/suite#" + NAME)
        self.assertEqual(m["repository"], "https://github.com/DojoGenesis/plugins")
        self.assertEqual(m["license"], "Apache-2.0")
        self.assertIn("mod", m["keywords"])

    def test_types_file_is_named_when_present(self):
        path = os.path.join(PLUGIN_ROOT, "types", "index.d.ts")
        if os.path.isfile(path):
            self.assertEqual(self.manifest.get("types"), "./types/index.d.ts")
        else:
            self.assertNotIn("types", self.manifest)

    def test_user_config_is_the_documented_set_and_each_option_is_read(self):
        cfg = self.manifest["userConfig"]
        self.assertEqual(sorted(cfg), sorted(USER_CONFIG))
        self.assertTrue(any(entry["type"] == "boolean" for entry in cfg.values()), "a boolean switch for the mod")
        source = read("hooks", "register.ts")
        readme = read("README.md")
        for key in cfg:
            with self.subTest(option=key):
                self.assertIn("options." + key, source)
                self.assertIn("`" + key + "`", readme)


class Wiring(unittest.TestCase):
    def test_hooks_json_has_the_mod_and_no_classic_hooks(self):
        hooks = json.loads(read("hooks", "hooks.json"))
        self.assertTrue(hooks["description"])
        self.assertEqual(hooks["hooks"], {})
        self.assertEqual(hooks["modules"], ["./register.ts"])
        for name in MODULES:
            self.assertTrue(os.path.isfile(os.path.join(PLUGIN_ROOT, "hooks", name)), name)

    def test_the_modules_import_only_files_of_the_plugin(self):
        for path in hooks_sources():
            text = read("hooks", os.path.basename(path))
            for target in re.findall(r"from '([^']+)'", text):
                with self.subTest(file=os.path.basename(path), target=target):
                    if target.startswith("."):
                        base = os.path.normpath(os.path.join(PLUGIN_ROOT, "hooks", target))
                        self.assertTrue(any(os.path.exists(base + ext) for ext in (".ts", ".tsx", "/index.d.ts", ".d.ts")))
                    else:
                        self.assertEqual(target, "claude-code")

    def test_the_types_file_is_self_contained(self):
        path = os.path.join(PLUGIN_ROOT, "types", "index.d.ts")
        if not os.path.isfile(path):
            # No state, so no contract; the manifest test checks it names none.
            self.assertNotIn("types", json.loads(read(".claude-plugin", "plugin.json")))
            return
        text = read("types", "index.d.ts")
        self.assertIsNone(re.search(r"^\s*import\s", text, re.M))
        self.assertIn("interface PluginState", text)
        self.assertIn("'" + NAME + "'", text)

    def test_the_kill_switches_are_read_by_literal_name(self):
        source = read("hooks", "register.ts")
        self.assertIn("$.env.get('DOJO_OFF')", source)
        self.assertIn("$.env.get('" + KILL_SWITCH + "')", source)

    def test_no_machine_paths_in_the_code(self):
        for path in hooks_sources() + sorted(glob.glob(os.path.join(PLUGIN_ROOT, "tests", "*.ts*"))):
            with self.subTest(file=os.path.basename(path)):
                with open(path, encoding="utf-8") as handle:
                    text = handle.read()
                self.assertIsNone(re.search(r"/(?:Users|home|private/tmp)/", text))


class Fallback(unittest.TestCase):
    def setUp(self):
        self.text = read("commands", FALLBACK + ".md")

    def test_frontmatter_has_a_description_and_a_non_empty_allowed_tools_list(self):
        lines = self.text.splitlines()
        self.assertEqual(lines[0], "---")
        meta = {}
        for line in lines[1:]:
            if line == "---":
                break
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip()
        self.assertTrue(json.loads(meta["description"]))
        self.assertTrue(json.loads(meta["allowed-tools"]))

    def test_it_says_how_to_turn_the_mod_on(self):
        self.assertIn("CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1", self.text)

    def test_the_mod_answers_the_qualified_name(self):
        self.assertIn("'" + NAME + ":" + FALLBACK + "'", read("hooks", "register.ts"))

    def test_it_is_the_only_command_file(self):
        self.assertEqual(sorted(os.listdir(os.path.join(PLUGIN_ROOT, "commands"))), [FALLBACK + ".md"])


class JsxTrap(unittest.TestCase):
    """`h` and `Fragment` are engine globals: declaring or taking either as a parameter breaks every draw."""

    PATTERNS = [
        re.compile(r"\b(?:const|let|var|function|class)\s+(?:h|Fragment)\b"),
        re.compile(r"[(,]\s*(?:h|Fragment)\s*[,)=:]"),
        re.compile(r"\b(?:h|Fragment)\s*=>"),
        re.compile(r"\bimport\s*\{[^}]*\b(?:h|Fragment)\b[^}]*\}"),
        re.compile(r"\b(?:h|Fragment)\s*(?:,|\})\s*=\s*"),
    ]

    def hits(self, text):
        out = []
        for pattern in self.PATTERNS:
            out.extend(pattern.findall(text))
        return out

    def test_no_module_or_test_names_anything_h_or_fragment(self):
        files = hooks_sources() + sorted(glob.glob(os.path.join(PLUGIN_ROOT, "tests", "*.ts*")))
        self.assertGreaterEqual(len(files), 2)
        for path in files:
            with self.subTest(file=os.path.relpath(path, PLUGIN_ROOT)):
                with open(path, encoding="utf-8") as handle:
                    text = handle.read()
                self.assertEqual(self.hits(text), [])
                self.assertNotIn("Fragment", text)
                self.assertNotIn("@jsx", text)

    def test_the_patterns_can_see_a_known_positive(self):
        for bad in ("const h = 1", "list.map((h) => h)", "const f = h => 1", "import { h } from 'x'", "function g(a, h) {}"):
            self.assertTrue(self.hits(bad), bad)
        self.assertEqual(self.hits("const hide = (x) => x; const ph = 2; hash(a, b)"), [])


class EnginePrefix(unittest.TestCase):
    """The engine heads a plugin's log lines, toasts and command answers with the plugin's name. A text that
    starts with it again reads `name: name: ...` (seen live on Claude Code 2.1.295)."""

    CALL = re.compile(r"\$\.ui\.(?:log|toast)\((?:[^()]|\([^()]*\))*?\)", re.S)
    SELF = re.compile(r"[`'\"]" + re.escape(NAME) + r": ")

    def offenders(self, text):
        return [call for call in self.CALL.findall(text) if self.SELF.search(call)]

    def test_no_log_or_toast_repeats_the_plugin_name(self):
        for path in hooks_sources():
            with self.subTest(file=os.path.basename(path)):
                with open(path, encoding="utf-8") as handle:
                    self.assertEqual(self.offenders(handle.read()), [])

    def test_the_check_can_see_a_known_positive(self):
        bad = "$.ui.toast(\n  ok\n    ? `" + NAME + ": done`\n    : `x`,\n)"
        self.assertTrue(self.offenders(bad))
        self.assertEqual(self.offenders("$.ui.log(`done for ${x}`)"), [])


class Hygiene(unittest.TestCase):
    """Public text: no banned words, no savings numbers, no full model ids in copy. No internal names, paths or
    ticket prefixes in any form: the central scanners read those from lists that stay on the maintainer's machine."""

    PUBLIC = [("README.md",), (".claude-plugin", "plugin.json"), ("commands", FALLBACK + ".md")]
    # The suite's public-vocabulary bans, split so this file passes the same lint.
    BANNED_WORDS = [
        "ecosyst" + "em", "plat" + "form", "optim" + "ize", "lever" + "age", "power" + "ful", "super" + "charge",
        "seam" + "less", "works out of the " + "box", "che" + "ap", "sa" + "ve",
    ]
    SAVINGS = re.compile(r"\b(fewer|less|cut|lower|reduce[sd]?)\b[^.\n]{0,30}\b\d", re.I)
    MODEL_ID = re.compile(r"claude-(?:opus|sonnet|haiku)-\d")

    def texts(self):
        return [(os.path.join(*p), read(*p)) for p in self.PUBLIC]

    def test_no_banned_words(self):
        for name, text in self.texts():
            lowered = text.lower()
            for word in self.BANNED_WORDS:
                with self.subTest(file=name, word=len(word)):
                    self.assertFalse(word in lowered, "banned word found")

    def test_no_percent_signs_or_savings_numbers(self):
        for name, text in self.texts():
            with self.subTest(file=name):
                self.assertNotIn("%", text)
                self.assertIsNone(self.SAVINGS.search(text))

    def test_no_full_model_ids_in_copy(self):
        for name, text in self.texts():
            with self.subTest(file=name):
                self.assertIsNone(self.MODEL_ID.search(text))

    def test_the_readme_has_what_the_suite_asks_for(self):
        text = read("README.md")
        self.assertIn(PROMISE, text)
        for needle in ["/plugin install " + NAME + "@dojo-genesis", "CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1", "early access",
                       "DOJO_OFF=1", KILL_SWITCH + "=1", "Honest limits", "Tested with Claude Code 2.1.295"] + COMMANDS:
            with self.subTest(needle=needle):
                self.assertIn(needle, text)

    def test_the_checks_can_see_a_known_positive(self):
        bad = ("A " + self.BANNED_WORDS[1] + " with 40% fewer 3 things on claude-opus-5-5.").lower()
        self.assertIn(self.BANNED_WORDS[1], bad)
        self.assertIn("%", bad)
        self.assertIsNotNone(self.SAVINGS.search(bad))
        self.assertIsNotNone(self.MODEL_ID.search(bad))


if __name__ == "__main__":
    unittest.main()
