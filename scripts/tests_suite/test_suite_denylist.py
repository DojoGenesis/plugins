"""Tests for suite_denylist.py. Every term here is synthetic; the real lists are never read.

The helper always sets HOME to an empty temp directory and both DOJO_DENYLIST and
DOJO_INTERNAL_REFS to temp lists. Without HOME, a cleared environment falls back to the
account's home and would quietly load the real lists.
"""
from __future__ import annotations

import contextlib
import io
import os
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

try:
    from . import _helpers as H
except ImportError:
    import _helpers as H

import suite_denylist as SD

A = "zq-synth-alpha"
B = "zq-synth-beta"
W = "zqword"
G = "zq-refs-gamma"
R = r"zq-rx-\d+"
R_HIT = "zq-rx-42"


class Base(unittest.TestCase):
    def setUp(self):
        self.work = tempfile.mkdtemp(prefix="deny-test-")
        self.home = os.path.join(self.work, "home")
        self.tree = os.path.join(self.work, "tree")
        os.makedirs(self.home)
        os.makedirs(self.tree)
        self.listfile = os.path.join(self.work, "list.txt")
        self.refsfile = os.path.join(self.work, "refs.txt")
        self.addCleanup(shutil.rmtree, self.work, True)
        self.set_refs(["i:" + G])

    def set_list(self, lines, raw=None):
        with open(self.listfile, "wb") as fh:
            fh.write(raw if raw is not None else ("\n".join(lines) + "\n").encode("utf-8"))

    def set_refs(self, lines, raw=None):
        with open(self.refsfile, "wb") as fh:
            fh.write(raw if raw is not None else ("\n".join(lines) + "\n").encode("utf-8"))

    def put(self, rel, content):
        H.write(os.path.join(self.tree, rel), content)
        return os.path.join(self.tree, rel)

    def env(self, **extra):
        e = {"PATH": "/usr/bin:/bin", "HOME": self.home, "DOJO_DENYLIST": self.listfile, "DOJO_INTERNAL_REFS": self.refsfile}
        for k, v in extra.items():
            if v is None:
                e.pop(k, None)
            else:
                e[k] = v
        return e

    def run_deny(self, *args, **extra):
        r = subprocess.run([H.PY39, H.DENY] + list(args), stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=self.env(**extra))
        return r.returncode, r.stdout.decode("utf-8", "replace"), r.stderr.decode("utf-8", "replace")

    def scan(self, *rel, **extra):
        paths = [os.path.join(self.tree, r) for r in rel] or [self.tree]
        return self.run_deny(*paths, **extra)

    def inproc(self, argv, env=None):
        buf = io.StringIO()
        with mock.patch.dict(os.environ, env or {"DOJO_DENYLIST": self.listfile, "DOJO_INTERNAL_REFS": self.refsfile, "HOME": self.home}):
            with contextlib.redirect_stdout(buf):
                rc = SD.main(argv)
        return rc, buf.getvalue()


