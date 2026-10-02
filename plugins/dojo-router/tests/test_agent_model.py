"""Tests for hooks/agent_model.py: hand-written payloads in, stdout JSON and exit code out."""
import json
import os
import stat
import tempfile
import time
import unittest

from _helpers import agent_payload, parse, run_hook

SCRIPT = "agent_model.py"


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.data = os.path.join(self.tmp.name, "data")
        os.mkdir(self.data)
        self.home = os.path.join(self.tmp.name, "home")
        os.mkdir(self.home)
        self.config = os.path.join(self.tmp.name, "config")
        os.mkdir(self.config)
        self.cwd = os.path.join(self.tmp.name, "proj")
        os.mkdir(self.cwd)
        os.mkdir(os.path.join(self.cwd, ".git"))  # the project is a repository root: the folder climb stops here

    def run_agent(self, payload, env=None, raw=None):
        merged = {"CLAUDE_CONFIG_DIR": self.config}
        if env:
            merged.update(env)
        return run_hook(SCRIPT, payload, env=merged, raw=raw, data_dir=self.data, home=self.home)

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

    def write_agent(self, directory, filename, text):
        os.makedirs(directory, exist_ok=True)
        with open(os.path.join(directory, filename), "w", encoding="utf-8") as handle:
            handle.write(text)


class WarnShape(Base):
    def test_unpinned_general_purpose_warns_with_the_exact_shape(self):
        body = self.assertWarned(self.run_agent(agent_payload("general-purpose")))
        self.assertEqual(set(body), {"hookSpecificOutput", "systemMessage"})
        specific = body["hookSpecificOutput"]
        self.assertEqual(specific["hookEventName"], "PreToolUse")
        self.assertEqual(set(specific), {"hookEventName", "additionalContext"})
        self.assertIsInstance(specific["additionalContext"], str)
        self.assertNotIn("permissionDecision", json.dumps(body))
        text = body["systemMessage"]
        self.assertTrue(text.startswith("dojo-router: "))
        for word in ("haiku", "sonnet", "opus", "DOJO_ROUTER_OFF=1"):
            self.assertIn(word, text)
        self.assertIn("suggested here: sonnet", text)
        self.assertEqual(specific["additionalContext"], text)

    def test_missing_subagent_type_is_treated_as_general_purpose(self):
        body = self.assertWarned(self.run_agent(agent_payload()))
        self.assertIn("general-purpose dispatch", body["systemMessage"])

    def test_blank_subagent_type_is_treated_as_general_purpose(self):
        body = self.assertWarned(self.run_agent(agent_payload("   ")))
        self.assertIn("general-purpose dispatch", body["systemMessage"])

    def test_explore_suggests_the_explore_tier(self):
        body = self.assertWarned(self.run_agent(agent_payload("Explore")))
        self.assertIn("suggested here: haiku", body["systemMessage"])

    def test_plan_warns(self):
        body = self.assertWarned(self.run_agent(agent_payload("Plan")))
        self.assertIn("Plan dispatch", body["systemMessage"])
        self.assertNotIn("ignore this", body["systemMessage"])

    def test_task_alias_warns(self):
        self.assertWarned(self.run_agent(agent_payload("general-purpose", tool_name="Task")))

    def test_unknown_custom_type_warns_with_the_pin_clause(self):
        body = self.assertWarned(self.run_agent(agent_payload("my-helper")))
        self.assertIn("pins a model, ignore this", body["systemMessage"])

    def test_the_rewritten_shape_the_mod_produces_is_silent(self):
        # What the mod hands the classic hook beneath it: the same call with a model filled in.
        payload = agent_payload("general-purpose", model="sonnet")
        payload["tool_input"].update({"run_in_background": True, "name": "worker"})
        self.assertSilent(self.run_agent(payload))


