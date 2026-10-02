"""Tests for scripts/prereg.py.

Run: cd plugins/dojo-settle && python3 -m unittest discover -s tests -v

Fixtures are hand-typed. The expected digest below is a literal computed once with
`shasum -a 256` on the text above the marker, outside prereg.py, and pasted in. The
script's own canonicalisation is never used to produce an expected value.
"""
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(HERE)
SCRIPT = os.path.join(PLUGIN, "scripts", "prereg.py")
MARKER = "MEASUREMENTS BEGIN BELOW THIS LINE"

# sha256 of build() with default arguments, text above the marker only.
ORACLE_HEX = "3ec4b6c0db626220e5dc065b32c408bf94a624f7529e76705b8d3b729d53a041"

BELOW = "\n## Results\n\nNothing measured yet.\n"


def build(rule="Keep the incumbent unless the candidate wins by at least 3 points on both references.",
          bar="Candidate must beat the incumbent by 3 points or more on reference A and on reference B. Anything less keeps the incumbent.",
          refutation="A loss of 1 point or more on reference B refutes the candidate even if A improves.",
          grid="Window 5s, 10s, 20s crossed with samples one and two. Nine cells, no others.",
          author="A reviewer who did not build the harness",
          baseline="The same nine cells with the change absent, run in the same session.",
          hypothesis="Whether to change the window from 10s to 20s.",
          incumbent="The 10s window, re-measured on both samples.",
          references="Reference A is a hand-made answer key. Reference B is a second, independent key.",
          should_lose="A clip with no speech, where any window should score the same.",
          extra_above="",
          title="Window length"):
    return (
        "# Pre-registration: %s\n"
        "\n"
        "## 1. What is decided\n"
        "\n"
        "%s\n"
        "\n"
        "## 2. Incumbent, measured here\n"
        "\n"
        "%s\n"
        "\n"
        "## 3. References and confound\n"
        "\n"
        "%s\n"
        "\n"
        "## 4. The rule and the bars\n"
        "\n"
        "### Decision rule\n"
        "\n"
        "%s\n"
        "\n"
        "### Numeric bars\n"
        "\n"
        "%s\n"
        "\n"
        "## 5. What would refute the option you want\n"
        "\n"
        "%s\n"
        "\n"
        "## 6. Frozen grid and held-out tasks\n"
        "\n"
        "### Frozen grid\n"
        "\n"
        "%s\n"
        "\n"
        "### Baseline arm (without)\n"
        "\n"
        "%s\n"
        "\n"
        "### Held-out task author\n"
        "\n"
        "%s\n"
        "\n"
        "### Task where the protocol should lose\n"
        "\n"
        "%s\n"
        "%s"
        "\n"
    ) % (title, hypothesis, incumbent, references, rule, bar, refutation, grid, baseline, author,
         should_lose, extra_above)


def full(above=None, below=BELOW, marker=MARKER):
    return (above if above is not None else build()) + marker + "\n" + below


def run(args, cwd=None, extra_env=None, exe=None):
    env = {"PATH": "/usr/bin:/bin", "HOME": os.environ.get("HOME", "/nonexistent")}
    if extra_env:
        env.update(extra_env)
    p = subprocess.run([exe or sys.executable, SCRIPT] + list(args), cwd=cwd, env=env,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return p.returncode, p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="prereg-test-")
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def path(self, name="p.md"):
        return os.path.join(self.tmp, name)

    def write(self, text, name="p.md", mode="w"):
        p = self.path(name)
        if mode == "wb":
            with open(p, "wb") as f:
                f.write(text)
        else:
            with open(p, "w", encoding="utf-8", newline="") as f:
                f.write(text)
        return p

    def read(self, p):
        with open(p, "r", encoding="utf-8", newline="") as f:
            return f.read()

    def freeze(self, text=None, name="p.md"):
        p = self.write(full() if text is None else text, name)
        code, out, err = run(["freeze", p])
        self.assertEqual(code, 0, out + err)
        return p

    def sidecar_digest(self, p):
        for line in self.read(p + ".sha256").splitlines():
            if line.startswith("sha256:"):
                return line.split(":", 1)[1].strip()
        self.fail("no sha256 line in sidecar")


