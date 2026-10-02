"""pricing.json is the one table: the numbers are the contract's, and the TypeScript copies cannot drift."""
import glob
import json
import os
import shutil
import subprocess
import tempfile
import unittest

from _helpers import PLUGIN_ROOT, PY, SCRIPTS

GEN = os.path.join(SCRIPTS, "gen_pricing_ts.py")

# USD per million tokens, as the suite contract states them: (input, output, cache read).
EXPECTED = {
    "claude-fable-5-1": (10, 50, 0.25),
    "claude-fable-5": (10, 50, 1.00),
    "claude-opus-5-5": (4, 20, 0.20),
    "claude-opus-5": (5, 25, 0.50),
    "claude-opus-4-8": (5, 25, 0.50),
    "claude-opus-4-7": (5, 25, 0.50),
    "claude-opus-4-6": (5, 25, 0.50),
    "claude-sonnet-5-5": (2, 10, 0.20),
    "claude-sonnet-5": (2, 10, 0.20),
    "claude-sonnet-4-6": (3, 15, 0.30),
    "claude-haiku-4-5": (1, 5, 0.10),
}


def load():
    with open(os.path.join(SCRIPTS, "pricing.json")) as handle:
        return json.load(handle)


def gen(*args):
    return subprocess.run([PY, GEN] + list(args), stdout=subprocess.PIPE, stderr=subprocess.PIPE)


class PricingTable(unittest.TestCase):
    def test_exactly_the_contract_models_and_numbers(self):
        models = load()["models"]
        self.assertEqual(set(models), set(EXPECTED))
        for name, (inp, out, read) in EXPECTED.items():
            with self.subTest(model=name):
                self.assertEqual(set(models[name]), {"input", "output", "cache_read"})
                self.assertEqual((models[name]["input"], models[name]["output"], models[name]["cache_read"]), (inp, out, read))

    def test_source_and_multipliers(self):
        table = load()
        self.assertEqual(table["source"], "Anthropic list prices as cached 2026-09-25")
        self.assertEqual(table["cache_write_5m_multiplier"], 1.25)
        self.assertEqual(table["cache_write_1h_multiplier"], 2.0)

    def test_the_cost_script_reads_this_table(self):
        import cost
        self.assertEqual(os.path.normpath(cost.PRICING_PATH), os.path.join(SCRIPTS, "pricing.json"))


class GeneratedCopies(unittest.TestCase):
    def test_the_committed_copies_match_their_sources(self):
        proc = gen("--check")
        self.assertEqual(proc.returncode, 0, proc.stdout)

    def test_the_check_notices_a_drifted_copy(self):
        """Positive control: the same check, run on a mutated copy, must fail."""
        with tempfile.TemporaryDirectory() as tmp:
            for rel in ("hooks/pricing.ts", "tests/vectors.ts"):
                os.makedirs(os.path.dirname(os.path.join(tmp, rel)), exist_ok=True)
                shutil.copy(os.path.join(PLUGIN_ROOT, rel), os.path.join(tmp, rel))
            self.assertEqual(gen("--check", "--root=" + tmp).returncode, 0)
            path = os.path.join(tmp, "hooks", "pricing.ts")
            with open(path) as handle:
                text = handle.read()
            self.assertIn('"input": 4,', text)
            with open(path, "w") as handle:
                handle.write(text.replace('"input": 4,', '"input": 5,', 1))
            proc = gen("--check", "--root=" + tmp)
            self.assertEqual(proc.returncode, 1)
            self.assertIn(b"hooks/pricing.ts", proc.stdout)

    def test_the_generated_file_says_so(self):
        with open(os.path.join(PLUGIN_ROOT, "hooks", "pricing.ts")) as handle:
            head = handle.read(400)
        self.assertIn("Generated", head)
        self.assertIn("do not edit", head)

    def test_every_python_file_compiles_under_the_system_interpreter(self):
        if not os.path.exists("/usr/bin/python3"):
            self.skipTest("no /usr/bin/python3")
        code = ("import py_compile, sys, tempfile, os;"
                "py_compile.compile(sys.argv[1], cfile=os.path.join(tempfile.mkdtemp(), 'x.pyc'), doraise=True)")
        files = glob.glob(os.path.join(PLUGIN_ROOT, "**", "*.py"), recursive=True)
        self.assertGreaterEqual(len(files), 4)
        for path in files:
            with self.subTest(path=os.path.relpath(path, PLUGIN_ROOT)):
                proc = subprocess.run(["/usr/bin/python3", "-c", code, path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                self.assertEqual(proc.returncode, 0, proc.stderr)


if __name__ == "__main__":
    unittest.main()