class SilentCases(Base):
    def test_named_models_are_silent(self):
        for model in ("haiku", "sonnet", "opus", "sonnet[1m]"):
            with self.subTest(model=model):
                self.assertSilent(self.run_agent(agent_payload("general-purpose", model=model)))

    def test_plugin_agent_type_is_silent(self):
        self.assertSilent(self.run_agent(agent_payload("some-plugin:reviewer")))

    def test_fork_is_silent(self):
        self.assertSilent(self.run_agent(agent_payload("fork")))

    def test_built_in_that_pins_its_own_model_is_silent(self):
        self.assertSilent(self.run_agent(agent_payload("statusline-setup")))

    def test_other_tool_names_are_silent(self):
        for name in ("TaskStop", "AgentX", "Bash", "Workflow", None):
            with self.subTest(name=name):
                payload = agent_payload("general-purpose")
                if name is None:
                    del payload["tool_name"]
                else:
                    payload["tool_name"] = name
                self.assertSilent(self.run_agent(payload))

    def test_mode_off_is_silent(self):
        self.assertSilent(self.run_agent(agent_payload(), env={"CLAUDE_PLUGIN_OPTION_MODE": "off"}))

    def test_kill_switches_are_silent(self):
        for name in ("DOJO_OFF", "DOJO_ROUTER_OFF"):
            with self.subTest(name=name):
                self.assertSilent(self.run_agent(agent_payload(), env={name: "1"}))

    def test_kill_switch_negative_controls_still_warn(self):
        self.assertWarned(self.run_agent(agent_payload(), env={"DOJO_OFF": "0"}))
        self.assertWarned(self.run_agent(agent_payload(), env={"DOJO_ROUTER_OFF": ""}))

    def test_subagent_model_env_makes_the_warning_moot(self):
        for name in ("CLAUDE_CODE_SUBAGENT_MODEL", "CLAUDE_CODE_SUBAGENT_MODEL_FORCE"):
            with self.subTest(name=name):
                self.assertSilent(self.run_agent(agent_payload(), env={name: "haiku"}))

    def test_empty_subagent_model_env_does_not_silence(self):
        self.assertWarned(self.run_agent(agent_payload(), env={"CLAUDE_CODE_SUBAGENT_MODEL": "  "}))


class MissingModelForms(Base):
    def test_these_all_count_as_missing(self):
        for model in (None, "", "   ", "inherit", " Inherit "):
            with self.subTest(model=model):
                self.assertWarned(self.run_agent(agent_payload("general-purpose", model=model)))