class TestOracle(Base):
    def test_digest_equals_hex_literal(self):
        p = self.freeze()
        self.assertEqual(self.sidecar_digest(p), ORACLE_HEX)

    @unittest.skipUnless(shutil.which("shasum") and shutil.which("sed"), "shasum or sed missing")
    def test_digest_equals_sed_pipeline(self):
        p = self.freeze()
        cmd = "sed '/^%s$/,$d' '%s' | shasum -a 256" % (MARKER, p)
        out = subprocess.run(["sh", "-c", cmd], stdout=subprocess.PIPE).stdout.decode()
        self.assertEqual(out.split()[0], self.sidecar_digest(p))
        self.assertEqual(out.split()[0], ORACLE_HEX)

    def test_sidecar_records_counts(self):
        p = self.freeze()
        text = self.read(p + ".sha256")
        above = build()
        self.assertIn("bytes: %d\n" % len(above.encode("utf-8")), text)
        self.assertIn("lines: %d\n" % above.count("\n"), text)


class TestFreezeThenVerify(Base):
    def test_verify_matches(self):
        p = self.freeze()
        code, out, err = run(["verify", p])
        self.assertEqual(code, 0, out + err)
        self.assertIn("digest matches", out)

    def test_results_below_marker_do_not_change_digest(self):
        p = self.freeze()
        with open(p, "a", encoding="utf-8") as f:
            f.write("\nCell 1: 41.2. Cell 2: 39.9.\n")
        self.assertEqual(run(["verify", p])[0], 0)

    def test_second_marker_below_does_not_change_digest(self):
        p = self.freeze()
        with open(p, "a", encoding="utf-8") as f:
            f.write("\n" + MARKER + "\nmore\n")
        self.assertEqual(run(["verify", p])[0], 0)

    def test_expect_matches_and_ignores_sidecar(self):
        p = self.freeze()
        os.remove(p + ".sha256")
        code, out, err = run(["verify", p, "--expect", ORACLE_HEX])
        self.assertEqual(code, 0, out + err)

    def test_expect_uppercase_hex_accepted(self):
        p = self.freeze()
        self.assertEqual(run(["verify", p, "--expect", ORACLE_HEX.upper()])[0], 0)


class TestTamperAboveMarker(Base):
    def verify_after(self, mutate):
        p = self.freeze()
        text = self.read(p)
        new = mutate(text)
        self.assertNotEqual(new, text, "mutation did not change the file")
        self.write(new)
        return run(["verify", p])

    def test_one_character(self):
        code, out, err = self.verify_after(lambda t: t.replace("Keep", "Kepe", 1))
        self.assertEqual(code, 1, out + err)
        self.assertIn("digest differs", out)

    def test_trailing_whitespace(self):
        self.assertEqual(self.verify_after(lambda t: t.replace("\n", " \n", 1))[0], 1)

    def test_blank_line_before_marker(self):
        self.assertEqual(self.verify_after(lambda t: t.replace("\n" + MARKER, "\n\n" + MARKER, 1))[0], 1)

    def test_marker_moved_up_one_line(self):
        def mutate(t):
            lines = t.split("\n")
            i = lines.index(MARKER)
            lines[i - 1], lines[i] = lines[i], lines[i - 1]
            return "\n".join(lines)
        self.assertEqual(self.verify_after(mutate)[0], 1)

    def test_marker_moved_down_one_line(self):
        def mutate(t):
            lines = t.split("\n")
            i = lines.index(MARKER)
            lines[i], lines[i + 1] = lines[i + 1], lines[i]
            return "\n".join(lines)
        self.assertEqual(self.verify_after(mutate)[0], 1)

    def test_new_marker_inserted_above_original(self):
        def mutate(t):
            return t.replace("## 5. What would refute", MARKER + "\n## 5. What would refute", 1)
        self.assertEqual(self.verify_after(mutate)[0], 1)

    def test_bom_added_does_not_change_digest(self):
        p = self.freeze()
        with open(p, "rb") as f:
            raw = f.read()
        self.write(b"\xef\xbb\xbf" + raw, mode="wb")
        self.assertEqual(run(["verify", p])[0], 0)


