import functools
import io
import itertools
import unittest

from pkgcheck import cli, constraints, semver

SEMVER_ORG_CHAIN = [
    "1.0.0-alpha",
    "1.0.0-alpha.1",
    "1.0.0-alpha.beta",
    "1.0.0-beta",
    "1.0.0-beta.2",
    "1.0.0-beta.11",
    "1.0.0-rc.1",
    "1.0.0",
]


class CompareOrdering(unittest.TestCase):
    def test_the_published_example_chain(self):
        for i, j in itertools.combinations(range(len(SEMVER_ORG_CHAIN)), 2):
            low, high = SEMVER_ORG_CHAIN[i], SEMVER_ORG_CHAIN[j]
            self.assertEqual(semver.compare(low, high), -1, (low, high))
            self.assertEqual(semver.compare(high, low), 1, (high, low))

    def test_equal_to_itself(self):
        for version in SEMVER_ORG_CHAIN + ["0.0.0", "10.20.30"]:
            self.assertEqual(semver.compare(version, version), 0, version)

    def test_core_is_numeric(self):
        self.assertEqual(semver.compare("1.10.0", "1.9.0"), 1)
        self.assertEqual(semver.compare("2.0.0", "10.0.0"), -1)
        self.assertEqual(semver.compare("1.0.10", "1.0.9"), 1)
        self.assertEqual(semver.compare("0.0.1", "0.0.0"), 1)

    def test_prerelease_never_beats_a_higher_core(self):
        self.assertEqual(semver.compare("1.0.0-zzz.99", "1.0.1"), -1)
        self.assertEqual(semver.compare("2.0.0-alpha", "1.99.99"), 1)

    def test_numeric_identifiers_compare_as_numbers(self):
        self.assertEqual(semver.compare("1.0.0-2", "1.0.0-10"), -1)
        self.assertEqual(semver.compare("1.0.0-alpha.2", "1.0.0-alpha.11"), -1)
        self.assertEqual(semver.compare("1.0.0-rc.9", "1.0.0-rc.10"), -1)

    def test_numeric_is_lower_than_alphanumeric(self):
        self.assertEqual(semver.compare("1.0.0-1", "1.0.0-a"), -1)
        self.assertEqual(semver.compare("1.0.0-999", "1.0.0-a"), -1)
        self.assertEqual(semver.compare("1.0.0-a.1", "1.0.0-a.b"), -1)
        self.assertEqual(semver.compare("1.0.0-1a", "1.0.0-2"), 1)

    def test_alphanumeric_identifiers_compare_as_text(self):
        self.assertEqual(semver.compare("1.0.0-alpha", "1.0.0-beta"), -1)
        self.assertEqual(semver.compare("1.0.0-Beta", "1.0.0-alpha"), -1)
        self.assertEqual(semver.compare("1.0.0-rc1", "1.0.0-rc10"), -1)
        self.assertEqual(semver.compare("1.0.0-rc2", "1.0.0-rc10"), 1)

    def test_more_identifiers_win_when_the_rest_is_equal(self):
        self.assertEqual(semver.compare("1.0.0-a", "1.0.0-a.0"), -1)
        self.assertEqual(semver.compare("1.0.0-a.1.2", "1.0.0-a.1"), 1)
        self.assertEqual(semver.compare("1.0.0-a.1", "1.0.0-a.1"), 0)

    def test_first_differing_identifier_decides(self):
        self.assertEqual(semver.compare("1.0.0-a.5.z", "1.0.0-a.6.a"), -1)
        self.assertEqual(semver.compare("1.0.0-b.1", "1.0.0-a.99.99"), 1)

    def test_antisymmetric_over_a_mixed_list(self):
        versions = SEMVER_ORG_CHAIN + [
            "1.0.0-1", "1.0.0-1a", "1.0.0-x-y", "0.9.9", "1.0.1", "1.0.0-alpha.0",
        ]
        for a in versions:
            for b in versions:
                self.assertEqual(
                    semver.compare(a, b), -semver.compare(b, a), (a, b)
                )

    def test_transitive_over_a_mixed_list(self):
        versions = SEMVER_ORG_CHAIN + ["1.0.0-1", "1.0.0-1a", "1.0.0-x-y", "0.9.9", "1.0.1"]
        ordered = sorted(versions, key=functools.cmp_to_key(semver.compare))
        for i, j in itertools.combinations(range(len(ordered)), 2):
            self.assertLessEqual(semver.compare(ordered[i], ordered[j]), 0)


