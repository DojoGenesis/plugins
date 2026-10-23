"""CSV in, text table out."""

import csv
import io

from gradebook import stats


def _is_number(text):
    try:
        float(text)
    except ValueError:
        return False
    return True


def parse_rows(text):
    rows = []
    seen_first = False
    for fields in csv.reader(io.StringIO(text)):
        if not fields or (len(fields) == 1 and not fields[0].strip()):
            continue
        if not seen_first:
            seen_first = True
            if len(fields) >= 2 and not _is_number(fields[1].strip()):
                continue  # header row
        if len(fields) != 2:
            raise ValueError(f"expected 2 fields, got {len(fields)}: {fields!r}")
        name = fields[0].strip()
        if not name:
            raise ValueError("missing name")
        try:
            score = float(fields[1].strip())
        except ValueError:
            raise ValueError(f"bad score for {name!r}: {fields[1]!r}") from None
        rows.append((name, score))
    return rows


def render(rows):
    if not rows:
        return "No scores"
    ordered = sorted(rows, key=lambda row: (-row[1], row[0]))
    lines = ["Name | Score | Grade"]
    for name, score in ordered:
        lines.append(f"{name} | {score:.1f} | {stats.letter_grade(score)}")
    summary = stats.summarize([score for _, score in rows])
    noun = "student" if summary["count"] == 1 else "students"
    lines.append(
        f"Class: {summary['count']} {noun}, "
        f"mean {summary['mean']:.1f}, median {summary['median']:.1f}"
    )
    return "\n".join(lines)