class TestMarkerLookalikes(Base):
    def digest_after_freeze(self, above):
        p = self.freeze(full(above))
        return self.sidecar_digest(p)

    def test_backticked_marker_is_not_the_marker(self):
        above = build(extra_above="\nNote: the line `%s` ends the registration.\n" % MARKER)
        self.assertEqual(self.digest_after_freeze(above), hashlib.sha256(above.encode()).hexdigest())

    def test_marker_inside_a_sentence_is_not_the_marker(self):
        above = build(extra_above="\nResults go after %s, never before.\n" % MARKER)
        self.assertEqual(self.digest_after_freeze(above), hashlib.sha256(above.encode()).hexdigest())

    def test_indented_marker_is_not_the_marker(self):
        above = build(extra_above="\n  %s\n" % MARKER)
        self.assertEqual(self.digest_after_freeze(above), hashlib.sha256(above.encode()).hexdigest())

    def test_trailing_space_marker_is_not_the_marker(self):
        above = build(extra_above="\n%s \n" % MARKER)
        self.assertEqual(self.digest_after_freeze(above), hashlib.sha256(above.encode()).hexdigest())

    def test_fenced_marker_is_not_the_marker(self):
        above = build(extra_above="\n```\n%s\n```\n" % MARKER)
        self.assertEqual(self.digest_after_freeze(above), hashlib.sha256(above.encode()).hexdigest())

    def test_tilde_fence_and_longer_fence(self):
        above = build(extra_above="\n````\n```\n%s\n```\n````\n~~~\n%s\n~~~\n" % (MARKER, MARKER))
        self.assertEqual(self.digest_after_freeze(above), hashlib.sha256(above.encode()).hexdigest())

    def test_only_lookalikes_means_no_marker_and_freeze_refuses(self):
        for lookalike in ("  %s\n" % MARKER, "`%s`\n" % MARKER, "```\n%s\n```\n" % MARKER, "%s \n" % MARKER):
            p = self.write(build() + lookalike + BELOW)
            code, out, err = run(["freeze", p])
            self.assertEqual(code, 1, lookalike)
            self.assertFalse(os.path.exists(p + ".sha256"))

    def test_unclosed_fence_hides_a_marker_below_it(self):
        p = self.write(build(extra_above="\n```\nopen fence\n") + MARKER + "\n" + BELOW)
        code, out, err = run(["freeze", p])
        self.assertEqual(code, 1)
        self.assertFalse(os.path.exists(p + ".sha256"))

    def test_verify_with_no_marker_exits_one(self):
        p = self.freeze()
        self.write(self.read(p).replace(MARKER, "gone"))
        self.assertEqual(run(["verify", p])[0], 1)


