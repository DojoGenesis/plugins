"""Tests for hooks/workflow_models.py. Every script here is hand-written synthetic JavaScript."""
import glob
import json
import os
import stat
import subprocess
import tempfile
import time
import unittest

import _helpers
from _helpers import FIXTURES_DIR, TESTS_DIR, parse, run_hook, workflow_payload

import workflow_models as wm

SCRIPT = "workflow_models.py"


def fixture(name):
    with open(os.path.join(FIXTURES_DIR, name), encoding="utf-8") as handle:
        return handle.read()


class Checker(unittest.TestCase):
    """The static checker, called directly."""

    def check(self, src):
        return wm.check_source(src)

    def flagged_lines(self, src):
        return [r["line"] for r in self.check(src)["missing"]]

    def test_positive_control_counts_three_calls_and_one_missing(self):
        res = self.check(fixture("one_unpinned.js"))
        self.assertEqual(res["calls"], 3)
        self.assertEqual(res["pinned"], 2)
        self.assertEqual(len(res["missing"]), 1)
        self.assertEqual(res["missing"][0]["label"], "builder")
        self.assertEqual(res["missing"][0]["line"], 6)
        self.assertEqual(res["unverifiable"], [])

    def test_clean_fixture_reports_a_real_nonzero_count(self):
        res = self.check(fixture("all_pinned.js"))
        self.assertEqual(res["calls"], 3)
        self.assertEqual(res["pinned"], 3)
        self.assertEqual((res["missing"], res["unverifiable"]), ([], []))
        self.assertTrue(res["balanced"])

    def test_no_options_object(self):
        self.assertEqual(self.flagged_lines("await agent('p')"), [1])
        self.assertEqual(self.flagged_lines("await agent()"), [1])

    def test_options_without_a_model(self):
        self.assertEqual(self.flagged_lines("await agent('p', { label: 'x', schema: {} })"), [1])
        self.assertEqual(self.flagged_lines("await agent('p', {})"), [1])

    def test_model_undefined_null_and_empty_are_missing(self):
        for value in ("undefined", "null", "''", '""', "'  '"):
            with self.subTest(value=value):
                self.assertEqual(self.flagged_lines("await agent('p', { model: %s })" % value), [1])

    def test_model_nested_in_a_schema_is_not_a_pin(self):
        src = "await agent('p', { schema: { properties: { model: { type: 'string' } } } })"
        self.assertEqual(self.flagged_lines(src), [1])

    def test_model_inside_the_first_argument_is_not_a_pin(self):
        self.assertEqual(self.flagged_lines("await agent({ model: 'haiku', text: 'p' }, { label: 'a' })"), [1])
        self.assertEqual(self.flagged_lines("await agent('{ model: \"haiku\" }', { label: 'a' })"), [1])
        self.assertEqual(self.flagged_lines("await agent('p' + JSON.stringify({ model: 'haiku' }), { label: 'a' })"), [1])

    def test_agent_inside_a_template_expression_is_found(self):
        res = self.check("const t = `before ${await agent('x')} after`")
        self.assertEqual(res["calls"], 1)
        self.assertEqual(len(res["missing"]), 1)

    def test_nested_template_expressions(self):
        res = self.check("const t = `a ${ `b ${await agent('x', {model:'haiku'})}` } c`\nawait agent('y')")
        self.assertEqual(res["calls"], 2)
        self.assertEqual(res["pinned"], 1)
        self.assertEqual([r["line"] for r in res["missing"]], [2])
        self.assertTrue(res["balanced"])

    def test_text_that_only_looks_like_a_call_is_ignored(self):
        src = "\n".join([
            "// agent('in a line comment')",
            "/* agent('in a block comment') */",
            "const a = \"agent('double quoted')\"",
            "const b = 'agent(\\'single quoted\\')'",
            "const c = `agent('plain template text')`",
            "x.agent('member call')",
            "x?.agent('optional member call')",
            "subagent('longer name')",
            "$agent('dollar name')",
            "_agent('underscore name')",
            "function agent(prompt, opts) { return prompt }",
        ])
        res = self.check(src)
        self.assertEqual(res["calls"], 0)
        self.assertTrue(res["balanced"])

    def test_whitespace_and_newlines_before_the_paren_still_count(self):
        self.assertEqual(self.check("await agent ('p')")["calls"], 1)
        self.assertEqual(self.check("await agent\n('p')")["calls"], 1)
        self.assertEqual(self.check("await agent?.('p')")["calls"], 1)

    def test_quoted_and_shorthand_model_keys_are_pins(self):
        for opts in ("{ 'model': 'haiku' }", '{ "model": \'x\' }', "{ model }", "{ model: big ? 'opus' : 'sonnet' }",
                     "{ label: 'a', model: pick(args) }"):
            with self.subTest(opts=opts):
                res = self.check("await agent('p', %s)" % opts)
                self.assertEqual((res["pinned"], res["missing"], res["unverifiable"]), (1, [], []))

    def test_plugin_agent_type_is_not_flagged(self):
        res = self.check("await agent('p', { agentType: 'some-plugin:reviewer' })")
        self.assertEqual((res["plugin"], res["missing"], res["unverifiable"]), (1, [], []))
        res = self.check("await agent('p', { agentType: 'builder' })")
        self.assertEqual(len(res["missing"]), 1)

    def test_unverifiable_forms_are_counted_never_called_pinned(self):
        forms = [
            "await agent('p', opts)",
            "await agent('p', big ? { model: 'opus' } : { model: 'haiku' })",
            "await agent('p', { ...base })",
            "await agent('p', { ...base, label: 'x' })",
            "await agent(...args)",
            "await agent('p', ...rest)",
            "await agent('p', { [key]: 'haiku' })",
            "await agent('p', makeOptions())",
        ]
        for src in forms:
            with self.subTest(src=src):
                res = self.check(src)
                self.assertEqual(res["calls"], 1)
                self.assertEqual(res["pinned"], 0)
                self.assertEqual(len(res["unverifiable"]), 1)
                self.assertEqual(res["missing"], [])

    def test_spread_with_an_explicit_model_is_a_pin(self):
        res = self.check("await agent('p', { ...base, model: 'haiku' })")
        self.assertEqual((res["pinned"], res["unverifiable"]), (1, []))

    def test_regex_literal_with_quotes_does_not_hide_a_later_call(self):
        src = "const r = /['\"(]/\nconst ok = r.test(x)\nawait agent('p', { label: 'x' })"
        res = self.check(src)
        self.assertEqual(res["calls"], 1)
        self.assertEqual([r["line"] for r in res["missing"]], [3])
        self.assertTrue(res["balanced"])

    def test_regex_after_return_and_division_are_told_apart(self):
        src = "const half = total / 2 / 3\nconst f = () => { return /\\)'/.test(s) }\nawait agent('p')"
        res = self.check(src)
        self.assertEqual([r["line"] for r in res["missing"]], [3])
        self.assertTrue(res["balanced"])

    def test_unbalanced_input_is_unverifiable_not_clean(self):
        for src in ("await agent('p', { model: 'haiku' }", "const t = `open ${await agent('x', {model:'haiku'})",
                    "const s = 'never closed\nawait agent('p', {model:'haiku'})", "/* never closed agent('p')"):
            with self.subTest(src=src):
                res = self.check(src)
                unsure = (not res["balanced"]) or res["unverifiable"]
                self.assertTrue(unsure)

    def test_line_numbers_survive_multiline_strings_and_comments(self):
        src = "/* a\nb\nc */\nconst t = `x\ny`\nawait agent('p')\n"
        self.assertEqual(self.flagged_lines(src), [6])

    def test_multiline_options_with_a_long_concatenated_prompt(self):
        src = (
            "await agent(\n"
            "  'Intro. ' + JSON.stringify({ a: [1, 2, { model: 'decoy' }] }) +\n"
            "  (cond ? 'x' : 'y') + helper(1, 2),\n"
            "  {\n    label: 'long',\n    model: 'sonnet',\n  },\n)\n"
        )
        res = self.check(src)
        self.assertEqual((res["calls"], res["pinned"], res["missing"], res["unverifiable"]), (1, 1, [], []))

    def test_inherit_is_not_a_pin(self):
        for value in ("'inherit'", "'Inherit'", "'  INHERIT '", '"inherit"'):
            with self.subTest(value=value):
                self.assertEqual(self.flagged_lines("await agent('p', { model: %s })" % value), [1])
        res = self.check("await agent('p', { model: 'haiku' })")
        self.assertEqual((res["pinned"], res["missing"]), (1, []))

    def test_void_zero_is_no_pin(self):
        self.assertEqual(self.flagged_lines("await agent('p', { model: void 0 })"), [1])

    def test_a_model_given_as_a_variable_or_call_counts_as_set(self):
        # What the README says: the hook does not look into the value of a model key.
        for opts in ("{ model: m }", "{ model }", "{ model: pick('x') }", "{ model: c ? 'opus' : undefined }",
                     "{ model: 'haiku', ...o }", "{ model: `inherit` }"):
            with self.subTest(opts=opts):
                res = self.check("await agent('p', %s)" % opts)
                self.assertEqual((res["pinned"], res["missing"], res["unverifiable"]), (1, [], []))

    def test_a_model_written_as_a_method_or_getter_cannot_be_checked(self):
        for opts in ("{ model() { return 'haiku' } }", "{ get model() { return 'haiku' } }",
                     "{ label: 'a', async model() { return 'haiku' } }", "{ set model(v) {} }"):
            with self.subTest(opts=opts):
                res = self.check("await agent('p', %s)" % opts)
                self.assertEqual((res["pinned"], res["missing"], len(res["unverifiable"])), (0, [], 1))

    def test_a_property_that_merely_contains_the_word_model_is_not_a_method(self):
        res = self.check("await agent('p', { models: 1, get label() { return 'x' } })")
        self.assertEqual(len(res["missing"]), 1)

    def test_an_inherit_or_empty_model_followed_by_a_spread_is_unverifiable(self):
        res = self.check("await agent('p', { model: 'inherit', ...base })")
        self.assertEqual((res["missing"], len(res["unverifiable"])), ([], 1))
        res = self.check("await agent('p', { ...base, model: 'inherit' })")
        self.assertEqual((len(res["missing"]), res["unverifiable"]), (1, []))

    def test_a_trailing_comma_does_not_hide_a_missing_options_object(self):
        self.assertEqual(self.flagged_lines("await agent('p',)"), [1])

    def test_indirect_ways_to_call_agent_are_listed_not_ignored(self):
        forms = [
            "await agent.call(null, 'p')",
            "await agent.apply(null, ['p'])",
            "const run = agent.bind(null)",
            "await (agent)('p')",
            "const a = agent\nawait a('p')",
            "const jobs = prompts.map(agent)",
            "const run = ok ? agent : other",
            "const table = { run: agent }",
            "await globalThis['agent']('p')",
            "const [a, b] = [agent, other]",
        ]
        for src in forms:
            with self.subTest(src=src):
                res = self.check(src)
                self.assertEqual(res["calls"], 0)
                self.assertEqual(len(res["indirect"]), 1)

    def test_uses_of_the_name_that_are_not_indirect_calls_are_not_listed(self):
        quiet = [
            "x.agent(1)",
            "const o = { agent: 1 }",
            "const { agent } = ctx",
            "const { a, agent } = ctx",
            "const f = agent => agent + 1",
            "const g = (agent, b) => agent",
            "function run(agent) { return 1 }",
            "function agent(p) { return p }",
            "const agent2 = 1\nagent2(1)",
            "// agent.call(null)\nconst s = 'agent.call(x)'",
            "if (typeof agent !== 'function') throw 1",
            "log(agent.length)",
            "import { agent } from 'x'",
        ]
        for src in quiet:
            with self.subTest(src=src):
                self.assertEqual(self.check(src)["indirect"], [])

    def test_indirect_reference_does_not_disturb_the_direct_count(self):
        res = self.check("const jobs = list.map(agent)\nawait agent('p', { model: 'haiku' })\nawait agent('q')")
        self.assertEqual((res["calls"], res["pinned"], len(res["missing"]), len(res["indirect"])), (2, 1, 1, 1))

    def test_unclosed_calls_are_linear_not_quadratic(self):
        started = time.time()
        res = self.check("agent(" * 5000)
        self.assertLess(time.time() - started, 1.0)
        self.assertEqual(res["calls"], 5000)
        self.assertEqual(len(res["unverifiable"]), 5000)

    def test_deeply_nested_closed_calls_are_linear_too(self):
        started = time.time()
        res = self.check("agent('p', { a: " * 3000 + "1" + " })" * 3000)
        self.assertLess(time.time() - started, 1.0)
        self.assertEqual(res["calls"], 3000)
        self.assertEqual(len(res["missing"]), 3000)

    def test_a_flood_of_unterminated_regex_candidates_is_bounded(self):
        started = time.time()
        res = self.check("(/[" * 20000)
        self.assertLess(time.time() - started, 2.0)
        self.assertFalse(res["balanced"])  # the look-ahead budget ran out, and it says so

    def test_long_runs_of_ordinary_code_stay_fast(self):
        src = "await agent('p', { model: 'haiku', label: 'x' })\n" * 9000
        started = time.time()
        res = self.check(src)
        self.assertLess(time.time() - started, 2.0)
        self.assertEqual((res["calls"], res["pinned"], res["missing"]), (9000, 9000, []))

    def test_a_regex_literal_longer_than_the_look_ahead_cap_is_read_as_division(self):
        long_regex = "/" + ("a" * (wm.MAX_REGEX_LITERAL + 50)) + "/"
        res = self.check("const r = %s\nawait agent('p', { label: 'z' })" % long_regex)
        self.assertEqual(len(res["missing"]), 1)

    def test_a_non_ascii_digit_in_code_does_not_crash_the_tokenizer(self):
        res = self.check("const n = \u00b2\nawait agent('p')")
        self.assertEqual(res["calls"], 1)

    def test_garbage_input_never_raises(self):
        for src in ("", "\x00\x01\x02", "}}}{{{", ")))(((", "agent(((", "`${`${`", "/", "'", "agent", "agent?.", "..."):
            with self.subTest(src=src):
                self.check(src)