class BlockMode(Base):
    def test_block_mode_denies_with_the_exact_shape_every_time(self):
        for _ in range(3):
            code, out, err = self.run_agent(agent_payload("general-purpose"), env={"CLAUDE_PLUGIN_OPTION_MODE": "block"})
            self.assertEqual(code, 0, err)
            body = parse(out)
            self.assertEqual(set(body), {"hookSpecificOutput", "systemMessage"})
            specific = body["hookSpecificOutput"]
            self.assertEqual(specific["hookEventName"], "PreToolUse")
            self.assertEqual(specific["permissionDecision"], "deny")
            reason = specific["permissionDecisionReason"]
            self.assertIsInstance(reason, str)
            for word in ("haiku", "sonnet", "opus"):
                self.assertIn(word, reason)
            self.assertTrue(body["systemMessage"])

    def test_block_mode_leaves_a_pinned_dispatch_alone(self):
        self.assertSilent(self.run_agent(agent_payload("general-purpose", model="haiku"),
                                         env={"CLAUDE_PLUGIN_OPTION_MODE": "block"}))

    def test_block_mode_denies_every_unpinned_built_in(self):
        for agent_type in ("general-purpose", "Explore", "Plan"):
            with self.subTest(agent_type=agent_type):
                body = parse(self.run_agent(agent_payload(agent_type),
                                            env={"CLAUDE_PLUGIN_OPTION_MODE": "block"})[1])
                self.assertEqual(body["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_the_deny_text_never_tells_the_model_to_ignore_it(self):
        body = parse(self.run_agent(agent_payload("Explore"), env={"CLAUDE_PLUGIN_OPTION_MODE": "block"})[1])
        reason = body["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertNotIn("ignore", reason.lower())
        self.assertIn("Retry the call with model set", reason)

    def test_block_mode_only_warns_about_a_custom_agent_it_cannot_see_into(self):
        # A custom agent may pin its own model somewhere this hook cannot read (a command-line flag,
        # a managed folder). Refusing it would leave no way through except overriding that pin.
        body = self.assertWarned(self.run_agent(agent_payload("my-helper", cwd=self.cwd),
                                                env={"CLAUDE_PLUGIN_OPTION_MODE": "block"}))
        self.assertNotIn("permissionDecision", json.dumps(body))
        text = body["systemMessage"]
        self.assertIn("pins a model, ignore this", text)
        self.assertIn("Block mode refuses built-in agent types only", text)

    def test_block_mode_custom_warning_is_once_per_session(self):
        payload = agent_payload("my-helper", session_id="s-block-custom", cwd=self.cwd)
        env = {"CLAUDE_PLUGIN_OPTION_MODE": "block"}
        self.assertWarned(self.run_agent(payload, env=env))
        self.assertSilent(self.run_agent(payload, env=env))

    def test_block_mode_stays_silent_for_a_custom_agent_that_pins_a_model(self):
        self.write_agent(os.path.join(self.config, "agents", "team"), "n.md", "---\nname: helper\nmodel: haiku\n---\n")
        self.assertSilent(self.run_agent(agent_payload("helper", cwd=self.cwd),
                                         env={"CLAUDE_PLUGIN_OPTION_MODE": "block"}))

    def test_block_mode_still_denies_a_built_in_name_whose_override_does_not_pin(self):
        self.write_agent(os.path.join(self.config, "agents"), "explore.md", "---\nname: Explore\nmodel: inherit\n---\n")
        body = parse(self.run_agent(agent_payload("Explore", cwd=self.cwd),
                                    env={"CLAUDE_PLUGIN_OPTION_MODE": "block"})[1])
        self.assertEqual(body["hookSpecificOutput"]["permissionDecision"], "deny")


class WarnDedupe(Base):
    def test_same_session_and_type_warns_once(self):
        payload = agent_payload("general-purpose", session_id="s-dedupe")
        self.assertWarned(self.run_agent(payload))
        self.assertSilent(self.run_agent(payload))

    def test_a_different_type_in_the_same_session_warns(self):
        self.assertWarned(self.run_agent(agent_payload("general-purpose", session_id="s2")))
        self.assertWarned(self.run_agent(agent_payload("Explore", session_id="s2")))

    def test_a_different_session_warns_again(self):
        self.assertWarned(self.run_agent(agent_payload("general-purpose", session_id="s3")))
        self.assertWarned(self.run_agent(agent_payload("general-purpose", session_id="s4")))

    def test_missing_or_non_string_session_id_warns_every_time(self):
        for sid in (None, 12, ["x"]):
            with self.subTest(sid=sid):
                payload = agent_payload("general-purpose", session_id=None)
                if sid is not None:
                    payload["session_id"] = sid
                self.assertWarned(self.run_agent(payload))
                self.assertWarned(self.run_agent(payload))

    def test_hostile_ids_stay_inside_the_state_dir(self):
        before = set(os.listdir(self.tmp.name))
        self.assertWarned(self.run_agent(agent_payload("a/b/../../c", session_id="../../evil")))
        self.assertWarned(self.run_agent(agent_payload("general-purpose", session_id="/etc/x")))
        self.assertEqual(set(os.listdir(self.tmp.name)), before)
        state = os.path.join(self.data, "dojo-router-state")
        self.assertEqual(len(os.listdir(state)), 2)
        self.assertEqual(os.listdir(self.data), ["dojo-router-state"])

    @unittest.skipIf(not hasattr(os, "geteuid") or os.geteuid() == 0, "needs a non-root user")
    def test_unwritable_state_still_warns_and_exits_zero(self):
        os.chmod(self.data, stat.S_IRUSR | stat.S_IXUSR)
        self.addCleanup(os.chmod, self.data, stat.S_IRWXU)
        payload = agent_payload("general-purpose", session_id="s-locked")
        self.assertWarned(self.run_agent(payload))
        self.assertWarned(self.run_agent(payload))


class CustomAgents(Base):
    def user_dir(self):
        return os.path.join(self.config, "agents")

    def project_dir(self):
        return os.path.join(self.cwd, ".claude", "agents")

    def test_user_agent_with_a_model_pin_is_silent(self):
        self.write_agent(self.user_dir(), "helper.md", "---\nname: helper\nmodel: sonnet\n---\nBody.\n")
        self.assertSilent(self.run_agent(agent_payload("helper", cwd=self.cwd)))

    def test_project_agent_with_a_model_pin_is_silent(self):
        self.write_agent(self.project_dir(), "helper.md", "---\nname: helper\nmodel: haiku\n---\nBody.\n")
        self.assertSilent(self.run_agent(agent_payload("helper", cwd=self.cwd)))

    def test_inherit_is_not_a_pin(self):
        self.write_agent(self.user_dir(), "helper.md", "---\nname: helper\nmodel: inherit\n---\n")
        self.assertWarned(self.run_agent(agent_payload("helper", cwd=self.cwd)))

    def test_no_model_line_is_not_a_pin(self):
        self.write_agent(self.user_dir(), "helper.md", "---\nname: helper\ndescription: x\n---\n")
        self.assertWarned(self.run_agent(agent_payload("helper", cwd=self.cwd)))

    def test_match_is_on_the_frontmatter_name_not_the_filename(self):
        self.write_agent(self.user_dir(), "unrelated-file.md", "---\nname: helper\nmodel: opus\n---\n")
        self.assertSilent(self.run_agent(agent_payload("helper", cwd=self.cwd)))
        self.write_agent(self.user_dir(), "other.md", "---\nname: someone-else\nmodel: opus\n---\n")
        self.assertWarned(self.run_agent(agent_payload("other", cwd=self.cwd)))

    def test_a_pinned_override_of_a_built_in_name_is_respected(self):
        self.write_agent(self.user_dir(), "explore.md", "---\nname: Explore\nmodel: haiku\n---\n")
        self.assertSilent(self.run_agent(agent_payload("Explore", cwd=self.cwd)))

    def test_nested_user_agent_with_a_pin_is_silent(self):
        self.write_agent(os.path.join(self.user_dir(), "team"), "n.md", "---\nname: helper\nmodel: haiku\n---\n")
        self.assertSilent(self.run_agent(agent_payload("helper", cwd=self.cwd)))

    def test_deeply_nested_user_agent_with_a_pin_is_silent(self):
        self.write_agent(os.path.join(self.user_dir(), "a", "b", "c"), "n.md", "---\nname: helper\nmodel: opus\n---\n")
        self.assertSilent(self.run_agent(agent_payload("helper", cwd=self.cwd)))

    def test_nested_project_agent_with_a_pin_is_silent(self):
        self.write_agent(os.path.join(self.project_dir(), "review"), "n.md", "---\nname: helper\nmodel: sonnet\n---\n")
        self.assertSilent(self.run_agent(agent_payload("helper", cwd=self.cwd)))

    def test_project_agent_is_found_from_a_subfolder_of_the_repository(self):
        self.write_agent(self.project_dir(), "helper.md", "---\nname: helper\nmodel: haiku\n---\n")
        deep = os.path.join(self.cwd, "services", "api")
        os.makedirs(deep)
        self.assertSilent(self.run_agent(agent_payload("helper", cwd=deep)))

    def test_a_nearer_agents_folder_wins_over_a_parent_one(self):
        self.write_agent(self.project_dir(), "helper.md", "---\nname: helper\nmodel: haiku\n---\n")
        sub = os.path.join(self.cwd, "pkg")
        self.write_agent(os.path.join(sub, ".claude", "agents"), "helper.md", "---\nname: helper\nmodel: inherit\n---\n")
        self.assertWarned(self.run_agent(agent_payload("helper", cwd=sub)))

    def test_the_climb_stops_at_the_repository_root(self):
        outer = os.path.join(self.tmp.name, "outer")
        repo = os.path.join(outer, "repo")
        deep = os.path.join(repo, "a", "b")
        os.makedirs(deep)
        os.mkdir(os.path.join(repo, ".git"))
        self.write_agent(os.path.join(outer, ".claude", "agents"), "helper.md", "---\nname: helper\nmodel: haiku\n---\n")
        self.assertWarned(self.run_agent(agent_payload("helper", cwd=deep)))  # above the root: not read
        self.write_agent(os.path.join(repo, ".claude", "agents"), "helper.md", "---\nname: helper\nmodel: haiku\n---\n")
        self.assertSilent(self.run_agent(agent_payload("helper", cwd=deep)))  # at the root: read

    def test_without_a_repository_the_climb_continues_upward(self):
        top = os.path.join(self.tmp.name, "norepo")
        deep = os.path.join(top, "a", "b")
        os.makedirs(deep)
        self.write_agent(os.path.join(top, ".claude", "agents"), "helper.md", "---\nname: helper\nmodel: haiku\n---\n")
        self.assertSilent(self.run_agent(agent_payload("helper", cwd=deep)))

    def test_a_relative_or_missing_cwd_does_not_crash(self):
        for cwd in ("", "relative/dir", "/definitely/not/here", None):
            with self.subTest(cwd=cwd):
                code, out, err = self.run_agent(agent_payload("helper", cwd=cwd))
                self.assertEqual(code, 0)
                self.assertNotIn("Traceback", err)

    def test_a_symlinked_folder_loop_is_not_followed(self):
        os.makedirs(self.user_dir())
        try:
            os.symlink(self.user_dir(), os.path.join(self.user_dir(), "loop"))
        except (OSError, NotImplementedError):
            self.skipTest("no symlinks here")
        self.write_agent(self.user_dir(), "helper.md", "---\nname: helper\nmodel: haiku\n---\n")
        started = time.time()
        self.assertSilent(self.run_agent(agent_payload("helper", cwd=self.cwd)))
        self.assertLess(time.time() - started, 3.0)

    def test_nested_files_are_bounded_too(self):
        # 300 pinned agents in nested folders and the one we want past the cap: it is not found, so it
        # warns, and the scan stays quick. Nothing is claimed beyond "bounded".
        for i in range(300):
            self.write_agent(os.path.join(self.user_dir(), "g%02d" % (i % 10)), "a%03d.md" % i,
                             "---\nname: a%03d\nmodel: sonnet\n---\n" % i)
        started = time.time()
        self.assertWarned(self.run_agent(agent_payload("zzz-beyond-the-cap", cwd=self.cwd)))
        self.assertLess(time.time() - started, 3.0)

    def test_malformed_and_binary_files_fail_open(self):
        self.write_agent(self.user_dir(), "broken.md", "---\nname: helper\nmodel sonnet but never closed\n")
        with open(os.path.join(self.user_dir(), "blob.md"), "wb") as handle:
            handle.write(bytes(range(256)) * 20)
        code, out, err = self.run_agent(agent_payload("helper", cwd=self.cwd))
        self.assertEqual(code, 0)
        self.assertNotIn("Traceback", err)
        self.assertIsNotNone(parse(out))  # nothing pinned could be read, so it still warns

    def test_an_oversized_agent_file_is_skipped(self):
        big = "---\nname: helper\nmodel: sonnet\n---\n" + ("x" * (70 * 1024))
        self.write_agent(self.user_dir(), "helper.md", big)
        self.assertWarned(self.run_agent(agent_payload("helper", cwd=self.cwd)))

    def test_scan_stays_fast_with_many_agent_files(self):
        for i in range(200):
            self.write_agent(self.user_dir(), "a%03d.md" % i, "---\nname: a%03d\nmodel: sonnet\n---\n" % i)
        started = time.time()
        result = self.run_agent(agent_payload("general-purpose", cwd=self.cwd))
        elapsed = time.time() - started
        self.assertWarned(result)
        self.assertLess(elapsed, 1.0)  # a bound on the scan, not a benchmark claim


class FailOpen(Base):
    def test_unusable_stdin_is_silent(self):
        for raw in ("", "not json", "[]", '"a string"', "null", "7", b"\xff\xfe\x00"):
            with self.subTest(raw=raw):
                self.assertSilent(self.run_agent(None, raw=raw))

    def test_odd_tool_input_is_silent(self):
        for tool_input in ([], None, "text", 5, ["x"]):
            with self.subTest(tool_input=tool_input):
                payload = agent_payload("general-purpose")
                payload["tool_input"] = tool_input
                self.assertSilent(self.run_agent(payload))

    def test_odd_subagent_type_is_silent(self):
        for value in (5, ["Explore"], {"a": 1}, True):
            with self.subTest(value=value):
                payload = agent_payload("general-purpose")
                payload["tool_input"]["subagent_type"] = value
                self.assertSilent(self.run_agent(payload))

    def test_odd_model_value_is_silent(self):
        for value in (5, ["haiku"], {"a": 1}):
            with self.subTest(value=value):
                payload = agent_payload("general-purpose")
                payload["tool_input"]["model"] = value
                self.assertSilent(self.run_agent(payload))

    def test_odd_cwd_and_session_values_do_not_crash(self):
        payload = agent_payload("general-purpose")
        payload["cwd"] = 12
        payload["session_id"] = {"x": 1}
        code, out, err = self.run_agent(payload)
        self.assertEqual(code, 0)
        self.assertNotIn("Traceback", err)


class Options(Base):
    def test_option_values_are_case_insensitive_and_stripped(self):
        code, out, _ = self.run_agent(agent_payload(), env={"CLAUDE_PLUGIN_OPTION_MODE": "BLOCK"})
        self.assertEqual(parse(out)["hookSpecificOutput"]["permissionDecision"], "deny")
        body = self.assertWarned(self.run_agent(agent_payload(), env={"CLAUDE_PLUGIN_OPTION_MODE": " warn "}))
        self.assertNotIn("permissionDecision", json.dumps(body))

    def test_unknown_mode_falls_back_to_warn(self):
        body = self.assertWarned(self.run_agent(agent_payload(), env={"CLAUDE_PLUGIN_OPTION_MODE": "bogus"}))
        self.assertNotIn("permissionDecision", json.dumps(body))

    def test_default_tier_is_reflected(self):
        body = self.assertWarned(self.run_agent(agent_payload(), env={"CLAUDE_PLUGIN_OPTION_DEFAULT_TIER": "opus"}))
        self.assertIn("suggested here: opus", body["systemMessage"])

    def test_invalid_default_tier_falls_back_to_sonnet(self):
        for value in ("bogus", "gpt-9", ""):
            with self.subTest(value=value):
                body = self.assertWarned(self.run_agent(agent_payload(), env={"CLAUDE_PLUGIN_OPTION_DEFAULT_TIER": value}))
                self.assertIn("suggested here: sonnet", body["systemMessage"])

    def test_explore_tier_option(self):
        body = self.assertWarned(self.run_agent(agent_payload("Explore"), env={"CLAUDE_PLUGIN_OPTION_EXPLORE_TIER": "sonnet"}))
        self.assertIn("suggested here: sonnet", body["systemMessage"])

    def test_default_tier_does_not_affect_explore(self):
        body = self.assertWarned(self.run_agent(agent_payload("Explore"), env={"CLAUDE_PLUGIN_OPTION_DEFAULT_TIER": "opus"}))
        self.assertIn("suggested here: haiku", body["systemMessage"])


if __name__ == "__main__":
    unittest.main()