class TestMatching(Base):
    def test_i_term_matches_in_any_case_and_inside_words(self):
        self.set_list(["i:" + A])
        for text in (A, A.upper(), "xx" + A.title() + "yy", "pre-" + A + "-post"):
            with self.subTest(text=text):
                self.put("f.txt", "line one\n" + text + "\n")
                rc, out, err = self.scan()
                self.assertEqual(rc, 1, out)
                self.assertIn("f.txt:2: <REDACTED term #1>", out)
                self.assertIn("1 hit(s); control ok (2 lists)", out)

    def test_w_term_is_a_case_sensitive_whole_word(self):
        self.set_list(["i:" + A, "w:" + W])
        hits = ["a %s b" % W, "%s." % W, "(%s)" % W, W, "x %s" % W]
        misses = ["x%s" % W, "%sx" % W, "%s-more" % W, "pre-%s" % W, "%s_x" % W, W.upper(), W.title()]
        for text in hits:
            with self.subTest(hit=text):
                self.put("f.txt", text + "\n")
                rc, out, _ = self.scan()
                self.assertEqual(rc, 1, text)
                self.assertIn("term #2", out)
        for text in misses:
            with self.subTest(miss=text):
                self.put("f.txt", text + "\n")
                rc, out, _ = self.scan()
                self.assertEqual(rc, 0, (text, out))

    def test_clean_tree(self):
        self.set_list(["i:" + A])
        self.put("f.txt", "nothing to see\n")
        rc, out, _ = self.scan()
        self.assertEqual(rc, 0)
        self.assertIn("0 hit(s); control ok", out)

    def test_term_numbers_count_parsed_terms_not_file_lines(self):
        self.set_list(["# comment", "", "x:ignored", "i:" + A, "", "# more", "i:" + B])
        self.put("f.txt", B + "\n")
        rc, out, _ = self.scan()
        self.assertEqual(rc, 1)
        self.assertIn("f.txt:1: <REDACTED term #2>", out)

    def test_line_numbers_with_crlf_and_no_trailing_newline(self):
        self.set_list(["i:" + A])
        self.put("crlf.txt", ("a\r\nb\r\n" + A + "\r\nd\r\n").encode("utf-8"))
        self.put("tail.txt", ("a\nb\n" + A).encode("utf-8"))
        rc, out, _ = self.scan()
        self.assertIn("crlf.txt:3:", out)
        self.assertIn("tail.txt:3:", out)

    def test_several_paths_and_a_single_file(self):
        self.set_list(["i:" + A])
        f1 = self.put("one/a.txt", A + "\n")
        self.put("two/b.txt", "clean\n")
        rc, out, _ = self.run_deny(f1, os.path.join(self.tree, "two"))
        self.assertEqual(rc, 1)
        self.assertEqual(out.count("<REDACTED term"), 1)

    def test_utf16_file_with_bom_is_scanned(self):
        self.set_list(["i:" + A])
        self.put("u16.txt", ("hello " + A + "\n").encode("utf-16"))
        rc, out, _ = self.scan()
        self.assertEqual(rc, 1, out)
        self.assertIn("u16.txt:1:", out)


