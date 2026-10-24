import io
import os
import tempfile
import unittest

from gradebook import cli, report, stats


class MeanAndMedian(unittest.TestCase):
    def test_mean_values(self):
        self.assertEqual(stats.mean([1, 2, 3, 4]), 2.5)
        self.assertEqual(stats.mean([7]), 7)
        self.assertAlmostEqual(stats.mean([0.1, 0.2, 0.3]), 0.2)

    def test_mean_returns_float(self):
        self.assertIsInstance(stats.mean([2, 4]), float)

    def test_mean_accepts_any_sequence(self):
        self.assertEqual(stats.mean((1, 2, 3)), 2)

    def test_mean_of_nothing_raises(self):
        with self.assertRaises(ValueError):
            stats.mean([])

    def test_median_odd(self):
        self.assertEqual(stats.median([9, 1, 5]), 5)

    def test_median_even_averages_the_middle_two(self):
        self.assertEqual(stats.median([10, 2, 8, 4]), 6)
        self.assertEqual(stats.median([1, 2]), 1.5)

    def test_median_single(self):
        self.assertEqual(stats.median([42]), 42)

    def test_median_does_not_change_the_input(self):
        data = [3, 1, 2]
        stats.median(data)
        self.assertEqual(data, [3, 1, 2])

    def test_median_of_nothing_raises(self):
        with self.assertRaises(ValueError):
            stats.median([])


class LetterGrades(unittest.TestCase):
    def test_boundaries(self):
        cases = [
            (100, "A"), (90.0, "A"), (89.99, "B"), (80, "B"), (79.99, "C"),
            (70, "C"), (69.5, "D"), (60, "D"), (59.99, "F"), (0, "F"),
        ]
        for score, grade in cases:
            self.assertEqual(stats.letter_grade(score), grade, score)

    def test_above_one_hundred_is_still_an_a(self):
        self.assertEqual(stats.letter_grade(104.5), "A")


class Summarize(unittest.TestCase):
    def test_keys_and_values(self):
        summary = stats.summarize([90, 70, 80, 100])
        self.assertEqual(
            summary,
            {"count": 4, "mean": 85, "median": 85, "min": 70, "max": 100},
        )

    def test_exact_keys(self):
        self.assertEqual(
            sorted(stats.summarize([1])), ["count", "max", "mean", "median", "min"]
        )

    def test_empty(self):
        self.assertEqual(
            stats.summarize([]),
            {"count": 0, "mean": None, "median": None, "min": None, "max": None},
        )


class ParseRows(unittest.TestCase):
    def test_header_is_skipped(self):
        self.assertEqual(report.parse_rows("name,score\nAda,95\n"), [("Ada", 95.0)])

    def test_no_header(self):
        self.assertEqual(
            report.parse_rows("Ada,95\nBob,82.5"), [("Ada", 95.0), ("Bob", 82.5)]
        )

    def test_blank_lines_and_whitespace(self):
        text = "\n  name , score \n\n  Ada ,  95 \n   \nBob,70\n\n"
        self.assertEqual(report.parse_rows(text), [("Ada", 95.0), ("Bob", 70.0)])

    def test_scores_are_floats(self):
        ((_, score),) = report.parse_rows("Ada,95")
        self.assertIsInstance(score, float)

    def test_header_only_and_empty_text(self):
        self.assertEqual(report.parse_rows("name,score\n"), [])
        self.assertEqual(report.parse_rows(""), [])
        self.assertEqual(report.parse_rows("\n\n"), [])

    def test_quoted_names(self):
        self.assertEqual(
            report.parse_rows('"Lovelace, Ada",99\n'), [("Lovelace, Ada", 99.0)]
        )

    def test_bad_score_after_the_first_line_raises(self):
        with self.assertRaises(ValueError):
            report.parse_rows("Ada,95\nBob,absent\n")

    def test_wrong_field_count_raises(self):
        with self.assertRaises(ValueError):
            report.parse_rows("Ada,95,extra\n")
        with self.assertRaises(ValueError):
            report.parse_rows("Ada,95\nBob\n")

    def test_missing_name_raises(self):
        with self.assertRaises(ValueError):
            report.parse_rows("Ada,95\n,80\n")

    def test_only_the_first_line_may_be_a_header(self):
        with self.assertRaises(ValueError):
            report.parse_rows("Ada,95\nname,score\n")


class Render(unittest.TestCase):
    def test_nothing(self):
        self.assertEqual(report.render([]), "No scores")

    def test_full_table(self):
        text = report.render([("Bob", 82.5), ("Ada", 95.0), ("Cy", 55.0)])
        self.assertEqual(
            text,
            "\n".join(
                [
                    "Name | Score | Grade",
                    "Ada | 95.0 | A",
                    "Bob | 82.5 | B",
                    "Cy | 55.0 | F",
                    "Class: 3 students, mean 77.5, median 82.5",
                ]
            ),
        )

    def test_no_trailing_newline(self):
        self.assertFalse(report.render([("Ada", 95.0)]).endswith("\n"))

    def test_singular(self):
        text = report.render([("Ada", 95.0)])
        self.assertEqual(text.split("\n")[-1], "Class: 1 student, mean 95.0, median 95.0")

    def test_ties_sort_by_name_in_plain_string_order(self):
        text = report.render([("bob", 80.0), ("Ada", 80.0), ("Zed", 80.0), ("Cy", 95.0)])
        names = [line.split(" | ")[0] for line in text.split("\n")[1:5]]
        self.assertEqual(names, ["Cy", "Ada", "Zed", "bob"])

    def test_grade_uses_the_unrounded_score(self):
        text = report.render([("Eve", 89.96)])
        self.assertEqual(text.split("\n")[1], "Eve | 90.0 | B")

    def test_scores_sorted_high_to_low(self):
        text = report.render([("A", 10.0), ("B", 99.0), ("C", 55.5)])
        scores = [line.split(" | ")[1] for line in text.split("\n")[1:4]]
        self.assertEqual(scores, ["99.0", "55.5", "10.0"])


class CommandLine(unittest.TestCase):
    CSV = "name,score\nAda,95\nBob,82.5\n"

    def run_main(self, argv, stdin_text=""):
        out, err = io.StringIO(), io.StringIO()
        code = cli.main(argv, io.StringIO(stdin_text), out, err)
        return code, out.getvalue(), err.getvalue()

    def test_stdin(self):
        code, out, err = self.run_main([], self.CSV)
        self.assertEqual(code, 0)
        self.assertEqual(err, "")
        self.assertTrue(out.endswith("\n"))
        self.assertEqual(out, report.render(report.parse_rows(self.CSV)) + "\n")

    def test_file_argument(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "scores.csv")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(self.CSV)
            code, out, err = self.run_main([path], "ignored")
        self.assertEqual(code, 0)
        self.assertIn("Bob | 82.5 | B", out)
        self.assertEqual(err, "")

    def test_empty_input(self):
        code, out, _ = self.run_main([], "")
        self.assertEqual((code, out), (0, "No scores\n"))

    def test_bad_data(self):
        code, out, err = self.run_main([], "Ada,95\nBob,absent\n")
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertTrue(err.startswith("error: "))
        self.assertTrue(err.endswith("\n"))

    def test_missing_file(self):
        code, out, err = self.run_main(["/no/such/dir/scores.csv"])
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertTrue(err.startswith("error: "))

    def test_too_many_arguments(self):
        code, out, err = self.run_main(["a.csv", "b.csv"])
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertTrue(err.startswith("usage:"))


if __name__ == "__main__":
    unittest.main()