class TestFreezeRefusals(Base):
    def refuse(self, text):
        p = self.write(text)
        code, out, err = run(["freeze", p])
        self.assertEqual(code, 1, out + err)
        self.assertFalse(os.path.exists(p + ".sha256"), "sidecar was written")
        return out + err

    def test_missing_marker(self):
        self.refuse(build() + BELOW)

    def test_unfilled_placeholder(self):
        self.refuse(full(build(grid="{{grid}}")))

    def test_placeholder_anywhere(self):
        self.refuse(full(build(extra_above="\nSee {{later}}.\n")))

    def test_empty_values_in_each_required_section(self):
        empties = ["", "   ", "\t", "none", "None", "n/a", "N/A", "TBD", "TODO", "-", "- none", "* TBD",
                   "- [ ] TBD", "- [x] none", "[ ] n/a", "<!-- write it here -->",
                   "1. TBD", "1) TBD", "(TBD)", "[TBD]", "<TBD>", '"TBD"', "'TBD'", "2. none", "- 1. N/A",
                   "1. (n/a)", "TBA", "to be determined", "<!-- note -->\n1. TBD"]
        fields = ["rule", "bar", "refutation", "grid", "author", "baseline", "hypothesis", "incumbent",
                  "references", "should_lose"]
        for field in fields:
            for e in empties:
                with self.subTest(field=field, value=e):
                    self.refuse(full(build(**{field: e})))

    def test_placeholder_only_bodies_are_refused_as_a_class(self):
        variants = [
            "TBD?", "TBD!", "TBD,", "TBD...", "TBD TBD", "~~TBD~~", "**1.** TBD", "**TBD**", "_TBD_",
            "N.A.", "N/A.", "n / a", "\u2014", "\u2013", "\u2026", "...", "..", "??", "?", "???", "!!",
            "| TBD | TBD |", "|---|---|\n| TBD | n/a |", "<b>TBD</b>", "<i>none</i>", "&nbsp;", "&#8203;",
            "a) TBD", "i. TBD", "iv) TBD", "(2) TBD", "1.TBD", "1)TBD", "TBD (fill in later)", "fill in later",
            "to be decided", "To Be Determined.", "pending", "undecided", "placeholder", "TK", "TKK", "XXX",
            "xxxx", "XXX XXX", "TBD\u200b", "T\u200bB\u200bD", "\uff34\uff22\uff24", "TBD\n\nTODO",
            "- TBD\n- TODO\n- ?", "1. TBD\n2. TBD?\n3. ...", "> TBD", "`TBD`", "TBD / TODO", "TBD; TBD",
            "none, n/a", "nil", "null", "nothing", "unknown", "WIP", "TBD\n<!-- real text -->",
            "<!-- real text -->\n??", "[TBD](#)",
            "T.B.D.", "T.B.D", "t.b.d.", "T. B. D.", "T.B.A.", "T.B.C.", "W.I.P.", "N.A.", "TBD 2", "1 TBD",
            "TBD-1", "to be announced", "to be confirmed", "FIXME", "Not applicable", "n/a 3",
        ]
        for field in ("rule", "bar", "refutation", "grid", "author", "baseline", "hypothesis",
                      "incumbent", "references", "should_lose"):
            for v in variants:
                with self.subTest(field=field, value=v):
                    self.refuse(full(build(**{field: v})))

    def test_placeholder_variants_through_the_cli_message(self):
        out = self.refuse(full(build(rule="TBD?")))
        self.assertIn("decision rule", out)
        self.assertIn("placeholders", out)

    def test_short_real_content_is_not_mistaken_for_a_placeholder(self):
        for v in ("p < 0.05", "0.05", "N = 20", "x < 5 and y > 3", "3 points", "5", "A beats B", "B",
                  "TBD is not allowed; the rule is: keep the incumbent.", "1. 3 points on both",
                  "Window 10s", "kept", "see section 2", "a < b", "A. N. Other", "Xi Chen", "A.", "B.", "C.",
                  "\u2265 3.", "X", "x", "n", "a", "Na Li", "1.5", "3 TBD is open"):
            with self.subTest(value=v):
                self.freeze(full(build(bar=v)), name="ok.md")
                os.remove(self.path("ok.md.sha256"))

    def test_unclosed_comment_hiding_a_section_is_refused(self):
        text = full()
        i = text.index("### Decision rule")
        hidden = text[:i] + "<!-- guidance that never ends\n\n" + text[i:]
        out = self.refuse(hidden)
        self.assertIn("never closed", out)

    def test_unclosed_comment_at_the_end_of_the_region_is_refused(self):
        out = self.refuse(full(build(extra_above="\n<!-- left open\n")))
        self.assertIn("never closed", out)

    def test_unclosed_comment_on_a_heading_line_is_refused(self):
        text = full().replace("### Numeric bars", "### Numeric bars <!-- oops")
        self.refuse(text)

    def test_comment_markers_in_code_do_not_hide_sections_or_count_as_unclosed(self):
        quoted = ("\nNotes use `<!--` markers and a later `-->` ends one.\n"
                  "\n```html\n<!-- start of a quoted comment\n```\n"
                  "\n```html\nthe end -->\n```\n"
                  "\nA lone `<!--` in code never opens a comment.\n")
        self.freeze(full(build(extra_above=quoted)))

    def test_closed_comment_in_prose_is_still_removed_and_text_after_it_survives(self):
        text = full(build(rule="<!-- note -->Keep the incumbent unless the candidate wins by 3 points."))
        self.freeze(text)

    def test_multiline_closed_comment_followed_by_real_text_is_accepted(self):
        self.freeze(full(build(bar="<!-- first\nsecond -->\nBeat the incumbent by 3 points.")))

    def test_real_content_that_starts_like_a_list_is_accepted(self):
        self.freeze(full(build(rule="1. Keep the incumbent unless the candidate wins by 3 points.\n2. Otherwise keep it.")))

    def test_required_heading_only_inside_an_html_comment_is_refused(self):
        text = full()
        head = "### Decision rule"
        i = text.index(head)
        j = text.index("### Numeric bars")
        commented = text[:i] + "<!--\n" + text[i:j] + "-->\n\n" + text[j:]
        self.assertNotEqual(commented, text)
        self.refuse(commented)

    def test_whole_section_inside_a_multiline_comment_is_refused(self):
        text = full()
        i = text.index("## 5. What would refute")
        j = text.index("## 6. Frozen grid")
        self.refuse(text[:i] + "<!--\n" + text[i:j] + "-->\n" + text[j:])

    def test_missing_heading(self):
        text = full().replace("### Held-out task author", "### Someone else")
        self.refuse(text)

    def test_each_required_section_deleted_is_refused(self):
        for heading in ("## 1. What is decided", "## 2. Incumbent, measured here",
                        "## 3. References and confound", "### Decision rule", "### Numeric bars",
                        "## 5. What would refute the option you want", "### Frozen grid",
                        "### Baseline arm (without)", "### Held-out task author",
                        "### Task where the protocol should lose"):
            with self.subTest(heading=heading):
                text = full()
                self.assertIn(heading, text)
                self.refuse(text.replace(heading, "### Renamed"))

    def test_placeholder_quoted_in_a_fence_or_comment_is_allowed(self):
        quoted = "\n```\nfinite_time = {{ name }}\n```\n\n<!-- fill {{later}} -->\n"
        self.freeze(full(build(extra_above=quoted)))

    def test_placeholder_in_prose_next_to_a_fence_is_still_refused(self):
        self.refuse(full(build(extra_above="\n```\nquoted {{ok}}\n```\n\nbut {{this}} is prose\n")))

    def test_inline_backticks_do_not_open_a_fence(self):
        text = full(build(extra_above="\n```inline``` text on its own line\n"))
        p = self.freeze(text)
        self.assertEqual(run(["verify", p])[0], 0)

    def test_existing_sidecar_is_not_overwritten(self):
        p = self.freeze()
        before = self.read(p + ".sha256")
        code, out, err = run(["freeze", p])
        self.assertEqual(code, 1)
        self.assertEqual(self.read(p + ".sha256"), before)

    def test_freeze_missing_file_cannot_run(self):
        self.assertEqual(run(["freeze", self.path("nope.md")])[0], 2)

    def test_known_bad_control_unfilled_create_is_refused(self):
        p = self.path("fresh.md")
        self.assertEqual(run(["create", p, "--title", "Fresh"])[0], 0)
        code, out, err = run(["freeze", p])
        self.assertEqual(code, 1, "a template with nothing filled in must not freeze")
        self.assertFalse(os.path.exists(p + ".sha256"))