class TestListParsing(Base):
    def test_first_entry_w_or_with_metacharacters_still_passes_the_control(self):
        for lines in (["w:" + W, "i:" + A], ["i:a.b(c", "i:" + A], ["i:[x]*+?", "w:" + W]):
            with self.subTest(lines=lines):
                self.set_list(lines)
                self.put("f.txt", "clean\n")
                rc, out, _ = self.scan()
                self.assertEqual(rc, 0, out)
                self.assertIn("control ok", out)

    def test_metacharacter_term_matches_literally(self):
        self.set_list(["i:a.b(c"])
        self.put("f.txt", "a.b(c\naxb(c\n")
        rc, out, _ = self.scan()
        self.assertEqual(out.count("<REDACTED term"), 1, out)

    def test_empty_and_whitespace_terms_are_skipped_and_never_match_everything(self):
        self.set_list(["i:", "w:", "i: ", "i:\t", "w:  ", "r:", "r: ", "i:" + A])
        self.put("f.txt", "anything at all, with spaces\ttabs\n")
        rc, out, _ = self.scan()
        self.assertEqual(rc, 0, out)
        self.assertIn("ignored 7 malformed list line(s)", out)

    def test_regex_terms_that_cannot_work_are_skipped_and_counted(self):
        self.set_list(["i:" + A, "r:(unclosed", "r:x*", "r:(?:)", "r:a|", "r:" + R])
        self.put("f.txt", "anything at all\n" + R_HIT + "\n")
        rc, out, err = self.scan()
        self.assertEqual(rc, 1, out)
        self.assertIn("ignored 4 malformed list line(s)", out)
        self.assertIn("f.txt:2: <REDACTED term #2>", out)
        self.assertNotIn("unclosed", out + err)

    def test_bom_and_crlf_lists_parse(self):
        self.put("f.txt", A + "\n")
        self.set_list(None, raw=b"\xef\xbb\xbfi:" + A.encode() + b"\r\n")
        rc, out, _ = self.scan()
        self.assertEqual(rc, 1, out)
        self.set_list(None, raw=("# c\r\ni:%s\r\nw:%s\r\n" % (A, W)).encode())
        rc, out, _ = self.scan()
        self.assertEqual(rc, 1, out)

    def test_unknown_prefix_is_counted_not_echoed(self):
        self.set_list(["q:" + B, "i:" + A])
        self.put("f.txt", "clean\n")
        rc, out, err = self.scan()
        self.assertEqual(rc, 0)
        self.assertIn("ignored 1 malformed", out)
        self.assertNotIn(B, out + err)

    def test_default_path_is_under_the_home_config_dir(self):
        cfg = os.path.join(self.home, ".config", "dojo")
        os.makedirs(cfg)
        with open(os.path.join(cfg, "stealth-denylist.txt"), "w") as fh:
            fh.write("i:%s\n" % A)
        self.put("f.txt", A + "\n")
        rc, out, _ = self.run_deny(self.tree, DOJO_DENYLIST=None)
        self.assertEqual(rc, 1, out)

    def test_default_refs_path_is_under_the_home_config_dir(self):
        cfg = os.path.join(self.home, ".config", "dojo")
        os.makedirs(cfg)
        with open(os.path.join(cfg, "internal-refs.txt"), "w") as fh:
            fh.write("i:%s\n" % B)
        self.set_list(["i:" + A])
        self.put("f.txt", B + "\n")
        rc, out, _ = self.run_deny(self.tree, DOJO_INTERNAL_REFS=None)
        self.assertEqual(rc, 1, out)
        self.assertIn("f.txt:1: <REDACTED term #2.1>", out)

    def test_refs_flag_beats_environment(self):
        other = os.path.join(self.work, "other-refs.txt")
        with open(other, "w") as fh:
            fh.write("i:%s\n" % B)
        self.set_list(["i:" + A])
        self.put("f.txt", B + "\n")
        rc, out, _ = self.run_deny("--internal-refs", other, self.tree)
        self.assertEqual(rc, 1, out)
        rc, out, _ = self.run_deny("--internal-refs=" + other, self.tree)
        self.assertEqual(rc, 1, out)

    def test_flag_beats_environment(self):
        other = os.path.join(self.work, "other.txt")
        with open(other, "w") as fh:
            fh.write("i:%s\n" % B)
        self.set_list(["i:" + A])
        self.put("f.txt", B + "\n")
        rc, out, _ = self.run_deny("--denylist", other, self.tree)
        self.assertEqual(rc, 1, out)


