"""The Stop hook, run as a subprocess against hand-written transcripts and payloads."""
import json
import os
import time
import unittest

import _helpers as h


class Base(unittest.TestCase):
    def setUp(self):
        self.sb = h.Sandbox(self)

    def run_hook(self, entries=None, env=None, stdin=None, **payload_kw):
        if entries is not None:
            self.sb.write(entries)
        payload = stdin if stdin is not None else self.sb.payload(**payload_kw)
        return h.run_hook(payload, env if env is not None else self.sb.env(), cwd=self.sb.project)

    def claim_turn(self, final="Fixed. The tests pass.", middle=None):
        """A turn with a claim and, by default, only an edit behind it. `middle` comes after the edit."""
        return [h.prompt("please fix the bug"), h.edit_use("e1"), h.tool_result("e1", "ok")] + (middle or []) + [
            h.assistant_text(final)
        ]


class TestKillSwitchesAndModes(Base):
    def test_default_mode_blocks_with_the_documented_shape(self):
        r = self.run_hook(self.claim_turn())
        self.assertEqual(r.code, 0)
        self.assertEqual(r.err, "")
        data = r.json()
        self.assertEqual(data["decision"], "block")
        self.assertTrue(data["reason"].startswith("dojo-verify:"))
        self.assertIn("unverified", data["reason"])
        self.assertIn("DOJO_VERIFY_OFF=1", data["reason"])
        self.assertIn("mode=warn", data["reason"])

    def test_reason_quotes_at_most_sixty_characters_of_the_claim(self):
        long_claim = "Fixed " + "the very long thing " * 20 + "and it all works."
        r = self.run_hook(self.claim_turn(final=long_claim))
        reason = r.json()["reason"]
        quoted = reason.split('"')[1]
        self.assertLessEqual(len(quoted), 60)
        self.assertTrue(quoted.endswith("..."))

    def test_reason_collapses_newlines_and_control_characters(self):
        r = self.run_hook(self.claim_turn(final="Fixed\tthe\x07bug\nright now"))
        reason = r.json()["reason"]
        self.assertNotIn("\x07", reason)
        self.assertNotIn("\n", reason)

    def test_dojo_off_is_silent(self):
        r = self.run_hook(self.claim_turn(), env=self.sb.env(DOJO_OFF="1"))
        self.assertTrue(r.silent)

    def test_dojo_verify_off_is_silent(self):
        r = self.run_hook(self.claim_turn(), env=self.sb.env(DOJO_VERIFY_OFF="1"))
        self.assertTrue(r.silent)

    def test_true_also_counts_as_off(self):
        r = self.run_hook(self.claim_turn(), env=self.sb.env(DOJO_VERIFY_OFF="true"))
        self.assertTrue(r.silent)

    def test_zero_does_not_turn_anything_off(self):
        r = self.run_hook(self.claim_turn(), env=self.sb.env(DOJO_OFF="0", DOJO_VERIFY_OFF="0"))
        self.assertTrue(r.blocked)

    def test_warn_mode_is_a_system_message_only_and_case_insensitive(self):
        r = self.run_hook(self.claim_turn(), env=self.sb.env(CLAUDE_PLUGIN_OPTION_MODE="WARN"))
        self.assertEqual(r.code, 0)
        data = r.json()
        self.assertNotIn("decision", data)
        self.assertTrue(data["systemMessage"].startswith("dojo-verify:"))

    def test_off_mode_is_silent(self):
        r = self.run_hook(self.claim_turn(), env=self.sb.env(CLAUDE_PLUGIN_OPTION_MODE="off"))
        self.assertTrue(r.silent)

    def test_unknown_mode_falls_back_to_block(self):
        r = self.run_hook(self.claim_turn(), env=self.sb.env(CLAUDE_PLUGIN_OPTION_MODE="garbage"))
        self.assertTrue(r.blocked)

    def test_stop_hook_active_never_blocks(self):
        r = self.run_hook(self.claim_turn(), stop_hook_active=True)
        self.assertTrue(r.silent)

    def test_a_subagent_stop_is_skipped(self):
        r = self.run_hook(self.claim_turn(), agent_id="a1", agent_type="general-purpose")
        self.assertTrue(r.silent)


class TestFailOpen(Base):
    def assert_open(self, r):
        self.assertEqual(r.code, 0)
        self.assertEqual(r.out, "")
        self.assertNotIn("Traceback", r.err)
        self.assertEqual(r.err, "")

    def test_empty_stdin(self):
        self.assert_open(h.run_hook(b"", self.sb.env(), cwd=self.sb.project))

    def test_non_json_stdin(self):
        self.assert_open(h.run_hook(b"this is not json", self.sb.env(), cwd=self.sb.project))

    def test_json_array_stdin(self):
        self.assert_open(h.run_hook(b"[1, 2, 3]", self.sb.env(), cwd=self.sb.project))

    def test_missing_transcript_path(self):
        self.assert_open(self.run_hook(stdin={"session_id": "s", "stop_hook_active": False,
                                              "last_assistant_message": "Fixed and deployed."}))

    def test_null_transcript_path(self):
        self.assert_open(self.run_hook(stdin=self.sb.payload(transcript_path=None,
                                                             last_assistant_message="Fixed and deployed.")))

    def test_nonexistent_file(self):
        p = self.sb.payload(transcript_path=os.path.join(self.sb.root, "nope.jsonl"),
                            last_assistant_message="Fixed and deployed.")
        self.assert_open(self.run_hook(stdin=p))

    def test_directory_as_transcript_path(self):
        p = self.sb.payload(transcript_path=self.sb.project, last_assistant_message="Fixed and deployed.")
        self.assert_open(self.run_hook(stdin=p))

    def test_binary_garbage_file(self):
        with open(self.sb.transcript, "wb") as fh:
            fh.write(bytes(range(256)) * 400)
        self.assert_open(self.run_hook(last_assistant_message="Fixed and deployed."))

    def test_malformed_lines_are_skipped_not_fatal(self):
        self.sb.write(self.claim_turn(final="Fixed."), raw_tail="{not json\n[1,2]\n\"str\"\n")
        r = self.run_hook()
        self.assertTrue(r.blocked)

    def test_malformed_lines_in_the_middle(self):
        with open(self.sb.transcript, "w") as fh:
            fh.write(json.dumps(h.prompt("go")) + "\n")
            fh.write(json.dumps(h.edit_use("e1")) + "\n")
            fh.write("{broken\n\n\n")
            fh.write(json.dumps(h.tool_result("e1", "ok")) + "\n")
            fh.write(json.dumps(h.assistant_text("Fixed and deployed.")) + "\n")
        r = self.run_hook()
        self.assertTrue(r.blocked)

    def test_stdin_over_one_megabyte(self):
        big = json.dumps(self.sb.payload(last_assistant_message="Fixed. " + "x" * (1024 * 1024 + 10)))
        self.sb.write(self.claim_turn())
        self.assert_open(h.run_hook(big.encode("utf-8"), self.sb.env(), cwd=self.sb.project))

    def test_non_string_fields_do_not_crash(self):
        self.sb.write(self.claim_turn())
        p = self.sb.payload(last_assistant_message=["Fixed."], session_id=12345, stop_hook_active="no")
        r = self.run_hook(stdin=p)
        self.assertEqual(r.code, 0)
        self.assertEqual(r.err, "")