class BuildMetadataAndHyphens(unittest.TestCase):
    def test_build_is_ignored(self):
        self.assertEqual(semver.compare("1.0.0+a", "1.0.0+b"), 0)
        self.assertEqual(semver.compare("1.0.0+a", "1.0.0"), 0)
        self.assertEqual(semver.compare("1.0.0-rc.1+x", "1.0.0-rc.1"), 0)
        self.assertEqual(semver.compare("1.0.0-rc.1+zzz", "1.0.0-rc.2+aaa"), -1)
        self.assertEqual(semver.compare("1.0.1+a", "1.0.0+z"), 1)

    def test_empty_build_is_allowed(self):
        self.assertEqual(semver.compare("1.2.3+", "1.2.3"), 0)

    def test_hyphen_in_build_is_not_a_prerelease(self):
        self.assertEqual(semver.compare("1.0.0+build-5", "1.0.0"), 0)
        self.assertEqual(semver.compare("1.0.0+exp-sha-5114f85", "1.0.0-alpha"), 1)

    def test_hyphen_inside_prerelease(self):
        self.assertEqual(semver.compare("1.0.0-x-y", "1.0.0-x-z"), -1)
        self.assertEqual(semver.compare("1.0.0-alpha-1", "1.0.0"), -1)
        self.assertEqual(semver.compare("1.0.0-a-1", "1.0.0-a-1"), 0)
        self.assertEqual(semver.compare("1.0.0-a-1.2", "1.0.0-a-1.10"), -1)

    def test_plus_inside_the_build_part(self):
        self.assertEqual(semver.compare("1.0.0+a+b", "1.0.0"), 0)


class Malformed(unittest.TestCase):
    BAD = [
        "", "1", "1.2", "1.2.3.4", "a.b.c", "1.2.x", "1..3", ".1.2", "1.2.",
        "v1.2.3", "-1.2.3", "1.2.3-", "1.2.3-a..b", "1.2.3-.a", "1.2.3-a.",
        "1.2.-3", "+build", "1.2.3 4",
    ]

    def test_compare_rejects_bad_versions_on_either_side(self):
        for bad in self.BAD:
            with self.assertRaises(ValueError, msg=repr(bad)):
                semver.compare(bad, "1.0.0")
            with self.assertRaises(ValueError, msg=repr(bad)):
                semver.compare("1.0.0", bad)

    def test_parse_core_rejects_the_same(self):
        for bad in self.BAD:
            with self.assertRaises(ValueError, msg=repr(bad)):
                semver.parse_core(bad)


class ParseCore(unittest.TestCase):
    def test_values(self):
        self.assertEqual(semver.parse_core("1.2.3"), (1, 2, 3))
        self.assertEqual(semver.parse_core("0.0.0"), (0, 0, 0))
        self.assertEqual(semver.parse_core("10.20.30"), (10, 20, 30))
        self.assertEqual(semver.parse_core("1.2.3-rc.1+b.5"), (1, 2, 3))
        self.assertEqual(semver.parse_core("4.5.6-x-y"), (4, 5, 6))
        self.assertEqual(semver.parse_core("4.5.6+build-1"), (4, 5, 6))

    def test_results_are_ints(self):
        for part in semver.parse_core("7.8.9"):
            self.assertIsInstance(part, int)