class TestFailClosed(Base):
    def test_missing_list_exits_two(self):
        rc, out, _ = self.run_deny(self.tree, DOJO_DENYLIST=None)
        self.assertEqual(rc, 2, out)
        self.assertIn("denylist missing; could not run", out)

    def test_missing_second_list_exits_two(self):
        self.set_list(["i:" + A])
        rc, out, _ = self.run_deny(self.tree, DOJO_INTERNAL_REFS=None)
        self.assertEqual(rc, 2, out)
        self.assertIn("internal-refs list missing; could not run", out)
        self.assertNotIn("0 hit(s)", out)

    def test_allow_missing_skips_with_a_visible_message(self):
        rc, out, _ = self.run_deny("--allow-missing", self.tree, DOJO_DENYLIST=None, DOJO_INTERNAL_REFS=None)
        self.assertEqual(rc, 0)
        self.assertIn("SKIPPED (no denylist)", out)

    def test_allow_missing_with_one_list_still_scans_with_the_other(self):
        self.set_list(["i:" + A])
        self.put("f.txt", A + "\n")
        rc, out, _ = self.run_deny("--allow-missing", self.tree, DOJO_INTERNAL_REFS=None)
        self.assertEqual(rc, 1, out)
        self.assertIn("SKIPPED the internal-refs list (missing)", out)
        self.assertIn("control ok (1 list)", out)

    def test_allow_missing_does_not_excuse_an_empty_list(self):
        self.set_list([])
        rc, out, _ = self.run_deny("--allow-missing", self.tree)
        self.assertEqual(rc, 2, out)
        self.set_list(["i:" + A])
        self.set_refs(["# nothing"])
        rc, out, _ = self.run_deny("--allow-missing", self.tree)
        self.assertEqual(rc, 2, out)

    def test_empty_comment_only_and_unusable_lists_exit_two(self):
        for lines in ([], ["# only a comment", ""], ["q:nope"], ["i: "], ["r:(unclosed"], [r"r:(?<=a)b"]):
            for which in ("first", "second"):
                with self.subTest(lines=lines, which=which):
                    self.set_list(["i:" + A])
                    self.set_refs(["i:" + G])
                    (self.set_list if which == "first" else self.set_refs)(lines, raw=b"" if not lines else None)
                    rc, out, _ = self.scan()
                    self.assertEqual(rc, 2, out)
                    self.assertNotIn("0 hit(s)", out)

    def test_w_only_and_r_only_lists_get_a_control_too(self):
        for lines in (["w:" + W], ["r:" + R], [r"r:^zq-anchor-\w{3}$"], [r"r:\bzq-[ab]+-(?:x|y)?z"]):
            with self.subTest(lines=lines):
                self.set_list(lines)
                self.put("f.txt", "clean\n")
                rc, out, _ = self.scan()
                self.assertEqual(rc, 0, out)
                self.assertIn("control ok", out)

    def test_blind_scanner_fails_the_control(self):
        self.set_list(["i:" + A])
        self.put("f.txt", A + "\n")
        with mock.patch.object(SD, "match_line", lambda line, terms: []):
            rc, out = self.inproc([self.tree])
        self.assertEqual(rc, 2)
        self.assertIn("positive control failed for the denylist", out)
        self.assertNotIn("0 hit(s)", out)

    def test_the_second_list_has_its_own_control(self):
        self.set_list(["i:" + A])
        self.set_refs(["i:" + G])
        real = SD.match_line

        def blind_for_list_two(line, terms):
            return [] if terms.list_no == 2 else real(line, terms)

        with mock.patch.object(SD, "match_line", blind_for_list_two):
            rc, out = self.inproc([self.tree])
        self.assertEqual(rc, 2, out)
        self.assertIn("positive control failed for the internal-refs list", out)
        self.assertNotIn("0 hit(s)", out)

    def test_a_canary_from_one_list_cannot_satisfy_the_other(self):
        # the first list can see its own canary; the second list's canary must be found by the second list
        self.set_list(["i:" + A])
        self.set_refs(["i:" + G])
        seen = []
        real = SD.run_control

        def spy(terms):
            seen.append(terms.list_no)
            return real(terms)

        with mock.patch.object(SD, "run_control", spy):
            rc, out = self.inproc([self.tree])
        self.assertEqual(seen, [1, 2])

    def test_name_hit_cannot_stand_in_for_a_content_hit(self):
        self.set_list(["i:canary"])  # matches the control file's own name
        with mock.patch.object(SD, "match_line", lambda line, terms: []):
            rc, out = self.inproc([self.tree])
        self.assertEqual(rc, 2, out)

    def test_control_dir_is_removed_normally_and_after_an_exception(self):
        self.set_list(["i:" + A])
        made = []
        real = SD.tempfile.mkdtemp

        def spy(*a, **k):
            d = real(*a, **k)
            made.append(d)
            return d

        with mock.patch.object(SD.tempfile, "mkdtemp", spy):
            self.inproc([self.tree])
            self.assertEqual(len(made), 2)  # one control per list
            for d in made:
                self.assertFalse(os.path.exists(d))

            def boom(*a, **k):
                raise RuntimeError(A)
            with mock.patch.object(SD, "scan_tree", boom):
                rc, out = self.inproc([self.tree])
            self.assertEqual(rc, 2)
            self.assertEqual(len(made), 3)
            self.assertFalse(os.path.exists(made[2]))
            self.assertIn("RuntimeError", out)
            self.assertNotIn(A, out)

    def test_missing_path_argument_exits_two(self):
        self.set_list(["i:" + A])
        rc, out, _ = self.run_deny(os.path.join(self.tree, "no-such"))
        self.assertEqual(rc, 2, out)

    def test_unknown_option_exits_two(self):
        self.set_list(["i:" + A])
        rc, out, _ = self.run_deny("--nope", self.tree)
        self.assertEqual(rc, 2, out)

    def test_help_exits_zero(self):
        rc, out, _ = self.run_deny("--help")
        self.assertEqual(rc, 0)
        self.assertIn("Exit codes", out)