class TestEvidence(Base):
    def test_claim_with_a_passing_check_is_silent(self):
        r = self.run_hook(self.claim_turn(middle=h.passing_check("b1")))
        self.assertTrue(r.silent)

    def test_claim_with_an_edit_only_is_blocked(self):
        self.assertTrue(self.run_hook(self.claim_turn()).blocked)

    def test_claim_when_the_check_result_is_an_error(self):
        mid = [h.bash_use("b1", "pytest -q"), h.tool_result("b1", "FAILED tests/test_a.py", is_error=True)]
        self.assertTrue(self.run_hook(self.claim_turn(middle=mid)).blocked)

    def test_claim_when_the_result_starts_with_exit_code_and_is_error_is_missing(self):
        mid = [h.bash_use("b1", "pytest -q"), h.tool_result("b1", "Exit code 1\n1 failed")]
        self.assertTrue(self.run_hook(self.claim_turn(middle=mid)).blocked)

    def test_claim_when_the_check_was_interrupted(self):
        mid = [h.bash_use("b1", "pytest -q"), h.tool_result("b1", "3 passed", interrupted=True)]
        self.assertTrue(self.run_hook(self.claim_turn(middle=mid)).blocked)

    def test_a_check_with_no_result_is_not_evidence(self):
        mid = [h.bash_use("b1", "pytest -q")]
        self.assertTrue(self.run_hook(self.claim_turn(middle=mid)).blocked)

    def test_a_check_before_the_last_edit_does_not_count(self):
        entries = [h.prompt("go")] + h.passing_check("b1") + [h.edit_use("e1"), h.tool_result("e1", "ok"),
                                                                 h.assistant_text("Fixed.")]
        self.assertTrue(self.run_hook(entries).blocked)

    def test_a_check_after_the_last_edit_counts_even_with_an_earlier_edit(self):
        entries = ([h.prompt("go"), h.edit_use("e1"), h.tool_result("e1", "ok")] + h.passing_check("b1")
                   + [h.edit_use("e2"), h.tool_result("e2", "ok")] + h.passing_check("b2")
                   + [h.assistant_text("Fixed.")])
        self.assertTrue(self.run_hook(entries).silent)

    def test_a_failed_edit_is_not_a_change(self):
        entries = ([h.prompt("go"), h.edit_use("e1"), h.tool_result("e1", "ok")] + h.passing_check("b1")
                   + [h.edit_use("e2"), h.tool_result("e2", "String to replace not found", is_error=True),
                      h.assistant_text("Fixed.")])
        self.assertTrue(self.run_hook(entries).silent)

    def test_every_edit_tool_is_a_change(self):
        for name in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
            with self.subTest(name=name):
                entries = ([h.prompt("go")] + h.passing_check("b1")
                           + [h.tool_use("m1", name, {"file_path": "/work/app/x"}), h.tool_result("m1", "ok"),
                              h.assistant_text("Fixed.")])
                self.assertTrue(self.run_hook(entries).blocked)

    def test_a_session_with_no_change_in_it_is_never_judged(self):
        # Answers that only describe things use these words as adjectives or history; nothing was done.
        for text in [
            "Yes, it's deployed and verified.",
            "It returns the fixed point of the map. Use a fixed seed for repeatable runs.",
            "The bug was fixed in version 2.3.",
            "Your site is deployed on Cloudflare Pages.",
            "The signature is verified by the server.",
            "Tests pass the fixture through conftest.py.",
            "Interest rates are fixed for five years.",
            "All tests pass.",
        ]:
            with self.subTest(text=text):
                entries = [h.prompt("a question"), h.assistant_text(text)]
                self.assertTrue(self.run_hook(entries).silent)

    def test_a_read_only_turn_is_not_judged_either(self):
        entries = [h.prompt("where is it hosted?"), h.tool_use("r1", "Read", {"file_path": "/tmp/x"}),
                   h.tool_result("r1", "name = x"), h.assistant_text("Your site is deployed on Cloudflare Pages.")]
        self.assertTrue(self.run_hook(entries).silent)

    def test_dispatching_an_agent_is_not_a_change_the_hook_can_see(self):
        for name in ("Agent", "Task", "Workflow"):
            with self.subTest(name=name):
                entries = [h.prompt("go"), h.tool_use("a1", name, {"prompt": "do it"}),
                           h.tool_result("a1", "agent says it fixed everything"), h.assistant_text("Fixed and deployed.")]
                self.assertTrue(self.run_hook(entries).silent)

    def test_zero_tool_weak_word_is_not_blocked(self):
        entries = [h.prompt("any other questions?"), h.assistant_text("Done.")]
        self.assertTrue(self.run_hook(entries).silent)

    def test_weak_word_after_an_edit_is_blocked(self):
        entries = [h.prompt("go"), h.edit_use("e1"), h.tool_result("e1", "ok"), h.assistant_text("Done.")]
        self.assertTrue(self.run_hook(entries).blocked)

    def test_weak_word_after_a_command_that_writes_a_file_is_blocked(self):
        entries = [h.prompt("go"), h.bash_use("b1", "echo 5 > retries.txt"), h.tool_result("b1", ""),
                   h.assistant_text("It works.")]
        self.assertTrue(self.run_hook(entries).blocked)

    def test_a_read_only_command_is_not_a_change(self):
        entries = [h.prompt("go"), h.bash_use("b1", "git status"), h.tool_result("b1", "clean"),
                   h.assistant_text("It works.")]
        self.assertTrue(self.run_hook(entries).silent)

    def test_commands_that_change_files_are_changes(self):
        for cmd in ["echo 5 > retries.txt", "cat a >> b", "sed -i '' s/a/b/ f.py", "sed -i.bak s/a/b/ f.py",
                    "perl -pi -e s/a/b/ f.py", "tee out.txt", "mv a b", "cp a b", "rm -rf build", "touch x",
                    "mkdir -p out", "git checkout -- f.py", "git apply fix.patch", "git reset --hard HEAD",
                    "npm install", "pnpm add left-pad", "pip install requests", "prettier --write .", "ruff format .", "cargo fmt", "go mod tidy", "gofmt -w x.go",
                    "dd if=a of=b", "bash -c 'echo hi > f'", "cd src && sed -i '' s/a/b/ f.py"]:
            with self.subTest(cmd=cmd):
                entries = ([h.prompt("go")] + h.passing_check("b1")
                           + [h.bash_use("b2", cmd), h.tool_result("b2", ""), h.assistant_text("Fixed.")])
                self.assertTrue(self.run_hook(entries).blocked)

    def test_a_scratch_file_in_the_temp_directory_is_not_a_change(self):
        for name, inp in (("Write", {"file_path": "/tmp/notes.md", "content": "x"}),
                          ("Edit", {"file_path": "/private/tmp/claude-1/scratch.py", "old_string": "a", "new_string": "b"}),
                          ("NotebookEdit", {"notebook_path": "/var/folders/ab/cd/T/n.ipynb"})):
            with self.subTest(name=name):
                entries = ([h.prompt("go"), h.edit_use("e1"), h.tool_result("e1", "ok")] + h.passing_check("b1")
                           + [h.tool_use("m1", name, inp), h.tool_result("m1", "ok"), h.assistant_text("Fixed.")])
                self.assertTrue(self.run_hook(entries).silent)

    def test_a_project_inside_the_temp_directory_still_counts(self):
        proj = "/private/tmp/somewhere/repo"
        inp = {"file_path": proj + "/notes.txt", "old_string": "a", "new_string": "b"}
        entries = [h.prompt("go"), h.tool_use("m1", "Edit", inp), h.tool_result("m1", "ok"),
                   h.assistant_text("Done. All tests pass.")]
        self.assertTrue(self.run_hook(entries, cwd=proj).blocked)
        scratch = {"file_path": "/private/tmp/elsewhere/scratch.py", "old_string": "a", "new_string": "b"}
        entries = [h.prompt("go"), h.tool_use("m2", "Edit", scratch), h.tool_result("m2", "ok"),
                   h.assistant_text("Done. All tests pass.")]
        self.assertTrue(self.run_hook(entries, cwd=proj).silent)

    def test_commands_that_only_read_are_not_changes(self):
        for cmd in ["git status", "git log -3", "git diff", "git commit -m x", "git add -A", "git push origin main",
                    "ls > /dev/null", "echo hi 2>&1", "cat f.py", "grep -r x .", "npm run dev &> /dev/null",
                    "curl -s https://example.test/ >/dev/null", "ruff check .", "prettier --check .",
                    "pytest 2>&1 | tee out.log", "echo a | tee /dev/null", "git diff > /tmp/patch.diff",
                    "rm -rf /tmp/scratch", "cp a.txt /tmp/a.txt"]:
            with self.subTest(cmd=cmd):
                entries = ([h.prompt("go")] + h.passing_check("b1")
                           + [h.bash_use("b2", cmd), h.tool_result("b2", ""), h.assistant_text("Fixed.")])
                self.assertTrue(self.run_hook(entries).silent)

    def test_a_command_that_writes_and_then_checks_is_backed(self):
        mid = [h.bash_use("b1", "sed -i '' s/a/b/ f.py && pytest -q"), h.tool_result("b1", "3 passed")]
        entries = [h.prompt("go")] + mid + [h.assistant_text("Fixed.")]
        self.assertTrue(self.run_hook(entries).silent)

    def test_a_command_that_checks_and_then_writes_is_not(self):
        mid = [h.bash_use("b1", "pytest -q && sed -i '' s/a/b/ f.py"), h.tool_result("b1", "3 passed")]
        entries = [h.prompt("go")] + mid + [h.assistant_text("Fixed.")]
        self.assertTrue(self.run_hook(entries).blocked)

    def test_a_heredoc_body_is_text_not_commands(self):
        cmd = "cat > check.sh <<'EOF'\npytest\nEOF"
        entries = [h.prompt("go"), h.bash_use("b1", cmd), h.tool_result("b1", ""), h.assistant_text("Fixed.")]
        self.assertTrue(self.run_hook(entries).blocked)
        cmd = "git commit -m \"$(cat <<'EOF'\nIt works, tests pass\nEOF\n)\""
        entries = [h.prompt("go"), h.edit_use("e1"), h.tool_result("e1", "ok"), h.bash_use("b1", cmd),
                   h.tool_result("b1", "1 file changed"), h.assistant_text("Fixed.")]
        self.assertTrue(self.run_hook(entries).blocked)

    def test_a_plain_answer_with_no_claim_is_silent(self):
        entries = [h.prompt("what is this?"), h.assistant_text("It is a hook that reads the transcript.")]
        self.assertTrue(self.run_hook(entries).silent)

    def test_bypass_commands_do_not_count_as_checks(self):
        bypasses = [
            ("ls build/", "a.js"),
            ("cat test_output.log", "all passed"),
            ("test -f setup.py", ""),
            ("[ -f x ]", ""),
            ('echo "pytest passed"', "pytest passed"),
            ('git commit -m "fix tests"', "1 file changed"),
            ("mkdir -p build", ""),
            ("# pytest", ""),
            ("grep -r pytest .", "./a.py:import pytest"),
            ("npm test || true", ""),
            ("pytest; true", ""),
            ("pytest | tail -3", "2 failed, 1 passed"),
            ("pytest -q", "FAILED tests/test_a.py::test_x"),
            ("pytest -q", "Traceback (most recent call last):\n  File x"),
        ]
        for cmd, out in bypasses:
            with self.subTest(cmd=cmd, out=out):
                mid = [h.bash_use("b1", cmd), h.tool_result("b1", out)]
                self.assertTrue(self.run_hook(self.claim_turn(middle=mid)).blocked)

    def test_the_usual_test_runners_count(self):
        runners = ["node --test", "node --test tests/", "python3 tests/test_foo.py", "./scripts/test.sh",
                   "bash scripts/release-check.sh", "sh run-tests.sh", "ctest --output-on-failure", "mix test",
                   "bundle exec rake test", "php artisan test", "go test ./...", "cargo test", "pytest", "vitest run",
                   "jest", "npm test", "pnpm test", "yarn test", "make test", "make check",
                   'CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1 "$CLAUDE_BIN" plugin test plugins/x']
        for cmd in runners:
            with self.subTest(cmd=cmd):
                mid = [h.bash_use("b1", cmd), h.tool_result("b1", "ok")]
                self.assertTrue(self.run_hook(self.claim_turn(middle=mid)).silent)

    def test_dry_runs_and_help_do_not_count(self):
        for cmd in ["make -n test", "make --dry-run check", "just --dry-run test", "python3 tests/test_foo.py --help"]:
            with self.subTest(cmd=cmd):
                mid = [h.bash_use("b1", cmd), h.tool_result("b1", "pytest")]
                self.assertTrue(self.run_hook(self.claim_turn(middle=mid)).blocked)

    def test_real_checks_count(self):
        positives = [
            "cd pkg && pytest -q",
            "FOO=1 npm run test",
            "uv run pytest",
            "python3 -m unittest discover",
            "npx vitest run",
            'bash -c "go test ./..."',
            "pnpm typecheck",
            "cargo clippy",
            "make check",
            "curl -sf https://example.test/health",
        ]
        for cmd in positives:
            with self.subTest(cmd=cmd):
                mid = [h.bash_use("b1", cmd), h.tool_result("b1", "ok")]
                self.assertTrue(self.run_hook(self.claim_turn(middle=mid)).silent)

    def test_masked_idioms_do_not_count(self):
        cases = [
            ("pytest -q >/dev/null 2>&1 && echo ok || echo broken", "broken"),
            ('npm test && echo PASS || echo "tests had problems"', "tests had problems"),
            ("pytest > out.log 2>&1; echo done", "done"),
        ]
        for cmd, out in cases:
            with self.subTest(cmd=cmd):
                mid = [h.bash_use("b1", cmd), h.tool_result("b1", out)]
                self.assertTrue(self.run_hook(self.claim_turn(middle=mid)).blocked)

    def test_a_check_that_reaches_a_visible_ok_still_counts(self):
        for cmd, out in [("pytest && echo ok || exit 1", "1 passed\nok"),
                         ('npm test && echo PASS || echo "tests had problems"', "5 passed\nPASS")]:
            with self.subTest(cmd=cmd):
                mid = [h.bash_use("b1", cmd), h.tool_result("b1", out)]
                self.assertTrue(self.run_hook(self.claim_turn(middle=mid)).silent)

    def test_a_tool_run_through_a_package_manager_counts(self):
        for cmd in ["pnpm tsc --noEmit", "pnpm vitest run", "yarn jest", "yarn eslint ."]:
            with self.subTest(cmd=cmd):
                mid = [h.bash_use("b1", cmd), h.tool_result("b1", "ok")]
                self.assertTrue(self.run_hook(self.claim_turn(middle=mid)).silent)

    def test_version_and_listing_runs_do_not_count(self):
        for cmd in ["pytest --version", "pytest --collect-only -q", "npx jest --listTests", "tsc --version",
                    "eslint --help"]:
            with self.subTest(cmd=cmd):
                mid = [h.bash_use("b1", cmd), h.tool_result("b1", "x")]
                self.assertTrue(self.run_hook(self.claim_turn(middle=mid)).blocked)

    def test_read_only_browser_calls_do_not_count(self):
        for name in ("mcp__Claude_Browser__tabs_context", "mcp__Claude_Browser__preview_list",
                     "mcp__playwright__browser_close"):
            with self.subTest(name=name):
                mid = [h.tool_use("m1", name, {}), h.tool_result("m1", "[]")]
                self.assertTrue(self.run_hook(self.claim_turn(middle=mid)).blocked)

    def test_browser_navigate_screenshot_and_page_text_count(self):
        for name in ("mcp__playwright__browser_navigate", "mcp__playwright__browser_take_screenshot",
                     "mcp__Claude_Browser__get_page_text", "mcp__claude-in-chrome__navigate"):
            with self.subTest(name=name):
                mid = [h.tool_use("m1", name, {}), h.tool_result("m1", "Page title: Example")]
                self.assertTrue(self.run_hook(self.claim_turn(middle=mid)).silent)

    def test_browser_tool_with_a_result_counts(self):
        mid = [h.tool_use("m1", "mcp__playwright__browser_navigate", {"url": "https://example.test"}),
               h.tool_result("m1", "Page title: Example")]
        self.assertTrue(self.run_hook(self.claim_turn(middle=mid)).silent)

    def test_browser_tool_with_an_error_does_not_count(self):
        mid = [h.tool_use("m1", "mcp__playwright__browser_navigate", {"url": "https://example.test"}),
               h.tool_result("m1", "net::ERR_CONNECTION_REFUSED", is_error=True)]
        self.assertTrue(self.run_hook(self.claim_turn(middle=mid)).blocked)

    def test_background_check_with_no_completion_is_not_evidence(self):
        mid = [h.bash_use("b1", "npm test", run_in_background=True),
               h.tool_result("b1", "Command running in background with ID: bg1")]
        self.assertTrue(self.run_hook(self.claim_turn(middle=mid)).blocked)

    def test_background_check_with_a_clean_completion_notice_is_evidence(self):
        mid = [h.bash_use("b1", "npm test", run_in_background=True),
               h.tool_result("b1", "Command running in background with ID: bg1"),
               h.task_notification("b1", 0)]
        self.assertTrue(self.run_hook(self.claim_turn(middle=mid)).silent)

    def test_background_check_with_a_failing_completion_notice_is_not_evidence(self):
        mid = [h.bash_use("b1", "npm test", run_in_background=True),
               h.tool_result("b1", "Command running in background with ID: bg1"),
               h.task_notification("b1", 1)]
        self.assertTrue(self.run_hook(self.claim_turn(middle=mid)).blocked)

    def test_background_completion_for_a_command_that_is_not_a_check(self):
        mid = [h.bash_use("b1", "sleep 5", run_in_background=True),
               h.tool_result("b1", "Command running in background with ID: bg1"),
               h.task_notification("b1", 0, description="sleep 5")]
        self.assertTrue(self.run_hook(self.claim_turn(middle=mid)).blocked)

    def test_a_sidechain_check_is_not_evidence_for_the_main_thread(self):
        mid = [h.sidechain(h.bash_use("s1", "pytest -q")), h.sidechain(h.tool_result("s1", "3 passed"))]
        self.assertTrue(self.run_hook(self.claim_turn(middle=mid)).blocked)