class Subprocess(unittest.TestCase):
    """The hook as the engine runs it."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.data = os.path.join(self.tmp.name, "data")
        os.mkdir(self.data)

    def run_wf(self, payload=None, env=None, raw=None, timeout=10):
        return run_hook(SCRIPT, payload, env=env, raw=raw, data_dir=self.data, home=self.tmp.name, timeout=timeout)

    def assertSilent(self, result):
        code, out, err = result
        self.assertEqual(code, 0)
        self.assertEqual(out, "")
        self.assertNotIn("Traceback", err)

    def assertWarned(self, result):
        code, out, err = result
        self.assertEqual(code, 0, err)
        self.assertNotIn("Traceback", err)
        body = parse(out)
        self.assertIsNotNone(body, "expected a warning, got silence")
        return body

    def write(self, name, text, mode="w"):
        path = os.path.join(self.tmp.name, name)
        with open(path, mode) as handle:
            handle.write(text)
        return path

    def test_clean_script_is_silent(self):
        self.assertSilent(self.run_wf(workflow_payload(script=fixture("all_pinned.js"))))

    def test_one_unpinned_agent_is_flagged_with_counts_label_and_line(self):
        body = self.assertWarned(self.run_wf(workflow_payload(script=fixture("one_unpinned.js"))))
        self.assertEqual(set(body), {"hookSpecificOutput", "systemMessage"})
        specific = body["hookSpecificOutput"]
        self.assertEqual(set(specific), {"hookEventName", "additionalContext"})
        self.assertEqual(specific["hookEventName"], "PreToolUse")
        self.assertNotIn("permissionDecision", json.dumps(body))
        text = body["systemMessage"]
        self.assertTrue(text.startswith("dojo-router: "))
        self.assertIn("3 agent() calls and 2 set a model", text)
        self.assertIn("line 6", text)
        self.assertIn("label builder", text)
        self.assertIn("DOJO_ROUTER_OFF=1", text)

    def test_unverifiable_options_are_reported_not_passed(self):
        body = self.assertWarned(self.run_wf(workflow_payload(script="await agent('p', opts)")))
        text = body["systemMessage"]
        self.assertIn("1 agent() call and 0 set a model", text)
        self.assertIn("cannot be checked", text)

    def test_unbalanced_script_is_reported_with_exit_zero(self):
        body = self.assertWarned(self.run_wf(workflow_payload(script="const t = `open ${await agent('x', {model: 'haiku'})")))
        self.assertIn("did not parse cleanly", body["systemMessage"])

    def test_non_code_text_without_any_dispatch_is_silent(self):
        self.assertSilent(self.run_wf(workflow_payload(script="export const meta = { name: 'x' }\nconst t = `open")))

    def test_regex_with_quotes_before_an_unpinned_call_is_not_silence(self):
        src = "const r = /['(]/\nawait agent('p', { label: 'z' })"
        body = self.assertWarned(self.run_wf(workflow_payload(script=src)))
        self.assertIn("line 2", body["systemMessage"])

    def test_name_only_is_silent(self):
        self.assertSilent(self.run_wf(workflow_payload(name="some-plugin:build")))

    def test_script_path_is_read_when_script_is_absent(self):
        path = self.write("wf.js", fixture("one_unpinned.js"))
        body = self.assertWarned(self.run_wf(workflow_payload(script_path=path)))
        self.assertIn("line 6", body["systemMessage"])

    def test_script_path_takes_precedence_over_a_clean_inline_script(self):
        path = self.write("wf.js", fixture("one_unpinned.js"))
        body = self.assertWarned(self.run_wf(workflow_payload(script=fixture("all_pinned.js"), script_path=path)))
        self.assertIn("line 6", body["systemMessage"])

    def test_relative_script_path_resolves_against_the_payload_cwd(self):
        self.write("wf.js", fixture("one_unpinned.js"))
        body = self.assertWarned(self.run_wf(workflow_payload(script_path="wf.js", cwd=self.tmp.name)))
        self.assertIn("line 6", body["systemMessage"])

    def test_unreadable_script_path_is_silent_even_with_a_script_present(self):
        missing = os.path.join(self.tmp.name, "nope.js")
        self.assertSilent(self.run_wf(workflow_payload(script_path=missing)))
        self.assertSilent(self.run_wf(workflow_payload(script_path=missing, script=fixture("one_unpinned.js"))))

    def test_directory_script_path_is_silent(self):
        self.assertSilent(self.run_wf(workflow_payload(script_path=self.tmp.name)))

    @unittest.skipUnless(hasattr(os, "mkfifo"), "needs mkfifo")
    def test_fifo_script_path_is_silent_and_does_not_hang(self):
        fifo = os.path.join(self.tmp.name, "pipe.js")
        os.mkfifo(fifo)
        try:
            result = self.run_wf(workflow_payload(script_path=fifo), timeout=3)
        except subprocess.TimeoutExpired:
            self.fail("hook blocked on a FIFO")
        self.assertSilent(result)

    def test_oversized_inputs_are_silent(self):
        big = fixture("one_unpinned.js") + "\n// " + ("x" * (520 * 1024)) + "\n"
        self.assertSilent(self.run_wf(workflow_payload(script_path=self.write("big.js", big))))
        self.assertSilent(self.run_wf(workflow_payload(script=big)))

    def test_the_size_cap_is_512_kb_and_the_edge_is_exact(self):
        self.assertEqual(wm.MAX_SCRIPT_BYTES, 512 * 1024)
        head = "await agent('p', { label: 'z' })\n// "
        for extra, expect_warning in ((0, True), (1, False)):
            with self.subTest(extra=extra):
                body = head + "x" * (wm.MAX_SCRIPT_BYTES + extra - len(head.encode("utf-8")))
                self.assertEqual(len(body.encode("utf-8")), wm.MAX_SCRIPT_BYTES + extra)
                path = self.write("edge%d.js" % extra, body)
                result = self.run_wf(workflow_payload(script_path=path))
                if expect_warning:
                    self.assertIn("line 1", self.assertWarned(result)["systemMessage"])
                else:
                    self.assertSilent(result)
                inline = self.run_wf(workflow_payload(script=body))
                if expect_warning:
                    self.assertWarned(inline)
                else:
                    self.assertSilent(inline)

    def test_unclosed_calls_finish_well_inside_the_hook_timeout(self):
        started = time.time()
        body = self.assertWarned(self.run_wf(workflow_payload(script="agent(" * 5000), timeout=4))
        self.assertLess(time.time() - started, 1.5)
        self.assertIn("5000 agent() calls", body["systemMessage"])

    def test_a_space_flood_after_the_name_does_not_stall_the_hook(self):
        started = time.time()
        result = self.run_wf(workflow_payload(script="agent" + " " * 400000 + "'"), timeout=4)
        self.assertLess(time.time() - started, 2.0)
        self.assertEqual(result[0], 0)

    def test_an_indirect_use_is_reported_once_with_its_line(self):
        src = "const jobs = list.map(agent)\nawait agent('p', { model: 'haiku' })\n"
        body = self.assertWarned(self.run_wf(workflow_payload(script=src)))
        text = body["systemMessage"]
        self.assertIn("1 agent() call and 1 set a model", text)
        self.assertIn("1 reference used agent as a value", text)
        self.assertIn("line 1", text)

    def test_an_indirect_use_alone_warns_but_never_blocks(self):
        src = "await agent.call(null, 'p')"
        body = self.assertWarned(self.run_wf(workflow_payload(script=src), env={"CLAUDE_PLUGIN_OPTION_MODE": "block"}))
        self.assertNotIn("permissionDecision", json.dumps(body))

    def test_inherit_is_flagged_and_blocked_like_a_missing_model(self):
        src = "await agent('p', { model: 'inherit', label: 'x' })"
        code, out, err = self.run_wf(workflow_payload(script=src), env={"CLAUDE_PLUGIN_OPTION_MODE": "block"})
        self.assertEqual(code, 0, err)
        self.assertEqual(parse(out)["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_a_model_method_is_reported_not_blocked(self):
        src = "await agent('p', { get model() { return 'haiku' } })"
        body = self.assertWarned(self.run_wf(workflow_payload(script=src), env={"CLAUDE_PLUGIN_OPTION_MODE": "block"}))
        self.assertNotIn("permissionDecision", json.dumps(body))
        self.assertIn("cannot be checked", body["systemMessage"])

    def test_several_calls_use_the_plural(self):
        body = self.assertWarned(self.run_wf(workflow_payload(script="await agent('a')\nawait agent('b')")))
        self.assertIn("2 agent() calls and 0 set a model", body["systemMessage"])

    def test_non_utf8_bytes_do_not_crash(self):
        raw = fixture("one_unpinned.js").encode("utf-8") + b"\n// \xff\xfe\xfd\n"
        path = self.write("odd.js", raw, mode="wb")
        body = self.assertWarned(self.run_wf(workflow_payload(script_path=path)))
        self.assertIn("line 6", body["systemMessage"])

    def test_block_mode_denies_with_the_lines_listed(self):
        code, out, err = self.run_wf(workflow_payload(script=fixture("one_unpinned.js")),
                                     env={"CLAUDE_PLUGIN_OPTION_MODE": "block"})
        self.assertEqual(code, 0, err)
        body = parse(out)
        specific = body["hookSpecificOutput"]
        self.assertEqual(specific["permissionDecision"], "deny")
        self.assertIn("line 6", specific["permissionDecisionReason"])
        for word in ("haiku", "sonnet", "opus"):
            self.assertIn(word, specific["permissionDecisionReason"])
        self.assertTrue(body["systemMessage"])

    def test_block_mode_only_blocks_what_it_is_sure_of(self):
        body = self.assertWarned(self.run_wf(workflow_payload(script="await agent('p', opts)"),
                                             env={"CLAUDE_PLUGIN_OPTION_MODE": "block"}))
        self.assertNotIn("permissionDecision", json.dumps(body))

    def test_block_mode_clean_script_is_silent(self):
        self.assertSilent(self.run_wf(workflow_payload(script=fixture("all_pinned.js")),
                                      env={"CLAUDE_PLUGIN_OPTION_MODE": "block"}))

    def test_warn_mode_dedupes_per_script_per_session(self):
        first = workflow_payload(script=fixture("one_unpinned.js"), session_id="wf-s1")
        self.assertWarned(self.run_wf(first))
        self.assertSilent(self.run_wf(first))
        other = workflow_payload(script=fixture("one_unpinned.js") + "\nawait agent('more')\n", session_id="wf-s1")
        self.assertWarned(self.run_wf(other))
        again = workflow_payload(script=fixture("one_unpinned.js"), session_id="wf-s2")
        self.assertWarned(self.run_wf(again))

    def test_mode_off_and_kill_switches_are_silent(self):
        payload = workflow_payload(script=fixture("one_unpinned.js"))
        self.assertSilent(self.run_wf(payload, env={"CLAUDE_PLUGIN_OPTION_MODE": "off"}))
        self.assertSilent(self.run_wf(payload, env={"DOJO_OFF": "1"}))
        self.assertSilent(self.run_wf(payload, env={"DOJO_ROUTER_OFF": "1"}))
        self.assertWarned(self.run_wf(workflow_payload(script=fixture("one_unpinned.js")), env={"DOJO_OFF": "0"}))

    def test_other_tools_are_silent(self):
        for name in ("Agent", "WorkflowX", "Bash", None):
            with self.subTest(name=name):
                payload = workflow_payload(script=fixture("one_unpinned.js"))
                if name is None:
                    del payload["tool_name"]
                else:
                    payload["tool_name"] = name
                self.assertSilent(self.run_wf(payload))

    def test_garbage_input_fails_open(self):
        for raw in ("", "not json", "[]", '"x"', "null", b"\xff\xfe"):
            with self.subTest(raw=raw):
                self.assertSilent(self.run_wf(raw=raw))
        for tool_input in ([], None, "text", 5):
            with self.subTest(tool_input=tool_input):
                payload = workflow_payload(script="x")
                payload["tool_input"] = tool_input
                self.assertSilent(self.run_wf(payload))
        for script in (5, ["agent('p')"], None):
            with self.subTest(script=script):
                payload = workflow_payload()
                payload["tool_input"]["script"] = script
                self.assertSilent(self.run_wf(payload))


class SelfLint(unittest.TestCase):
    """If the suite's own workflows are present beside this plugin, none may carry an unpinned agent()."""

    def test_sibling_workflows_pin_every_agent_call(self):
        pattern = os.path.join(TESTS_DIR, "..", "..", "dojo-flow", "workflows", "*.js")
        files = sorted(glob.glob(pattern))
        if not files:
            self.skipTest("no sibling workflows present")
        for path in files:
            with open(path, encoding="utf-8", errors="replace") as handle:
                res = wm.check_source(handle.read())
            with self.subTest(file=os.path.basename(path)):
                self.assertGreater(res["calls"], 0)
                self.assertEqual(res["missing"], [])


if __name__ == "__main__":
    unittest.main()