class TestCreate(Base):
    FLAGS = ["--hypothesis", "Switch from A to B?", "--incumbent", "A, re-measured here",
             "--references", "Key one and key two", "--rule", "Switch only if B wins by 3 on both.",
             "--bar", "3 points on both keys; otherwise keep A.", "--refutation", "B loses 1 point on key two.",
             "--grid", "Cells 1 to 6.", "--baseline", "The same cells with the change absent.",
             "--held-out-author", "A reviewer who did not build it",
             "--should-lose", "A trivial input where B has nothing to add."]

    def test_filled_create_then_freeze_and_verify(self):
        p = self.path("c.md")
        code, out, err = run(["create", p, "--title", "A or B"] + self.FLAGS)
        self.assertEqual(code, 0, out + err)
        self.assertEqual(run(["freeze", p])[0], 0)
        self.assertEqual(run(["verify", p])[0], 0)

    def test_create_writes_no_hash(self):
        p = self.path("c.md")
        run(["create", p, "--title", "T"] + self.FLAGS)
        self.assertFalse(os.path.exists(p + ".sha256"))
        self.assertNotRegex(self.read(p), r"[0-9a-f]{64}")

    def test_create_refuses_to_overwrite(self):
        p = self.write("keep me")
        code, out, err = run(["create", p, "--title", "T"])
        self.assertEqual(code, 1)
        self.assertEqual(self.read(p), "keep me")

    def test_create_missing_parent_exits_two(self):
        code, out, err = run(["create", os.path.join(self.tmp, "no", "such", "p.md"), "--title", "T"])
        self.assertEqual(code, 2)

    def test_create_requires_title(self):
        self.assertEqual(run(["create", self.path("t.md")])[0], 2)
        self.assertEqual(run(["create", self.path("t.md"), "--title", "  "])[0], 1)

    def test_create_refuses_marker_in_a_value(self):
        p = self.path("m.md")
        code, out, err = run(["create", p, "--title", "T", "--rule", "a\n" + MARKER + "\nb"])
        self.assertEqual(code, 1)
        self.assertFalse(os.path.exists(p))

    def test_template_substitution_is_single_pass(self):
        p = self.path("s.md")
        run(["create", p, "--title", "T", "--rule", "see {{bar}}", "--bar", "X"])
        self.assertIn("see {{bar}}", self.read(p))

    def test_created_file_has_the_marker_once_as_a_whole_line(self):
        p = self.path("o.md")
        run(["create", p, "--title", "T"])
        self.assertEqual(self.read(p).split("\n").count(MARKER), 1)