class TestClaimText(Base):
    def blocked(self, text, with_check=False):
        mid = h.passing_check("b1") if with_check else None
        return self.run_hook(self.claim_turn(final=text, middle=mid), last_assistant_message=text).blocked

    def test_negations_and_disclosures_are_not_blocked(self):
        for text in [
            "This is not verified.",
            "unverified",
            "I haven't verified this.",
            "I couldn't run the tests.",
            "The tests did not pass.",
            "It is not yet deployed.",
            "The bug isn't fixed.",
            "Nothing is verified yet.",
        ]:
            with self.subTest(text=text):
                self.assertFalse(self.blocked(text))

    def test_mixed_sentences_are_still_blocked(self):
        for text in [
            "Fixed the parser. Removed the unverified_users flag.",
            "Tests pass; I didn't touch the docs.",
            "Fixed and deployed; removed the unverified_users flag",
        ]:
            with self.subTest(text=text):
                self.assertTrue(self.blocked(text))

    def test_incidental_words_do_not_switch_detection_off(self):
        for text in [
            "I didn't run into any issues. Fixed and deployed.",
            "Fixed the bug where unverified users could log in. All tests pass.",
            "Added tests for the untested branch; all tests pass.",
            "No tests were broken by this change. Everything is green.",
        ]:
            with self.subTest(text=text):
                self.assertTrue(self.blocked(text))

    def test_a_disclosure_excuses_its_own_sentence_only(self):
        self.assertFalse(self.blocked("Fixed the parser (unverified: no test suite here)."))
        self.assertFalse(self.blocked("Fixed the parser, but I couldn't run the tests."))
        self.assertFalse(self.blocked("Fixed the typo; not tested."))
        self.assertFalse(self.blocked("Fixed the parser, untested."))
        # a claim in a neighbouring sentence is still a claim
        self.assertTrue(self.blocked("Fixed and deployed. I couldn't verify it in production."))
        self.assertTrue(self.blocked("I couldn't verify it in production. Fixed and deployed."))
        self.assertTrue(self.blocked("Fixed the parser.\nUnverified: the deploy."))
        self.assertTrue(self.blocked("Everything is green.\nRenamed the module.\nI did not run the tests."))

    def test_a_description_of_the_bug_is_not_a_disclosure(self):
        for text in [
            "Root cause: the loader never checked the file size. Fixed it with a guard, and all tests pass.",
            "The bug was that the token wasn't validated.\nFixed in auth.py.",
            "The old script couldn't run on Python 3.9. Fixed.",
            "Fixed the crash. Previously the parser did not check for empty input.",
            "The handler was never tested against empty bodies; now it's fixed.",
            "I fixed the off-by-one. It wasn't verified by the old tests, which is why it slipped.",
            "Fixed. The config loader was unable to run without HOME set.",
            "Fixed the bug where it wasn't tested.",
        ]:
            with self.subTest(text=text):
                self.assertTrue(self.blocked(text))

    def test_a_claim_followed_by_a_question_tag_is_still_a_claim(self):
        for text in [
            "Fixed it and all tests pass, want me to commit?",
            "All tests pass and it's deployed; should I open a PR?",
            "Fixed the parser and the build is green \u2014 shall I push?",
            "Fixed it and all tests pass \u2014 want me to commit?",
            "Fixed it and all tests pass so should I commit?",
            "Done, shall I commit?",
            "Fixed it, right?",
            "It's fixed, isn't it?",
            "Since all tests pass, should I commit?",
            "All tests pass; anything else?",
        ]:
            with self.subTest(text=text):
                self.assertTrue(self.blocked(text))
                self.assertFalse(self.blocked(text, with_check=True))

    def test_a_question_that_asserts_a_claim_after_a_subordinator_is_still_a_claim(self):
        for text in [
            "Want me to commit now that all tests pass?",
            "Should I commit, since all tests pass?",
            "Shall I push it now that it's fixed and verified?",
            "Do you want me to deploy, now that the build is green?",
            "Would you like me to push because the build is green?",
            "Should I merge as the tests are passing?",
            "Can I close this given that all tests pass?",
            "Want me to push, seeing as everything passes?",
        ]:
            with self.subTest(text=text):
                self.assertTrue(self.blocked(text))
                self.assertFalse(self.blocked(text, with_check=True))

    def test_a_hedge_that_starts_with_should_is_not_a_question_opener(self):
        for text in [
            "Should be fixed now and all tests pass, want me to commit?",
            "Should now be fixed and the build is green, want me to push?",
        ]:
            with self.subTest(text=text):
                self.assertTrue(self.blocked(text))
                self.assertFalse(self.blocked(text, with_check=True))

    def test_a_question_with_a_condition_or_a_timing_is_not_a_claim(self):
        for text in [
            "Should I commit as soon as the tests pass?",
            "Want me to wait until all tests pass?",
            "Want me to deploy once the build is green?",
            "Should I commit if all tests pass?",
            "Should I rerun everything as needed?",
        ]:
            with self.subTest(text=text):
                self.assertFalse(self.blocked(text))

    def test_a_pure_question_is_not_a_claim(self):
        for text in [
            "Is it fixed?",
            "Should I deploy it?",
            "Do all tests pass?",
            "Want me to commit?",
            "Okay, is it fixed?",
            "If the tests pass, should I commit?",
            "Is it fixed, or should I keep going?",
            "Does it work now, and are all tests passing?",
            "Want me to confirm that all tests pass?",
            "Which tests pass?",
            "Ready to deploy?",
        ]:
            with self.subTest(text=text):
                self.assertFalse(self.blocked(text))

    def test_a_disclosure_still_excuses_a_claim_that_is_followed_by_a_question(self):
        self.assertFalse(self.blocked("Fixed it (unverified), want me to commit?"))
        self.assertFalse(self.blocked("Fixed it, but I couldn't run the tests \u2014 want me to try?"))

    def test_a_first_person_bug_history_is_not_a_disclosure(self):
        for text in [
            "It failed in CI because we never ran the migration there; fixed and all tests pass.",
            "The bug slipped through because we never tested it on Windows; fixed now.",
            "Previously we never validated it; all tests pass now.",
            "I never ran it on Python 3.9 before; fixed.",
            "Resolved; we didn't test it before but it's fixed now.",
            "We never ran it in CI, which is how it slipped through; fixed now.",
            "Root cause: we never ran the migration; fixed and all tests pass.",
            "Earlier I didn't check it on Windows; fixed and all tests pass.",
            "We never ran it on Python 3.9 until now; fixed.",
            "It broke as we never ran the migration there; fixed.",
            "CI was red since we never ran the migration there; fixed and all tests pass.",
            "The regression happened when we didn't run the migration; fixed and the tests pass.",
            "We never tested it on Windows, hence the crash; fixed now.",
            "Until today we never tested it on Windows; fixed and all tests pass.",
            "In the original PR we never tested it on Windows; it's fixed now.",
            "We didn't run the migration in CI, which broke prod; fixed and all tests pass.",
            "We didn't check the null case, so it crashed; fixed and all tests pass.",
            "The bug was that we never ran it on Windows; fixed.",
            "Turns out we never ran the migration on prod; it's fixed now.",
            "We never ran the suite on Python 3.9, thus the failure; fixed and all tests pass.",
        ]:
            with self.subTest(text=text):
                self.assertTrue(self.blocked(text))

    def test_a_first_person_disclosure_about_this_work_still_excuses(self):
        for text in [
            "I never ran the tests, but it's fixed.",
            "Fixed; I didn't run the tests.",
            "Fixed it; I haven't run the tests yet.",
            "I couldn't run the tests because Docker is down; fixed the parser.",
            "I couldn't run the tests before committing; fixed.",
            "Fixed; I didn't run the tests before committing.",
            "Because Docker is down, I couldn't run the tests; fixed the parser though.",
            "Fixed the null check, but because the fixture DB is gone I couldn't run the tests.",
            "Since Docker is down I couldn't run the tests; fixed the parser.",
            "Since the build takes an hour I didn't run the tests; fixed.",
            "Fixed it, though I didn't test it on Windows.",
            "Fixed it, but I haven't run the tests since the CI is down.",
        ]:
            with self.subTest(text=text):
                self.assertFalse(self.blocked(text))

    def test_the_usual_success_phrasings_are_claims(self):
        for text in ["The test suite passes.", "The full suite passes now.", "All 112 passed.", "112/112 passed.",
                     "The suite is green.", "CI is green.", "All checks pass.", "Everything passes.",
                     "Tests: passing."]:
            with self.subTest(text=text):
                self.assertTrue(self.blocked(text))
                self.assertFalse(self.blocked(text, with_check=True))

    def test_negation_stops_at_a_conjunction(self):
        self.assertTrue(self.blocked("No regressions and all tests pass."))
        self.assertTrue(self.blocked("Marked as fixed."))
        self.assertTrue(self.blocked("Managed to get it fixed."))
        self.assertFalse(self.blocked("No tests pass."))
        self.assertFalse(self.blocked("I need to get the tests passing."))

    def test_an_unclosed_fence_hides_only_its_own_line(self):
        self.assertTrue(self.blocked("Here is the plan:\n```\nstep\nAll tests pass."))
        self.assertFalse(self.blocked("```\nAll tests passed\n```\nI have not looked further."))

    def test_strong_words_used_as_adjectives_are_not_claims(self):
        for text in ["Used a fixed seed so the runs repeat.", "The fixed point of the map is zero.",
                     "Compare it with the deployed copy."]:
            with self.subTest(text=text):
                self.assertFalse(self.blocked(text))

    def test_code_is_stripped_before_matching(self):
        self.assertFalse(self.blocked("The log shows:\n```\nAll tests passed\n```\nI have not looked further."))
        self.assertFalse(self.blocked("The flag `verified` is set in the config."))
        self.assertTrue(self.blocked("Fixed the bug (see the `unverified` flag)."))

    def test_questions_future_and_conditionals_are_not_blocked(self):
        for text in ["Is it fixed?", "Once it's deployed, check the page.", "I'll verify after you confirm.",
                     "If the tests pass, merge it."]:
            with self.subTest(text=text):
                self.assertFalse(self.blocked(text))

    def test_word_boundaries(self):
        for text in ["fixed-width", "well-done", "undone", "workspace", "dist/builds/app", "verify", "deployment"]:
            with self.subTest(text=text):
                self.assertFalse(self.blocked(text))
        for text in ["Fixed.", "all green!", "Tests pass,", "DEPLOYED"]:
            with self.subTest(text=text):
                self.assertTrue(self.blocked(text))

    def test_last_assistant_message_wins_over_the_transcript(self):
        entries = self.claim_turn(final="Fixed and deployed.")
        self.assertFalse(self.run_hook(entries, last_assistant_message="Not verified yet.").blocked)
        entries = self.claim_turn(final="Here is a plain summary.")
        self.assertTrue(self.run_hook(entries, last_assistant_message="Fixed and deployed.").blocked)

    def test_transcript_is_the_fallback_when_the_payload_has_no_message(self):
        self.assertTrue(self.run_hook(self.claim_turn(final="Fixed and deployed.")).blocked)

    def test_empty_final_message_is_not_a_claim(self):
        entries = [h.prompt("go"), h.assistant_text("Fixed."), h.edit_use("e1"), h.tool_result("e1", "ok"),
                   h.assistant_thinking()]
        self.assertTrue(self.run_hook(entries, last_assistant_message="").silent)

    def test_claim_with_a_check_that_ran_is_silent_for_every_word(self):
        for text in ["Tests pass.", "All green.", "Verified.", "Fixed.", "Deployed.", "Build passes.", "It works.",
                     "Done."]:
            with self.subTest(text=text):
                self.assertFalse(self.blocked(text, with_check=True))


