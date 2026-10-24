"""Interval methods named in section 4 of PREREG-2026-10-23-routing.md. Standard library only."""
import math
import random

Z95 = 1.959963984540054


def wilson(x, n, z=Z95):
    """Wilson score interval for x successes out of n."""
    if n == 0:
        return (float("nan"), float("nan"))
    p = x / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (centre - half, centre + half)


def newcombe_diff(x1, n1, x2, n2, z=Z95):
    """p1 - p2 with Newcombe's hybrid score interval (1998, method 10)."""
    p1, p2 = x1 / n1, x2 / n2
    l1, u1 = wilson(x1, n1, z)
    l2, u2 = wilson(x2, n2, z)
    d = p1 - p2
    lo = d - math.sqrt((p1 - l1) ** 2 + (u2 - p2) ** 2)
    hi = d + math.sqrt((u1 - p1) ** 2 + (p2 - l2) ** 2)
    return d, lo, hi


def pooled_mean(cells):
    """cells: {case: [values]} -> mean over cases of each case's mean (every case weighs the same)."""
    means = [sum(v) / len(v) for v in cells.values() if v]
    return sum(means) / len(means)


def bootstrap_ratio(routed, base, resamples=10000, seed=20261023):
    """Ratio of pooled means routed/base with a 95% percentile interval.

    routed, base: {case: [agent cost per run]}. Runs are resampled with replacement within each case and arm.
    """
    rng = random.Random(seed)
    point = pooled_mean(routed) / pooled_mean(base)
    stats = []
    for _ in range(resamples):
        r = {c: [rng.choice(v) for _ in v] for c, v in routed.items() if v}
        b = {c: [rng.choice(v) for _ in v] for c, v in base.items() if v}
        stats.append(pooled_mean(r) / pooled_mean(b))
    stats.sort()
    lo = stats[int(0.025 * resamples)]
    hi = stats[int(0.975 * resamples) - 1]
    return point, lo, hi
