"""Numbers for the gradebook."""


def mean(values):
    values = list(values)
    if not values:
        raise ValueError("mean of empty data")
    return sum(values) / len(values)


def median(values):
    ordered = sorted(values)
    count = len(ordered)
    if count == 0:
        raise ValueError("median of empty data")
    mid = count // 2
    if count % 2:
        return float(ordered[mid])
    return (ordered[mid - 1] + ordered[mid]) / 2


def letter_grade(score):
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    if score >= 60:
        return "D"
    return "F"


def summarize(values):
    values = list(values)
    if not values:
        return {"count": 0, "mean": None, "median": None, "min": None, "max": None}
    return {
        "count": len(values),
        "mean": mean(values),
        "median": median(values),
        "min": min(values),
        "max": max(values),
    }