class TestRedaction(Base):
    def check_hidden(self, *chunks):
        blob = "\n".join(chunks).lower()
        for term in (A, B, W, G, R_HIT):
            self.assertNotIn(term.lower(), blob)

    def test_term_never_appears_in_any_scenario(self):
        self.set_list(["i:" + A, "w:" + W, "q:" + B, "i:" + B])
        outputs = []
        # content hit
        self.put("content.txt", "x %s y\nx %s y\n" % (A.upper(), W))
        # filename hit and directory-name hit
        self.put("name-%s.txt" % A, "clean\n")
        self.put("dir-%s/inside.txt" % B, "clean\n")
        rc, out, err = self.scan()
        self.assertEqual(rc, 1)
        outputs += [out, err]
        self.assertIn("<REDACTED>", out)
        # a missing path argument that contains the term
        rc, out, err = self.run_deny(os.path.join(self.tree, "missing-" + A))
        self.assertEqual(rc, 2)
        outputs += [out, err]
        # unreadable file
        if os.geteuid() != 0:
            p = self.put("locked-%s.txt" % B, "x\n")
            os.chmod(p, 0)
            self.addCleanup(os.chmod, p, 0o600)
            rc, out, err = self.scan()
            outputs += [out, err]
        # oversize file
        self.put("big-%s.txt" % A, b"a" * 4_000_001)
        rc, out, err = self.scan()
        outputs += [out, err]
        self.assertIn("over 4 MB 1", out)
        # an exception path
        with mock.patch.object(SD, "scan_tree", side_effect=RuntimeError(A)):
            rc, out = self.inproc([self.tree])
        outputs.append(out)
        self.check_hidden(*outputs)

    def test_second_list_terms_and_regex_matches_are_never_printed(self):
        self.set_list(["i:" + A])
        self.set_refs(["i:" + G, "r:" + R])
        self.put("content.txt", "x %s y\nx %s y\n" % (G.upper(), R_HIT))
        self.put("name-%s.txt" % R_HIT, "clean\n")
        self.put("dir-%s/inside.txt" % G, "clean\n")
        rc, out, err = self.scan()
        self.assertEqual(rc, 1)
        self.assertIn("content.txt:1: <REDACTED term #2.1>", out)
        self.assertIn("content.txt:2: <REDACTED term #2.2>", out)
        self.assertIn("name-<REDACTED>.txt: <REDACTED term #2.2> (in the name)", out)
        self.assertIn("dir-<REDACTED>: <REDACTED term #2.1>", out)
        self.check_hidden(out, err)
        rc, out, err = self.run_deny(os.path.join(self.tree, "missing-" + R_HIT))
        self.assertEqual(rc, 2)
        self.check_hidden(out, err)

    def test_filename_hit_is_reported_with_a_redacted_path(self):
        self.set_list(["i:" + A])
        self.put("keep-%s.txt" % A, "clean\n")
        rc, out, _ = self.scan()
        self.assertEqual(rc, 1)
        self.assertIn("keep-<REDACTED>.txt: <REDACTED term #1> (in the name)", out)

    def test_directory_name_hit_is_reported(self):
        self.set_list(["i:" + A])
        self.put("d-%s/ok.txt" % A, "clean\n")
        rc, out, _ = self.scan()
        self.assertEqual(rc, 1)
        self.assertIn("d-<REDACTED>: <REDACTED term #1>", out)


