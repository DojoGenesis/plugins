#!/bin/sh
# Writes the project files into the current directory.
set -e

cat > '.gitignore' <<'__SCAFFOLD_FILE_END__'
__pycache__/
*.pyc
__SCAFFOLD_FILE_END__

cat > 'README.md' <<'__SCAFFOLD_FILE_END__'
# pkgcheck

Version precedence and version-range checks for package versions such as
`1.4.2`, `2.0.0-rc.1` or `1.0.0+build.7`.

Layout:

- `pkgcheck/semver.py`       comparing two versions
- `pkgcheck/constraints.py`  `satisfies(version, spec)` and `newest(versions, spec)`
- `pkgcheck/cli.py`          command line front end
- `tests/`                   the checks that must pass
__SCAFFOLD_FILE_END__

mkdir -p 'pkgcheck'
cat > 'pkgcheck/__init__.py' <<'__SCAFFOLD_FILE_END__'
"""pkgcheck: compare versions and check them against ranges."""
__SCAFFOLD_FILE_END__

mkdir -p 'tests'
cat > 'tests/__init__.py' <<'__SCAFFOLD_FILE_END__'
"""Tests for pkgcheck."""
__SCAFFOLD_FILE_END__

mkdir -p 'tests'
cat > 'tests/test_visible.py' <<'__SCAFFOLD_FILE_END__'
import io
import unittest

from pkgcheck import cli, constraints, semver


class Compare(unittest.TestCase):
    def test_plain_ordering(self):
        self.assertEqual(semver.compare("1.2.3", "1.2.4"), -1)
        self.assertEqual(semver.compare("2.0.0", "1.9.9"), 1)
        self.assertEqual(semver.compare("1.2.3", "1.2.3"), 0)

    def test_numbers_are_not_compared_as_text(self):
        self.assertEqual(semver.compare("1.10.0", "1.9.0"), 1)

    def test_prerelease_is_lower_than_release(self):
        self.assertEqual(semver.compare("1.0.0-alpha", "1.0.0"), -1)
        self.assertEqual(semver.compare("1.0.0", "1.0.0-rc.1"), 1)

    def test_core(self):
        self.assertEqual(semver.parse_core("3.4.5"), (3, 4, 5))

    def test_malformed(self):
        with self.assertRaises(ValueError):
            semver.compare("1.2", "1.2.3")


class Satisfies(unittest.TestCase):
    def test_comparison_operators(self):
        self.assertTrue(constraints.satisfies("1.2.3", ">=1.2.0"))
        self.assertFalse(constraints.satisfies("1.2.3", "<1.2.3"))
        self.assertTrue(constraints.satisfies("1.2.3", "==1.2.3"))
        self.assertTrue(constraints.satisfies("1.2.3", "1.2.3"))
        self.assertTrue(constraints.satisfies("1.2.3", "!=1.2.4"))

    def test_caret_and_tilde(self):
        self.assertTrue(constraints.satisfies("1.9.0", "^1.2.3"))
        self.assertFalse(constraints.satisfies("2.0.0", "^1.2.3"))
        self.assertTrue(constraints.satisfies("1.2.9", "~1.2.3"))
        self.assertFalse(constraints.satisfies("1.3.0", "~1.2.3"))

    def test_several_clauses(self):
        self.assertTrue(constraints.satisfies("1.4.0", ">=1.2.0, <1.5.0"))
        self.assertFalse(constraints.satisfies("1.5.0", ">=1.2.0, <1.5.0"))

    def test_newest(self):
        versions = ["1.0.0", "1.10.0", "1.9.0", "2.0.0"]
        self.assertEqual(constraints.newest(versions, "^1.0.0"), "1.10.0")
        self.assertIsNone(constraints.newest(versions, "<1.0.0"))


class Cli(unittest.TestCase):
    def test_prints_the_newest_match(self):
        out, err = io.StringIO(), io.StringIO()
        code = cli.main(["^1.0.0", "1.0.0", "1.1.0", "2.0.0"], out, err)
        self.assertEqual(code, 0)
        self.assertEqual(out.getvalue(), "1.1.0\n")


if __name__ == "__main__":
    unittest.main()
__SCAFFOLD_FILE_END__

git init -q
git add -A
git -c user.name=scaffold -c user.email=scaffold@example.invalid commit -qm scaffold