class TestVerifyCannotRun(Base):
    def test_missing_file(self):
        self.assertEqual(run(["verify", self.path("nope.md"), "--expect", ORACLE_HEX])[0], 2)

    def test_missing_sidecar_and_no_expect(self):
        p = self.write(full())
        self.assertEqual(run(["verify", p])[0], 2)

    def test_empty_sidecar(self):
        p = self.write(full())
        self.write("", name="p.md.sha256")
        self.assertEqual(run(["verify", p])[0], 2)

    def test_non_hex_sidecar(self):
        p = self.write(full())
        self.write("sha256: " + "z" * 64 + "\n", name="p.md.sha256")
        self.assertEqual(run(["verify", p])[0], 2)

    def test_wrong_length_sidecar(self):
        p = self.write(full())
        for bad in (ORACLE_HEX[:63], ORACLE_HEX + "0"):
            self.write("sha256: %s\n" % bad, name="p.md.sha256")
            self.assertEqual(run(["verify", p])[0], 2, bad)

    def test_two_digest_lines_in_sidecar(self):
        p = self.write(full())
        self.write("sha256: %s\nsha256: %s\n" % (ORACLE_HEX, ORACLE_HEX), name="p.md.sha256")
        self.assertEqual(run(["verify", p])[0], 2)

    def test_binary_sidecar(self):
        p = self.write(full())
        self.write(b"\xff\xfe\x00\x01", name="p.md.sha256", mode="wb")
        self.assertEqual(run(["verify", p])[0], 2)

    def test_directory_path(self):
        self.assertEqual(run(["verify", self.tmp, "--expect", ORACLE_HEX])[0], 2)
        self.assertEqual(run(["freeze", self.tmp])[0], 2)

    def test_bad_expect(self):
        p = self.freeze()
        self.assertEqual(run(["verify", p, "--expect", "abc"])[0], 2)

    def test_no_arguments(self):
        self.assertEqual(run([])[0], 2)

    def test_unknown_subcommand(self):
        self.assertEqual(run(["seal", self.path()])[0], 2)

    def test_never_exits_zero_when_it_cannot_run(self):
        p = self.write(full())
        for args in (["verify", p], ["verify", self.path("x")], ["verify"], ["freeze"]):
            self.assertNotEqual(run(args)[0], 0, args)


class TestDocumentedLimit(Base):
    def test_document_and_sidecar_rewritten_together_still_matches_but_expect_catches_it(self):
        p = self.freeze()
        # An author quietly edits the rule after seeing results, then re-records the digest.
        edited = full(build(rule="Switch if the candidate wins on either reference."))
        self.write(edited)
        os.remove(p + ".sha256")
        self.assertEqual(run(["freeze", p])[0], 0)
        code, out, err = run(["verify", p])
        self.assertEqual(code, 0, "documented limit: a rewritten sidecar matches its own document")
        self.assertIn("digest matches the recorded digest", out)
        for word in ("verified", "authentic", "genuine", "certified", "trusted", "tamper"):
            self.assertNotIn(word, out.lower())
        code, out, err = run(["verify", p, "--expect", ORACLE_HEX])
        self.assertEqual(code, 1, out + err)


class TestCanonicalisation(Base):
    def test_crlf_copy_gives_same_digest(self):
        p = self.write(full().replace("\n", "\r\n"), mode="w")
        code, out, err = run(["freeze", p])
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.sidecar_digest(p), ORACLE_HEX)
        # and a CRLF checkout of an LF-frozen file still matches
        q = self.freeze(name="lf.md")
        self.write(self.read(q).replace("\n", "\r\n"), name="lf.md")
        self.assertEqual(run(["verify", q])[0], 0)

    def test_bom_is_dropped_before_hashing(self):
        raw = b"\xef\xbb\xbf" + full().encode("utf-8")
        p = self.write(raw, mode="wb")
        code, out, err = run(["freeze", p])
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.sidecar_digest(p), ORACLE_HEX)

    def test_non_utf8_bytes_hash_as_bytes_without_a_traceback(self):
        above = build(extra_above="\nSample bytes: \xff\xfe.\n")
        raw = above.encode("latin-1") + MARKER.encode() + b"\n" + BELOW.encode()
        self.assertIn(b"\xff\xfe", raw)
        p = self.write(raw, mode="wb")
        code, out, err = run(["freeze", p])
        self.assertEqual(code, 0, out + err)
        self.assertNotIn("Traceback", out + err)
        prefix = raw[:raw.index(MARKER.encode())]
        self.assertEqual(self.sidecar_digest(p), hashlib.sha256(prefix).hexdigest())
        self.assertEqual(run(["verify", p])[0], 0)