class TestSecondList(Base):
    def test_hits_in_the_second_list_are_numbered_with_the_list_number(self):
        self.set_list(["i:" + A, "i:" + B])
        self.set_refs(["# c", "i:" + G, "w:" + W])
        self.put("f.txt", "%s\n%s\nplain %s here\n" % (B, G, W))
        rc, out, _ = self.scan()
        self.assertEqual(rc, 1)
        self.assertIn("f.txt:1: <REDACTED term #2>", out)
        self.assertIn("f.txt:2: <REDACTED term #2.1>", out)
        self.assertIn("f.txt:3: <REDACTED term #2.2>", out)
        self.assertIn("3 hit(s); control ok (2 lists)", out)

    def test_each_list_alone_is_enough_to_report(self):
        self.set_list(["i:" + A])
        self.set_refs(["i:" + G])
        self.put("f.txt", G + "\n")
        self.assertEqual(self.scan()[0], 1)
        self.put("f.txt", A + "\n")
        self.assertEqual(self.scan()[0], 1)
        self.put("f.txt", "clean\n")
        self.assertEqual(self.scan()[0], 0)


class TestRegexTerms(Base):
    def test_r_terms_search_each_line_case_sensitively(self):
        self.set_list(["i:" + A, "r:" + R])
        hits = ["x %s y" % R_HIT, R_HIT, "pre%spost" % R_HIT]
        misses = ["zq-rx-", "ZQ-RX-42", "zq-rx-x"]
        for text in hits:
            with self.subTest(hit=text):
                self.put("f.txt", text + "\n")
                rc, out, _ = self.scan()
                self.assertEqual(rc, 1, text)
                self.assertIn("term #2", out)
        for text in misses:
            with self.subTest(miss=text):
                self.put("f.txt", text + "\n")
                rc, out, _ = self.scan()
                self.assertEqual(rc, 0, (text, out))

    def test_inline_flags_make_a_regex_case_insensitive(self):
        self.set_list(["i:" + A, r"r:(?i)zq-flag-\d+"])
        self.put("f.txt", "ZQ-FLAG-7\n")
        rc, out, _ = self.scan()
        self.assertEqual(rc, 1, out)

    def test_anchors_apply_per_line(self):
        self.set_list(["i:" + A, r"r:^zq-start\b"])
        self.put("f.txt", "zq-start here\nnot zq-start\n")
        rc, out, _ = self.scan()
        self.assertEqual(out.count("<REDACTED term"), 1, out)
        self.assertIn("f.txt:1:", out)

    def test_regex_matches_in_a_path_are_redacted(self):
        self.set_list(["i:" + A, "r:" + R])
        self.put("keep-%s.txt" % R_HIT, "clean\n")
        rc, out, _ = self.scan()
        self.assertIn("keep-<REDACTED>.txt: <REDACTED term #2> (in the name)", out)
        self.assertNotIn(R_HIT, out)


class TestSynth(unittest.TestCase):
    def test_samples_match_their_pattern(self):
        import re
        for pat in (r"zq-rx-\d+", r"^zq-a\w{3}$", r"\bzq-[ab]+-(?:x|y)?z", r"zq(?:one|two)three", r"zq-[^0-9]-end",
                    r"zq.{2}end", r"zq-[0-9a-f]{4,6}-id", r"(?i)zq-case", r"zq\.dot\s+word"):
            with self.subTest(pattern=pat):
                sample = SD.synth_from_regex(pat)
                self.assertIsNotNone(sample, pat)
                self.assertTrue(re.compile(pat).search(sample) or re.compile(pat).search("x " + sample + " y"), (pat, sample))

    def test_patterns_it_cannot_satisfy_return_none(self):
        for pat in (r"(?<=a)b", r"a(?!b)b", "("):
            with self.subTest(pattern=pat):
                self.assertIsNone(SD.synth_from_regex(pat))

    def test_canary_prefers_i_then_w_then_r(self):
        t = SD.parse_terms(("r:%s\nw:%s\ni:%s\n" % (R, W, A)).encode())
        self.assertEqual(SD.canary_for(t), A)
        t = SD.parse_terms(("r:%s\nw:%s\n" % (R, W)).encode())
        self.assertEqual(SD.canary_for(t), W)
        t = SD.parse_terms(("r:%s\n" % R).encode())
        self.assertRegex(SD.canary_for(t), R)
        self.assertIsNone(SD.canary_for(SD.parse_terms(b"# nothing\n")))