class TestSessionScope(Base):
    def test_a_check_in_an_earlier_turn_backs_a_later_claim(self):
        entries = ([h.prompt("first"), h.edit_use("e1"), h.tool_result("e1", "ok")] + h.passing_check("b1")
                   + [h.assistant_text("Done, tests pass."), h.prompt("second"), h.assistant_text("Fixed.")])
        self.assertTrue(self.run_hook(entries).silent)

    def test_an_edit_in_an_earlier_turn_with_no_check_since_is_judged_in_a_later_turn(self):
        entries = [h.prompt("first"), h.edit_use("e1"), h.tool_result("e1", "ok"), h.assistant_text("Edited."),
                   h.prompt("second"), h.assistant_text("Fixed.")]
        self.assertTrue(self.run_hook(entries).blocked)

    def test_a_check_before_the_edit_of_a_later_turn_does_not_carry_over(self):
        entries = ([h.prompt("first")] + h.passing_check("b1") + [h.assistant_text("Fixed."), h.prompt("second"),
                   h.edit_use("e1"), h.tool_result("e1", "ok"), h.assistant_text("Fixed again.")])
        self.assertTrue(self.run_hook(entries).blocked)

    def test_a_claim_in_the_previous_turn_is_not_judged_now(self):
        entries = [h.prompt("first"), h.edit_use("e1"), h.tool_result("e1", "ok"),
                   h.assistant_text("Fixed and deployed."), h.prompt("second"),
                   h.assistant_text("Here is a plain answer.")]
        self.assertTrue(self.run_hook(entries).silent)

    def test_entries_that_are_not_prompts_do_not_end_the_turn(self):
        # The claim sits before the entry. If the entry were taken for a prompt, the claim would belong to the
        # previous turn and nothing would be judged.
        not_prompts = {
            "task notification": h.task_notification("zz", 0, description="other"),
            "peer message": h.meta_user("a peer says hi", origin={"kind": "peer"}),
            "non-human origin, not meta": h.prompt("text injected by something that is not the person",
                                                    origin={"kind": "task-notification"}, isMeta=False),
            "local command stdout": h.legacy_prompt("<local-command-stdout>ok</local-command-stdout>"),
            "skill expansion": h.meta_user("Base directory for this skill: x\n..."),
            "stop hook feedback": h.meta_user("Stop hook feedback:\ndojo-verify: ..."),
            "sidechain prompt": h.sidechain(h.prompt("a subagent was told this")),
            "system reminder meta": h.meta_user("<system-reminder>x</system-reminder>"),
        }
        for label, entry in not_prompts.items():
            with self.subTest(label=label):
                entries = [h.prompt("go"), h.edit_use("e1"), h.tool_result("e1", "ok"), h.assistant_text("Fixed."),
                           entry]
                self.assertTrue(self.run_hook(entries).blocked)

    def test_a_legacy_prompt_with_no_origin_ends_the_turn(self):
        entries = [h.prompt("first"), h.edit_use("e1"), h.tool_result("e1", "ok"), h.assistant_text("Fixed."),
                   h.legacy_prompt("second")]
        self.assertTrue(self.run_hook(entries).silent)

    def test_a_slash_command_entry_ends_the_turn(self):
        entries = [h.prompt("first"), h.edit_use("e1"), h.tool_result("e1", "ok"), h.assistant_text("Fixed."),
                   h.legacy_prompt("<command-message>x</command-message>\n<command-name>/x</command-name>")]
        self.assertTrue(self.run_hook(entries).silent)

    def test_a_compaction_ends_the_view_so_an_earlier_edit_is_not_seen(self):
        summary = h.legacy_prompt("This session is being continued from a previous conversation...")
        summary["isCompactSummary"] = True
        entries = [h.prompt("old"), h.edit_use("e1"), h.tool_result("e1", "ok"), summary,
                   h.assistant_text("Fixed and deployed.")]
        self.assertTrue(self.run_hook(entries).silent)

    def test_a_compact_boundary_system_entry_also_ends_the_view(self):
        marker = {"type": "system", "subtype": "compact_boundary", "uuid": h.uid()}
        entries = [h.prompt("old"), h.edit_use("e1"), h.tool_result("e1", "ok"), marker,
                   h.assistant_text("Fixed and deployed.")]
        self.assertTrue(self.run_hook(entries).silent)

    def test_work_after_a_compaction_is_judged(self):
        summary = h.legacy_prompt("This session is being continued from a previous conversation...")
        summary["isCompactSummary"] = True
        entries = [h.prompt("old")] + h.passing_check("b1") + [summary, h.prompt("fresh"), h.edit_use("e1"),
                                                                 h.tool_result("e1", "ok"),
                                                                 h.assistant_text("Fixed.")]
        self.assertTrue(self.run_hook(entries).blocked)

    def test_no_prompt_in_the_window_still_judges_the_edits_in_it(self):
        entries = h.passing_check("b1") + [h.assistant_text("Fixed.")]
        self.assertTrue(self.run_hook(entries).silent)
        entries = [h.edit_use("e1"), h.tool_result("e1", "ok"), h.assistant_text("Fixed.")]
        self.assertTrue(self.run_hook(entries).blocked)