class TestNoEcho(Base):
    CANARY = "CANARY-7f3a91-not-for-output"

    def test_no_file_text_in_output(self):
        p = self.freeze(full(build(extra_above="\n%s\n" % self.CANARY)))
        outputs = []
        code, out, err = run(["verify", p])
        outputs += [out, err]
        self.write(self.read(p).replace(self.CANARY, "CHANGED-7f3a91"))
        code, out, err = run(["verify", p])
        self.assertEqual(code, 1)
        outputs += [out, err]
        self.write(self.read(p).replace("CHANGED-7f3a91", self.CANARY))
        code, out, err = run(["freeze", p])
        outputs += [out, err]
        for o in outputs:
            self.assertNotIn(self.CANARY, o)
            self.assertNotIn("CHANGED-7f3a91", o)

    def test_no_file_text_when_refused(self):
        p = self.write(full(build(rule="none", extra_above="\n%s\n" % self.CANARY)))
        code, out, err = run(["freeze", p])
        self.assertEqual(code, 1)
        self.assertNotIn(self.CANARY, out + err)


class TestOutputWording(Base):
    BANNED = ("verified", "certified", "tamper-proof", "tamperproof", "trusted", "authentic", "signature", "signed")

    def test_wording_across_commands(self):
        p = self.path("w.md")
        collected = []
        for args in (["create", p, "--title", "T"], ["freeze", p], ["verify", p],
                     ["create", p, "--title", "T"], ["verify", p, "--expect", "nothex"]):
            code, out, err = run(args)
            collected.append(out + err)
        q = self.freeze(name="w2.md")
        collected.append(run(["verify", q])[1])
        self.write(self.read(q).replace("Keep", "Kepe", 1), name="w2.md")
        collected.append(run(["verify", q])[1])
        for text in collected:
            for word in self.BANNED:
                self.assertNotIn(word, text.lower())

    def test_help_exits_zero(self):
        self.assertEqual(run(["-h"])[0], 0)
        self.assertEqual(run(["freeze", "-h"])[0], 0)


class TestEnvironment(Base):
    def test_kill_switch_variables_are_not_read(self):
        p = self.path("k.md")
        env = {"DOJO_OFF": "1", "DOJO_SETTLE_OFF": "1"}
        self.assertEqual(run(["create", p, "--title", "T"], extra_env=env)[0], 0)
        q = self.write(full(), name="k2.md")
        self.assertEqual(run(["freeze", q], extra_env=env)[0], 0)
        self.assertEqual(run(["verify", q], extra_env=env)[0], 0)

    def test_runs_with_a_scrubbed_environment(self):
        # run() already passes only PATH and HOME; also try with no HOME at all
        env = {"PATH": "/usr/bin:/bin"}
        p = self.write(full())
        proc = subprocess.run([sys.executable, SCRIPT, "freeze", p], env=env,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    @unittest.skipUnless(os.path.exists("/usr/bin/python3"), "no system python3")
    def test_system_python_compiles_and_runs_it(self):
        pyc_dir = tempfile.mkdtemp(prefix="prereg-pyc-")
        self.addCleanup(shutil.rmtree, pyc_dir, True)
        proc = subprocess.run(["/usr/bin/python3", "-c",
                               "import py_compile,sys;py_compile.compile(sys.argv[1], cfile=sys.argv[2], doraise=True)",
                               SCRIPT, os.path.join(pyc_dir, "x.pyc")],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        p = self.write(full())
        self.assertEqual(run(["freeze", p], exe="/usr/bin/python3")[0], 0)
        self.assertEqual(self.sidecar_digest(p), ORACLE_HEX)


if __name__ == "__main__":
    unittest.main()
