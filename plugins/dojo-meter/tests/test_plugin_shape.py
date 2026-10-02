"""Static checks on the plugin as shipped: manifest, wiring, the command, the JSX trap, public-text hygiene."""
import glob
import json
import os
import re
import stat
import unittest

from _helpers import PLUGIN_ROOT

# The promise exactly as the suite contract words it.
PROMISE = ("See what each turn, agent and model costs, and how big your context is: a cost report from your "
           "transcripts, and a live band with the mod.")


def read(*parts):
    with open(os.path.join(PLUGIN_ROOT, *parts), encoding="utf-8") as handle:
        return handle.read()


def frontmatter(text):
    lines = text.splitlines()
    assert lines[0] == "---"
    meta = {}
    for line in lines[1:]:
        if line == "---":
            break
        key, _, value = line.partition(":")
        meta[key.strip()] = value.strip()
    return meta


def unquote(value):
    return json.loads(value) if value.startswith('"') else value


class Manifest(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads(read(".claude-plugin", "plugin.json"))

    def test_description_is_the_promise_verbatim_and_within_budget(self):
        self.assertEqual(self.manifest["description"], PROMISE)
        self.assertLessEqual(len(self.manifest["description"]), 200)

    def test_required_fields(self):
        m = self.manifest
        self.assertEqual(m["name"], "dojo-meter")
        self.assertEqual(m["version"], "0.1.0")
        self.assertEqual(m["author"], {"name": "Dojo Genesis", "email": "cruz@trespiesdesign.com"})
        self.assertEqual(m["homepage"], "https://dojogenesis.com/suite#dojo-meter")
        self.assertEqual(m["repository"], "https://github.com/DojoGenesis/plugins")
        self.assertEqual(m["license"], "Apache-2.0")
        self.assertTrue(m["keywords"])
        self.assertEqual(m["types"], "./types/index.d.ts")
        self.assertTrue(os.path.isfile(os.path.join(PLUGIN_ROOT, "types", "index.d.ts")))

    def test_user_config_matches_the_contract(self):
        cfg = self.manifest["userConfig"]
        self.assertEqual(set(cfg), {"show_band", "budget_usd", "context_warn_tokens"})
        self.assertEqual((cfg["show_band"]["type"], cfg["show_band"]["default"]), ("boolean", True))
        self.assertEqual((cfg["budget_usd"]["type"], cfg["budget_usd"]["default"], cfg["budget_usd"]["min"]), ("number", 0, 0))
        self.assertEqual((cfg["context_warn_tokens"]["type"], cfg["context_warn_tokens"]["default"],
                          cfg["context_warn_tokens"]["min"]), ("number", 400000, 0))

    def test_manifest_defaults_match_the_defaults_in_the_mod(self):
        source = read("hooks", "register.ts")
        cfg = self.manifest["userConfig"]
        self.assertIn("asFlag(options.show_band, %s)" % str(cfg["show_band"]["default"]).lower(), source)
        self.assertIn("asLimit(options.budget_usd, %d)" % cfg["budget_usd"]["default"], source)
        self.assertIn("asLimit(options.context_warn_tokens, %d)" % cfg["context_warn_tokens"]["default"], source)


class Wiring(unittest.TestCase):
    def test_hooks_json_has_the_mod_and_no_classic_hooks(self):
        hooks = json.loads(read("hooks", "hooks.json"))
        self.assertTrue(hooks["description"])
        self.assertEqual(hooks["hooks"], {})
        self.assertEqual(hooks["modules"], ["./register.ts"])
        for name in ("register.ts", "band.tsx", "ledger.ts", "pricing.ts"):
            self.assertTrue(os.path.isfile(os.path.join(PLUGIN_ROOT, "hooks", name)), name)

    def test_the_module_imports_only_files_of_the_plugin(self):
        for name in ("register.ts", "band.tsx", "ledger.ts"):
            for target in re.findall(r"from '([^']+)'", read("hooks", name)):
                if target.startswith("."):
                    base = os.path.normpath(os.path.join(PLUGIN_ROOT, "hooks", target))
                    self.assertTrue(any(os.path.exists(base + ext) for ext in (".ts", ".tsx", "/index.d.ts", ".d.ts")),
                                    "%s imports %s" % (name, target))
                else:
                    self.assertEqual(target, "claude-code", "%s imports %s" % (name, target))

    def test_the_types_file_is_self_contained(self):
        text = read("types", "index.d.ts")
        self.assertNotIn("EngineInterface", text)
        self.assertIsNone(re.search(r"^\s*import\s", text, re.M))
        for name in ("MeterBand", "MeterLedger"):
            self.assertIn("export type %s" % name, text)
        self.assertIn("'dojo-meter'", text)


class Commands(unittest.TestCase):
    def setUp(self):
        self.cost = read("commands", "cost.md")
        self.band = read("commands", "band.md")

    def test_cost_command_runs_the_script_it_is_allowed_to_run(self):
        meta = frontmatter(self.cost)
        allowed = json.loads(meta["allowed-tools"])
        self.assertEqual(len(allowed), 1)
        allowed_path = re.match(r"^Bash\((.+?):\*\)$", allowed[0]).group(1)
        block = re.search(r"```!\n(.*?)\n```", self.cost, re.S).group(1)
        ran_path = block.split()[0].strip('"')
        self.assertEqual(allowed_path, ran_path)
        self.assertEqual(ran_path, "${CLAUDE_PLUGIN_ROOT}/scripts/cost.py")
        self.assertIn("${CLAUDE_SESSION_ID}", block)
        self.assertIn("$ARGUMENTS", block)
        self.assertIn("--default-session", block)

    def test_the_band_command_declares_a_non_empty_allowed_tools_list(self):
        meta = frontmatter(self.band)
        self.assertIn("allowed-tools", meta)
        allowed = json.loads(meta["allowed-tools"])
        self.assertIsInstance(allowed, list)
        self.assertTrue(allowed)
        for item in allowed:
            self.assertIsInstance(item, str)
            self.assertTrue(item.strip())

    def test_the_script_is_executable_and_names_python3(self):
        path = os.path.join(PLUGIN_ROOT, "scripts", "cost.py")
        self.assertTrue(os.stat(path).st_mode & stat.S_IXUSR)
        with open(path) as handle:
            self.assertEqual(handle.readline().strip(), "#!/usr/bin/env python3")

    def test_command_text_is_short_and_plain(self):
        body = self.cost.split("```", 2)[2].strip()
        self.assertEqual(body, "Show the report above to the user exactly as printed, in one code block, with no commentary.")
        self.assertNotIn("model:", frontmatter(self.cost))  # a model switch would forfeit the prompt cache

    def test_descriptions_fit_and_the_always_on_weight_is_small(self):
        total = 0
        for text in (self.cost, self.band):
            desc = unquote(frontmatter(text)["description"])
            self.assertLessEqual(len(desc), 200)
            total += len(desc)
        self.assertLess(total, 1000)
        self.assertIn("mod", unquote(frontmatter(self.band)["description"]))

    def test_there_are_no_skills_or_agents_adding_always_on_weight(self):
        self.assertFalse(os.path.exists(os.path.join(PLUGIN_ROOT, "skills")))
        self.assertFalse(os.path.exists(os.path.join(PLUGIN_ROOT, "agents")))


class JsxTrap(unittest.TestCase):
    """`h` and `Fragment` are engine globals: declaring or taking either as a parameter breaks every draw."""

    PATTERNS = [
        re.compile(r"\b(?:const|let|var|function|class)\s+(?:h|Fragment)\b"),
        re.compile(r"[(,]\s*(?:h|Fragment)\s*[,)=:]"),
        re.compile(r"\b(?:h|Fragment)\s*=>"),
        re.compile(r"\bimport\s*\{[^}]*\b(?:h|Fragment)\b[^}]*\}"),
        re.compile(r"\b(?:h|Fragment)\s*(?:,|\})\s*=\s*"),
    ]

    def sources(self):
        files = glob.glob(os.path.join(PLUGIN_ROOT, "hooks", "*.ts*")) + glob.glob(os.path.join(PLUGIN_ROOT, "tests", "*.ts*"))
        self.assertGreaterEqual(len(files), 8)
        return files

    def hits(self, text):
        out = []
        for pattern in self.PATTERNS:
            out.extend(pattern.findall(text))
        return out

    def test_no_module_or_test_names_anything_h_or_fragment(self):
        for path in self.sources():
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


class Hygiene(unittest.TestCase):
    """Public text: no banned words, no savings numbers, no full model ids in copy. This class carries no
    internal names, paths or ticket prefixes in any form: the central scanners (scripts/suite_lint.py and
    scripts/suite_denylist.py) read those from lists that stay on the maintainer's machine."""

    PUBLIC = [("README.md",), ("commands", "cost.md"), ("commands", "band.md"), (".claude-plugin", "plugin.json")]
    # The suite's public-vocabulary bans (build contract section 0), split so this file passes the same lint.
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

    def test_the_readme_has_what_the_contract_asks_for(self):
        text = read("README.md")
        self.assertIn(PROMISE, text)
        for needle in ("/plugin install dojo-meter@dojo-genesis", "CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1", "early access",
                       "DOJO_OFF=1", "DOJO_METER_OFF=1", "Honest limits", "Tested with Claude Code 2.1.286",
                       "unpriced", "partial", "list prices", "Subscription plans bill differently", "under-record"):
            self.assertIn(needle, text)

    def test_the_readme_does_not_claim_the_plugin_has_no_numbers(self):
        # It has thresholds (70 and 90 percent, a token count, 60 days); what it claims no figures for is savings.
        self.assertNotIn("no numbers in this plugin", read("README.md"))

    def test_the_checks_can_see_a_known_positive(self):
        bad = ("A " + self.BANNED_WORDS[1] + " with 40% fewer 3 things on claude-opus-5-5.").lower()
        self.assertIn(self.BANNED_WORDS[1], bad)
        self.assertIn("%", bad)
        self.assertIsNotNone(self.SAVINGS.search(bad))
        self.assertIsNotNone(self.MODEL_ID.search(bad))


if __name__ == "__main__":
    unittest.main()