class TestTailWindow(Base):
    def padding(self, total_bytes):
        blob = "x" * 100000
        return [h.assistant_text(blob) for _ in range(total_bytes // 100000)]

    def test_large_transcript_with_the_edit_and_check_inside_the_tail(self):
        entries = ([h.prompt("go")] + self.padding(3 * 1024 * 1024) + [h.edit_use("e1"), h.tool_result("e1", "ok")]
                   + h.passing_check("b1") + [h.assistant_text("Fixed.")])
        self.sb.write(entries)
        self.assertGreater(os.path.getsize(self.sb.transcript), 2 * 1024 * 1024)
        start = time.time()
        r = self.run_hook()
        elapsed = time.time() - start
        self.assertTrue(r.silent)
        self.assertLess(elapsed, 1.5)

    def test_large_transcript_with_no_check_still_blocks(self):
        entries = ([h.prompt("go")] + self.padding(3 * 1024 * 1024)
                   + [h.edit_use("e1"), h.tool_result("e1", "ok"), h.assistant_text("Fixed.")])
        self.sb.write(entries)
        self.assertTrue(self.run_hook().blocked)

    def test_an_edit_older_than_the_scan_is_not_seen_so_nothing_is_judged(self):
        old_edit = [h.prompt("go"), h.edit_use("e1"), h.tool_result("e1", "ok")]
        self.sb.write(old_edit + self.padding(3 * 1024 * 1024) + [h.assistant_text("Fixed.")])
        self.assertTrue(self.run_hook().silent)
        self.sb.write(old_edit + self.padding(1024 * 1024) + [h.assistant_text("Fixed.")])
        self.assertTrue(self.run_hook().blocked)

    def test_a_single_giant_line_is_skipped(self):
        self.sb.write([h.prompt("go"), h.edit_use("e1"), h.tool_result("e1", "ok"),
                       h.assistant_text("y" * (3 * 1024 * 1024))])
        r = self.run_hook(last_assistant_message="Fixed and deployed.")
        self.assertTrue(r.silent)

    def test_typical_case_is_fast(self):
        self.sb.write(self.claim_turn())
        start = time.time()
        r = self.run_hook()
        self.assertTrue(r.blocked)
        self.assertLess(time.time() - start, 1.0)


class TestShellCompounds(Base):
    """A write inside for/while/if/{ } is a write: the compound's keyword is not the program."""

    def after_a_passing_check(self, command, output="", is_error=None):
        return self.claim_turn(final="All tests pass.", middle=h.passing_check("b1") + [
            h.bash_use("b2", command), h.tool_result("b2", output, is_error=is_error)])

    def test_writes_inside_compound_commands_are_changes(self):
        for command in [
            'for f in src/*.py; do sed -i \'s/old/new/\' "$f"; done',
            "if [ -f a.py ]; then sed -i s/a/b/ a.py; fi",
            "{ sed -i s/a/b/ a.py; }",
            'while read f; do rm "$f"; done < list.txt',
            "if ! grep -q x a.py; then echo y >> a.py; else echo z; fi",
            'for f in src/*.py; do if grep -q old "$f"; then sed -i s/old/new/ "$f"; fi; done',
            "for f in a b\ndo\n  sed -i s/a/b/ $f\ndone",
            "grep -q x a.py || { sed -i s/a/b/ a.py; }",
            "time { rm -rf build; }",
            "time -p { sed -i s/a/b/ a.py; }",
        ]:
            with self.subTest(command=command):
                self.assertTrue(self.run_hook(self.after_a_passing_check(command)).blocked)

    def test_compounds_that_only_read_are_not_changes(self):
        for command in [
            "for f in a b; do echo $f; done",
            "if [ -f a.py ]; then cat a.py; fi",
            "for f in /tmp/a /tmp/b; do rm -rf /tmp/x; done",
            "true || { echo failed; exit 1; }",
            "echo 'do rm -rf x'",
            "time { cat a.py; }",
            "time { rm -rf /tmp/x; }",
        ]:
            with self.subTest(command=command):
                self.assertTrue(self.run_hook(self.after_a_passing_check(command)).silent)

    def test_a_loop_over_test_scripts_is_a_check(self):
        for command, output, backed in [
            ('for t in tests/test_*.py; do python3 "$t"; done', "ok", True),
            ("for t in tests/test_*.py; do python3 ${t}; done", "ok", True),
            ('for t in tests/test_*.py; do python3 "$t"; done', "1 failed", False),
            ('for f in src/*.py; do python3 "$f"; done', "ok", False),
            ("if pytest -q; then echo ok; fi", "3 passed\nok", True),
            ("for d in a b; do (cd $d && pytest -q); done", "3 passed", True),
            ("if [ -d tests ]; then pytest -q; else echo 'no tests dir'; fi", "no tests dir", False),
            ("if [ -d tests ]; then pytest -q; else echo 'no tests dir'; fi", "3 passed", True),
            ("if [ -d tests ]; then echo go; pytest -q; else echo 'no tests dir'; fi", "go\nno tests dir", False),
            ("if [ -d tests ]; then pytest -q; elif [ -d spec ]; then echo none; else echo skipped; fi", "skipped", False),
            ("if [ -d tests ]; then pytest -q; fi", "3 passed", True),
        ]:
            with self.subTest(command=command, output=output):
                turn = self.claim_turn(final="All tests pass.", middle=[
                    h.bash_use("b1", command), h.tool_result("b1", output)])
                self.assertEqual(self.run_hook(turn).blocked, not backed)


class TestNeverStartedIsPerSegment(Base):
    """Only the segment whose program was not found never started; what ran before it did run."""

    def after_a_passing_check(self, command, output, is_error=True):
        return self.claim_turn(final="All tests pass.", middle=h.passing_check("b1") + [
            h.bash_use("b2", command), h.tool_result("b2", output, is_error=is_error)])

    def test_a_later_segment_that_failed_to_start_keeps_the_earlier_writes(self):
        for command, output in [
            ("sed -i s/a/b/ src/x.py && pytest -q", "bash: pytest: command not found"),
            ("rm -rf dist && tsc -p .", "command not found: tsc"),
            ("cp new.py src/x.py; ./run.sh", "./run.sh: Permission denied"),
            ("rm -rf build && cat secret", "cat: secret: Permission denied"),
            ("rm -rf build; ./x", "bash: x: command not found"),
            ("nope && sed -i s/a/b/ f; sed -i s/c/d/ g", "bash: nope: command not found"),
            ("nope || sed -i s/a/b/ f", "bash: nope: command not found"),
            ("foo > out.txt", "bash: foo: command not found"),
            ("sed -i s/a/b/ f.py && pytest", "Exit code 127\nbash: line 1: pytest: command not found"),
            ("sed -i s/a/b/ f.py && pytest", "zsh:1: command not found: pytest"),
            ("rm -rf build && tsc", "(eval):1: command not found: tsc"),
            ("sed -i s/a/b/ f.py && pytest", "sh: 1: pytest: not found"),
            ("sed -i s/a/b/ f.py && npx tsc", "sh: 1: npx: not found"),
        ]:
            with self.subTest(command=command):
                self.assertTrue(self.run_hook(self.after_a_passing_check(command, output)).blocked)

    def test_a_segment_that_never_started_changed_nothing(self):
        for command, output in [
            ("sed -i s/a/b/ f.py", "Exit code 127\nbash: sed: command not found"),
            ("pytest -q && sed -i s/a/b/ f.py", "bash: pytest: command not found"),
            ("nope && sed -i s/a/b/ f", "bash: nope: command not found"),
            ("sed -i s/a/b/ f.py && pytest", "Permission to use Bash with command sed has been denied."),
            ("sed -i s/a/b/ f.py", "PreToolUse:Bash hook blocked this command"),
            ("pytest -q && sed -i s/a/b/ f.py", "zsh:1: command not found: pytest"),
            ("pytest -q && rm -rf build", "(eval):1: command not found: pytest"),
            ("pytest -q && sed -i s/a/b/ f.py", "sh: 1: pytest: not found"),
            ("npx tsc && sed -i s/a/b/ f.py", "sh: 1: npx: not found"),
            ("sed -i s/a/b/ f.py", "zsh:1: command not found: sed"),
        ]:
            with self.subTest(command=command):
                self.assertTrue(self.run_hook(self.after_a_passing_check(command, output)).silent)

    def test_a_missing_program_in_a_long_output_does_not_hide_a_write(self):
        output = "x" * 500 + "\nbash: sed: command not found"
        self.assertTrue(self.run_hook(self.after_a_passing_check("sed -i s/a/b/ f.py", output)).blocked)


class TestSequenceTable(Base):
    """The shared table of whole sessions (tests/cases.json, 'sequences'), run through the hook as transcripts."""

    def build(self, steps, text):
        entries = [h.prompt("please fix the bug")]
        for n, step in enumerate(steps):
            tid = "t%d" % n
            kind = step[0]
            if kind == "edit":
                entries += [h.edit_use(tid), h.tool_result(tid, "ok")]
            elif kind == "run":
                entries += [h.bash_use(tid, step[1]), h.tool_result(tid, step[2])]
            elif kind == "fail":
                entries += [h.bash_use(tid, step[1]), h.tool_result(tid, step[2], is_error=True)]
            elif kind == "scratch":
                entries += [h.tool_use(tid, "Write", {"file_path": "/tmp/notes.md", "content": "x"}), h.tool_result(tid, "ok")]
            elif kind == "read":
                entries += [h.tool_use(tid, "Read", {"file_path": "/tmp/x"}), h.tool_result(tid, "x = 1")]
            elif kind == "agent":
                entries += [h.tool_use(tid, "Agent", {"prompt": "do it"}), h.tool_result(tid, "done")]
            else:
                raise AssertionError(kind)
        return entries + [h.assistant_text(text)]

    def test_every_session_in_the_table(self):
        with open(os.path.join(h.PLUGIN_ROOT, "tests", "cases.json"), "r") as fh:
            table = json.load(fh)["sequences"]
        self.assertGreater(len(table), 15)
        wrong = []
        for row in table:
            self.sb.write(self.build(row["steps"], row["text"]))
            r = h.run_hook(self.sb.payload(session_id="seq-%d" % len(wrong)), self.sb.env(), cwd=self.sb.project)
            if r.blocked is not row["flagged"] or r.err != "":
                wrong.append(row["name"])
        self.assertEqual(wrong, [])


class TestSpeed(Base):
    """No final message can make the hook slow: the text it reads is capped."""

    def test_pathological_messages_stay_fast_in_process(self):
        hook = h.load_hook_module()
        messages = {
            "spaces": "tests" + " " * 100000,
            "repeated words": "all the " + "full " * 20000,
            "short sentences": "a. " * 40000,
            "claim words": "tests " * 20000,
            "dots": "." * 100000,
            "commas": "fixed, " * 20000,
            "numbers": "12 passed " * 10000,
            "one long sentence": "Fixed " + "word " * 30000,
            "disclosures": "I never " * 20000,
        }
        for label, text in messages.items():
            with self.subTest(label=label):
                start = time.time()
                hook.detect_claim(text, True)
                self.assertLess(time.time() - start, 0.2)

    def test_questions_and_histories_stay_fast_in_process(self):
        hook = h.load_hook_module()
        messages = {
            "commas then a question": "fixed, " * 20000 + "?",
            "dashes then a question": "fixed \u2014 " * 20000 + "?",
            "conjunctions then a question": "fixed and " * 20000 + "?",
            "openers": "want " * 20000 + "?",
            "history": "because we never ran it before; " * 5000,
            "never": "I never " * 20000 + "ran it before",
            "subordinators then a question": "should I commit since " * 5000 + "?",
            "as chains": "want me to push as " * 5000 + "?",
            "history causes": "as we never ran it hence " * 5000 + "fixed.",
        }
        for label, text in messages.items():
            with self.subTest(label=label):
                start = time.time()
                hook.detect_claim(text, True)
                self.assertLess(time.time() - start, 0.2)

    def test_a_command_with_thousands_of_branches_stays_fast_in_process(self):
        hook = h.load_hook_module()
        for label, command in {
            "if/else": "if [ -d t ]; then pytest -q; else echo no; fi; " * 3000,
            "nested": "if a; then " * 1000 + "pytest -q; " + "else echo no; fi; " * 1000,
            "never closed": "if a; then pytest -q; else echo no; " * 3000,
        }.items():
            with self.subTest(label=label):
                start = time.time()
                hook.command_events(command)
                self.assertLess(time.time() - start, 1.0)

    def test_a_message_that_fills_the_whole_input_still_finishes(self):
        self.sb.write(self.claim_turn())
        text = "Fixed " + " " * (1024 * 1024 - 20000)
        start = time.time()
        r = self.run_hook(last_assistant_message=text)
        self.assertEqual((r.code, r.err), (0, ""))
        self.assertLess(time.time() - start, 1.5)

    def test_a_claim_at_the_start_or_the_end_of_a_long_message_is_still_seen(self):
        hook = h.load_hook_module()
        filler = "word " * 20000
        self.assertIsNotNone(hook.detect_claim("All tests pass. " + filler, True))
        self.assertIsNotNone(hook.detect_claim(filler + " All tests pass.", True))


class TestMarkerAndState(Base):
    def state_files(self):
        found = []
        for root, _dirs, files in os.walk(self.sb.state):
            for f in files:
                found.append(os.path.join(root, f))
        return found

    def test_the_same_message_in_the_same_turn_is_blocked_once(self):
        self.sb.write(self.claim_turn())
        self.assertTrue(self.run_hook().blocked)
        self.assertTrue(self.run_hook().silent)

    def test_a_new_prompt_blocks_the_same_message_again(self):
        self.assertTrue(self.run_hook(self.claim_turn()).blocked)
        self.assertTrue(self.run_hook(self.claim_turn()).blocked)

    def test_warn_mode_writes_no_marker(self):
        r = self.run_hook(self.claim_turn(), env=self.sb.env(CLAUDE_PLUGIN_OPTION_MODE="warn"))
        self.assertIn("systemMessage", r.json())
        self.assertEqual(self.state_files(), [])

    def test_hostile_session_ids_stay_inside_the_state_dir(self):
        for sid in ["../../evil", "a/b\\c", "x" * 400, "", "‮\u0000"]:
            with self.subTest(sid=sid[:20]):
                r = self.run_hook(self.claim_turn(), session_id=sid)
                self.assertTrue(r.blocked)
        files = self.state_files()
        self.assertTrue(files)
        for f in files:
            self.assertTrue(os.path.abspath(f).startswith(self.sb.state + os.sep))
            self.assertLessEqual(len(os.path.basename(f)), 120)
        self.assertEqual(sorted(os.listdir(self.sb.root)),
                         sorted(["home", "project", "state", "tmp", "transcript.jsonl"]))

    def test_nothing_is_written_into_the_project(self):
        before = self.sb.project_listing()
        self.run_hook(self.claim_turn())
        self.run_hook(self.claim_turn(), env=self.sb.env(CLAUDE_PLUGIN_OPTION_MODE="warn"))
        self.assertEqual(self.sb.project_listing(), before)

    def test_without_plugin_data_the_temp_dir_is_used(self):
        r = self.run_hook(self.claim_turn(), env=self.sb.env(CLAUDE_PLUGIN_DATA=None))
        self.assertTrue(r.blocked)
        self.assertTrue(os.path.isdir(os.path.join(self.sb.tmpdir, "dojo-verify")))
        self.assertEqual(self.sb.project_listing(), [])

    def test_an_unwritable_state_dir_still_blocks(self):
        r = self.run_hook(self.claim_turn(), env=self.sb.env(CLAUDE_PLUGIN_DATA="/nonexistent/dojo/state"))
        self.assertTrue(r.blocked)


class TestPortability(Base):
    def test_block_and_fail_open_under_a_bare_environment(self):
        # The same invocation the engine could use on a machine with nothing but the system tools.
        import subprocess
        self.sb.write(self.claim_turn())
        env_cmd = ["/usr/bin/env", "-i", "PATH=/usr/bin:/bin", "HOME=" + self.sb.home,
                   "TMPDIR=" + self.sb.tmpdir, h.SYSTEM_PYTHON, h.HOOK]
        blocked = subprocess.run(env_cmd, input=json.dumps(self.sb.payload()).encode(), stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, timeout=20, cwd=self.sb.project)
        self.assertEqual(blocked.returncode, 0)
        self.assertEqual(json.loads(blocked.stdout)["decision"], "block")
        self.assertEqual(blocked.stderr, b"")
        open_ = subprocess.run(env_cmd, input=b"not json", stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               timeout=20, cwd=self.sb.project)
        self.assertEqual((open_.returncode, open_.stdout, open_.stderr), (0, b"", b""))

    def test_the_reason_is_ascii_safe_on_stdout(self):
        # ensure_ascii keeps a C-locale stdout from raising on the dash.
        r = self.run_hook(self.claim_turn(), env=self.sb.env(LC_ALL="C", PYTHONIOENCODING="ascii"))
        self.assertTrue(r.blocked)
        r.out.encode("ascii")


if __name__ == "__main__":
    unittest.main()