class TestWalker(Base):
    def test_skips_git_node_modules_and_pycache(self):
        self.set_list(["i:" + A])
        for d in (".git", "node_modules", "__pycache__", "src/node_modules"):
            self.put(d + "/f.txt", A + "\n")
        rc, out, _ = self.scan()
        self.assertEqual(rc, 0, out)

    def test_binary_files_are_skipped_and_counted(self):
        self.set_list(["i:" + A])
        self.put("bin.dat", b"\x00\x01" + A.encode() + b"\n")
        rc, out, _ = self.scan()
        self.assertEqual(rc, 0)
        self.assertIn("skipped 1 file(s) (binary 1", out)

    def test_symlinks_are_not_followed(self):
        self.set_list(["i:" + A])
        outside = os.path.join(self.work, "outside")
        os.makedirs(outside)
        H.write(os.path.join(outside, "x.txt"), A + "\n")
        os.symlink(outside, os.path.join(self.tree, "link"))
        os.symlink(self.tree, os.path.join(self.tree, "loop"))
        os.symlink(os.path.join(outside, "x.txt"), os.path.join(self.tree, "filelink.txt"))
        self.put("ok.txt", "clean\n")
        rc, out, _ = self.scan()
        self.assertEqual(rc, 0, out)
        self.assertIn("checked 3 symlink(s) by name and target string", out)
        self.assertNotIn("skipped", out)

    def test_symlink_name_is_matched_for_files_and_directories(self):
        self.set_list(["i:" + A])
        os.symlink("elsewhere", os.path.join(self.tree, A + "-file"))
        os.symlink("elsewhere", os.path.join(self.tree, "sub-" + A))
        rc, out, _ = self.scan()
        self.assertEqual(rc, 1, out)
        self.assertEqual(out.count("(in the name)"), 2, out)
        self.assertNotIn(A, out)
        self.assertIn("2 hit(s)", out)

    def test_symlink_target_string_is_matched_and_never_printed(self):
        self.set_list(["i:" + A])
        self.put("real.txt", "clean\n")
        os.makedirs(os.path.join(self.tree, "realdir"))
        os.symlink("../docs/" + A + "/x", os.path.join(self.tree, "dangling"))
        os.symlink("/opt/" + A.upper() + "/real.txt", os.path.join(self.tree, "filelink"))
        os.symlink("realdir/" + A, os.path.join(self.tree, "dirlink"))
        rc, out, _ = self.scan()
        self.assertEqual(rc, 1, out)
        self.assertEqual(out.count("(in the link target)"), 3, out)
        self.assertNotIn(A, out.lower())
        self.assertIn("3 hit(s)", out)

    def test_symlink_target_is_matched_by_the_second_list_and_by_regex_terms(self):
        self.set_list(["i:" + A, "r:" + R])
        self.set_refs(["w:" + W])
        os.symlink("a/" + R_HIT + "/b", os.path.join(self.tree, "one"))
        os.symlink("a/" + W + "/b", os.path.join(self.tree, "two"))
        os.symlink("a/" + W + "x/b", os.path.join(self.tree, "three"))
        rc, out, _ = self.scan()
        self.assertEqual(rc, 1, out)
        self.assertEqual(out.count("(in the link target)"), 2, out)
        self.assertIn("term #2.1", out)

    def test_symlinks_named_like_skipped_directories_are_still_checked(self):
        self.set_list(["i:" + A])
        os.symlink("x/" + A, os.path.join(self.tree, "node_modules"))
        os.symlink("x/" + A, os.path.join(self.tree, ".git"))
        rc, out, _ = self.scan()
        self.assertEqual(rc, 1, out)
        self.assertEqual(out.count("(in the link target)"), 2, out)

    def test_symlink_inside_a_subdirectory_is_found(self):
        self.set_list(["i:" + A])
        os.makedirs(os.path.join(self.tree, "a", "b"))
        os.symlink("t/" + A, os.path.join(self.tree, "a", "b", "l"))
        rc, out, _ = self.scan()
        self.assertEqual(rc, 1, out)
        self.assertIn("(in the link target)", out)

    def test_a_symlink_passed_as_the_scan_root_is_checked(self):
        self.set_list(["i:" + A])
        link = os.path.join(self.work, "rootlink")
        os.symlink("t/" + A, link)
        rc, out, _ = self.run_deny(link)
        self.assertEqual(rc, 1, out)
        self.assertIn("(in the link target)", out)
        clean = os.path.join(self.work, "cleanlink")
        os.symlink("t/ok", clean)
        rc, out, _ = self.run_deny(clean)
        self.assertEqual(rc, 0, out)

    def test_clean_symlinks_do_not_hit(self):
        self.set_list(["i:" + A])
        self.put("real.txt", "clean\n")
        os.symlink("real.txt", os.path.join(self.tree, "ok-link"))
        rc, out, _ = self.scan()
        self.assertEqual(rc, 0, out)
        self.assertIn("checked 1 symlink(s)", out)

    def test_file_that_vanishes_mid_walk_does_not_crash(self):
        self.set_list(["i:" + A])
        real = os.walk

        def fake_walk(root, **kw):
            if "deny-test-" in root and "suite-denylist-control" not in root:
                return iter([(root, [], ["ghost.txt"])])
            return real(root, **kw)

        with mock.patch.object(SD.os, "walk", fake_walk):
            rc, out = self.inproc([self.tree])
        self.assertEqual(rc, 0, out)
        self.assertIn("unreadable 1", out)

    @unittest.skipIf(os.geteuid() == 0, "root can read anything")
    def test_unreadable_file_is_counted(self):
        self.set_list(["i:" + A])
        p = self.put("locked.txt", A + "\n")
        os.chmod(p, 0)
        self.addCleanup(os.chmod, p, 0o600)
        rc, out, _ = self.scan()
        self.assertEqual(rc, 0)
        self.assertIn("unreadable 1", out)

    def test_nothing_is_written_into_the_scanned_tree(self):
        self.set_list(["i:" + A])
        self.put("f.txt", "clean\n")
        before = sorted(os.listdir(self.tree))
        self.scan()
        self.assertEqual(sorted(os.listdir(self.tree)), before)


class TestParityWithTheFirstScanner(Base):
    """The hardened scanner should find what tools/denyscan.py finds (same term semantics)."""

    def test_same_hit_count_on_a_synthetic_tree(self):
        ref = os.path.join(H.SCRIPTS, "..", "..", "tools", "denyscan.py")
        if not os.path.exists(ref):
            self.skipTest("tools/denyscan.py is not next to this checkout")
        self.set_list(["i:" + A, "w:" + W])
        self.put("a.txt", "%s\n%s here\nx%s\n" % (A, W, W))
        self.put("sub/b.txt", A.upper() + "\n")
        _rc, out, _ = self.scan()
        r = subprocess.run([H.PY39, ref, self.tree], stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=self.env())
        theirs = r.stdout.decode().count("denylisted term")
        self.assertEqual(out.count("<REDACTED term"), theirs)
        self.assertEqual(theirs, 3)


if __name__ == "__main__":
    unittest.main()
