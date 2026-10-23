#!/bin/sh
# Writes the project files into the current directory.
set -e

cat > '.gitignore' <<'__SCAFFOLD_FILE_END__'
__pycache__/
*.pyc
__SCAFFOLD_FILE_END__

cat > 'README.md' <<'__SCAFFOLD_FILE_END__'
# gradebook

Turns a class's scores (CSV text) into a ranked table with letter grades.

Layout:

- `gradebook/stats.py`   numbers: mean, median, letter grades, summary
- `gradebook/report.py`  CSV parsing and the text table
- `gradebook/cli.py`     command line front end
- `tests/`               the checks that must pass
__SCAFFOLD_FILE_END__

mkdir -p 'gradebook'
cat > 'gradebook/__init__.py' <<'__SCAFFOLD_FILE_END__'
"""gradebook: scores in, ranked report out."""
__SCAFFOLD_FILE_END__

mkdir -p 'tests'
cat > 'tests/__init__.py' <<'__SCAFFOLD_FILE_END__'
"""Tests for gradebook."""
__SCAFFOLD_FILE_END__

mkdir -p 'tests'
cat > 'tests/test_gradebook.py' <<'__SCAFFOLD_FILE_END__'
import io
import unittest

from gradebook import cli, report, stats


class Stats(unittest.TestCase):
    def test_mean(self):
        self.assertEqual(stats.mean([1, 2, 3, 4]), 2.5)

    def test_median_odd_and_even(self):
        self.assertEqual(stats.median([3, 1, 2]), 2)
        self.assertEqual(stats.median([4, 1, 3, 2]), 2.5)

    def test_letter_grades(self):
        self.assertEqual(stats.letter_grade(95), "A")
        self.assertEqual(stats.letter_grade(85), "B")
        self.assertEqual(stats.letter_grade(75), "C")
        self.assertEqual(stats.letter_grade(65), "D")
        self.assertEqual(stats.letter_grade(10), "F")

    def test_summarize(self):
        summary = stats.summarize([50, 100])
        self.assertEqual(summary["count"], 2)
        self.assertEqual(summary["mean"], 75)
        self.assertEqual(summary["min"], 50)
        self.assertEqual(summary["max"], 100)


class Report(unittest.TestCase):
    def test_parse_rows(self):
        rows = report.parse_rows("name,score\nAda,95\nBob,82.5\n")
        self.assertEqual(rows, [("Ada", 95.0), ("Bob", 82.5)])

    def test_render_has_header_rows_and_summary(self):
        text = report.render([("Bob", 82.5), ("Ada", 95.0)])
        lines = text.split("\n")
        self.assertEqual(lines[0], "Name | Score | Grade")
        self.assertEqual(lines[1], "Ada | 95.0 | A")
        self.assertEqual(lines[2], "Bob | 82.5 | B")
        self.assertTrue(lines[3].startswith("Class: 2 students"))

    def test_render_nothing(self):
        self.assertEqual(report.render([]), "No scores")


class Cli(unittest.TestCase):
    def test_reads_stdin(self):
        out, err = io.StringIO(), io.StringIO()
        code = cli.main([], io.StringIO("name,score\nAda,95\n"), out, err)
        self.assertEqual(code, 0)
        self.assertIn("Ada | 95.0 | A", out.getvalue())
        self.assertEqual(err.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
__SCAFFOLD_FILE_END__

git init -q
git add -A
git -c user.name=scaffold -c user.email=scaffold@example.invalid commit -qm scaffold