class Operators(unittest.TestCase):
    def test_each_operator(self):
        cases = [
            ("1.2.3", "==1.2.3", True), ("1.2.3", "==1.2.4", False),
            ("1.2.3", "1.2.3", True), ("1.2.3", "1.2.4", False),
            ("1.2.3", "!=1.2.3", False), ("1.2.3", "!=1.2.4", True),
            ("1.2.3", ">=1.2.3", True), ("1.2.2", ">=1.2.3", False),
            ("1.2.3", ">1.2.3", False), ("1.2.4", ">1.2.3", True),
            ("1.2.3", "<=1.2.3", True), ("1.2.4", "<=1.2.3", False),
            ("1.2.3", "<1.2.3", False), ("1.2.2", "<1.2.3", True),
        ]
        for version, spec, expected in cases:
            self.assertIs(constraints.satisfies(version, spec), expected, (version, spec))

    def test_numbers_not_text(self):
        self.assertTrue(constraints.satisfies("1.10.0", ">1.9.0"))
        self.assertTrue(constraints.satisfies("10.0.0", ">=9.0.0"))

    def test_whitespace(self):
        self.assertTrue(constraints.satisfies("1.2.3", ">= 1.2.3"))
        self.assertTrue(constraints.satisfies("1.2.3", "  >=1.0.0 ,  < 2.0.0  "))
        self.assertTrue(constraints.satisfies("1.2.3", " 1.2.3 "))

    def test_prerelease_ordering_is_used(self):
        self.assertTrue(constraints.satisfies("1.0.0-rc.1", ">=1.0.0-beta"))
        self.assertTrue(constraints.satisfies("1.0.0-rc.1", "<1.0.0"))
        self.assertTrue(constraints.satisfies("1.0.0-alpha.2", "<1.0.0-alpha.11"))
        self.assertFalse(constraints.satisfies("1.0.0-beta.11", "<1.0.0-beta.2"))

    def test_build_metadata_is_ignored(self):
        self.assertTrue(constraints.satisfies("1.2.3+abc", "==1.2.3"))
        self.assertTrue(constraints.satisfies("1.2.3", "==1.2.3+zzz"))

    def test_several_clauses_are_anded(self):
        spec = ">=1.0.0, !=1.3.0, <2.0.0"
        self.assertFalse(constraints.satisfies("1.3.0", spec))
        self.assertTrue(constraints.satisfies("1.4.0", spec))
        self.assertTrue(constraints.satisfies("1.0.0", spec))
        self.assertFalse(constraints.satisfies("2.0.0", spec))
        self.assertFalse(constraints.satisfies("0.9.9", spec))


class CaretAndTilde(unittest.TestCase):
    def check(self, spec, inside, outside):
        for version in inside:
            self.assertTrue(constraints.satisfies(version, spec), (spec, version))
        for version in outside:
            self.assertFalse(constraints.satisfies(version, spec), (spec, version))

    def test_caret_major(self):
        self.check("^1.2.3", ["1.2.3", "1.2.4", "1.9.9", "1.10.0"], ["1.2.2", "2.0.0", "0.9.0"])

    def test_caret_zero_minor(self):
        self.check("^0.2.3", ["0.2.3", "0.2.9"], ["0.2.2", "0.3.0", "1.0.0"])

    def test_caret_zero_zero(self):
        self.check("^0.0.3", ["0.0.3"], ["0.0.2", "0.0.4", "0.1.0"])

    def test_caret_all_zero(self):
        self.check("^0.0.0", ["0.0.0"], ["0.0.1", "0.1.0"])

    def test_tilde(self):
        self.check("~1.2.3", ["1.2.3", "1.2.9"], ["1.2.2", "1.3.0", "2.0.0"])
        self.check("~0.2.0", ["0.2.0", "0.2.5"], ["0.3.0", "0.1.9"])
        self.check("~1.0.0", ["1.0.0", "1.0.7"], ["1.1.0"])

    def test_two_digit_parts(self):
        self.check("^1.9.0", ["1.10.0", "1.19.2"], ["2.0.0"])
        self.check("~1.9.0", ["1.9.5"], ["1.10.0"])
        self.check("^0.9.0", ["0.9.7"], ["0.10.0"])

    def test_lower_bound_may_carry_a_prerelease(self):
        self.check(
            "^1.2.3-beta.1",
            ["1.2.3-beta.2", "1.2.3-beta.11", "1.2.3", "1.5.0"],
            ["1.2.3-alpha", "1.2.3-beta", "2.0.0"],
        )
        self.check("~1.2.3-rc.1", ["1.2.3-rc.1", "1.2.3"], ["1.2.3-rc.0", "1.3.0"])

    def test_prerelease_of_the_next_major_is_inside_the_range(self):
        # No special prerelease rule: it is below the upper bound 2.0.0.
        self.assertTrue(constraints.satisfies("2.0.0-rc.1", "^1.2.3"))
        self.assertFalse(constraints.satisfies("2.0.0", "^1.2.3"))

    def test_caret_combined_with_another_clause(self):
        self.assertTrue(constraints.satisfies("1.4.0", "^1.2.3, !=1.3.0"))
        self.assertFalse(constraints.satisfies("1.3.0", "^1.2.3, !=1.3.0"))

    def test_build_metadata_in_the_bound(self):
        self.assertTrue(constraints.satisfies("1.2.4", "^1.2.3+build"))


class SpecErrors(unittest.TestCase):
    def test_bad_specs(self):
        for spec in [
            "", " ", ">=1.0.0,", ",>=1.0.0", ">=1.0.0,,<2.0.0", "=>1.0.0", "=1.0.0",
            "*", "~", "^", ">=", ">=1.0", "1.0", "latest", ">= ", "~1.2", "^x.y.z",
        ]:
            with self.assertRaises(ValueError, msg=repr(spec)):
                constraints.satisfies("1.0.0", spec)

    def test_bad_version(self):
        for version in ["1.2", "", "x", "1.2.3-"]:
            with self.assertRaises(ValueError, msg=repr(version)):
                constraints.satisfies(version, ">=1.0.0")

    def test_every_clause_is_checked_even_after_one_fails(self):
        with self.assertRaises(ValueError):
            constraints.satisfies("1.0.0", "<0.5.0,garbage")
        with self.assertRaises(ValueError):
            constraints.satisfies("1.0.0", "<0.5.0, >=1.x")


class Newest(unittest.TestCase):
    def test_picks_the_highest_match(self):
        versions = ["1.0.0", "1.10.0", "1.9.0", "2.0.0"]
        self.assertEqual(constraints.newest(versions, "^1.0.0"), "1.10.0")
        self.assertEqual(constraints.newest(versions, ">=1.0.0"), "2.0.0")
        self.assertEqual(constraints.newest(versions, "<2.0.0"), "1.10.0")
        self.assertEqual(
            constraints.newest(["1.0.0", "2.0.0-rc.1", "2.0.0"], "<2.0.0"), "2.0.0-rc.1"
        )

    def test_prerelease_ordering(self):
        self.assertEqual(
            constraints.newest(["1.0.0-beta.2", "1.0.0-beta.11"], ">=1.0.0-alpha"),
            "1.0.0-beta.11",
        )
        self.assertEqual(
            constraints.newest(["1.0.0-alpha", "1.0.0-beta", "1.0.0-alpha.1"], ">=1.0.0-alpha"),
            "1.0.0-beta",
        )

    def test_nothing_matches(self):
        self.assertIsNone(constraints.newest(["1.0.0", "2.0.0"], "<1.0.0"))
        self.assertIsNone(constraints.newest([], ">=0.0.0"))

    def test_ties_keep_the_first(self):
        self.assertEqual(constraints.newest(["1.0.0+a", "1.0.0+b"], "==1.0.0"), "1.0.0+a")
        self.assertEqual(constraints.newest(["1.0.0+b", "1.0.0+a"], ">=1.0.0"), "1.0.0+b")

    def test_returns_the_original_string(self):
        self.assertEqual(constraints.newest(["1.2.3+meta"], ">=1.0.0"), "1.2.3+meta")

    def test_accepts_any_iterable(self):
        self.assertEqual(constraints.newest(iter(["1.0.0", "1.1.0"]), "^1.0.0"), "1.1.0")

    def test_malformed_entry_raises(self):
        with self.assertRaises(ValueError):
            constraints.newest(["1.0.0", "oops"], ">=1.0.0")


class CommandLine(unittest.TestCase):
    def run_main(self, argv):
        out, err = io.StringIO(), io.StringIO()
        code = cli.main(argv, out, err)
        return code, out.getvalue(), err.getvalue()

    def test_prints_the_newest_match(self):
        code, out, err = self.run_main(["^1.0.0", "1.0.0", "1.10.0", "1.9.0", "2.0.0"])
        self.assertEqual((code, out, err), (0, "1.10.0\n", ""))

    def test_prerelease_order_in_output(self):
        code, out, _ = self.run_main([">=1.0.0-alpha", "1.0.0-beta.2", "1.0.0-beta.11"])
        self.assertEqual((code, out), (0, "1.0.0-beta.11\n"))

    def test_no_match(self):
        code, out, err = self.run_main(["<1.0.0", "1.0.0", "2.0.0"])
        self.assertEqual((code, out, err), (1, "none\n", ""))

    def test_bad_spec_or_version(self):
        for argv in (["=>1.0.0", "1.0.0"], [">=1.0.0", "1.0"]):
            code, out, err = self.run_main(argv)
            self.assertEqual(code, 2, argv)
            self.assertEqual(out, "", argv)
            self.assertTrue(err.startswith("error: "), argv)
            self.assertTrue(err.endswith("\n"), argv)

    def test_usage(self):
        for argv in ([], [">=1.0.0"]):
            code, out, err = self.run_main(argv)
            self.assertEqual(code, 2, argv)
            self.assertEqual(out, "", argv)
            self.assertTrue(err.startswith("usage:"), argv)


if __name__ == "__main__":
    unittest.main()
