"""Version ranges built on top of pkgcheck.semver."""

from pkgcheck import semver

_OPERATORS = ("==", "!=", ">=", "<=", ">", "<", "^", "~")


def _parse_clause(text):
    text = text.strip()
    if not text:
        raise ValueError("empty clause")
    for operator in _OPERATORS:
        if text.startswith(operator):
            bound = text[len(operator):].strip()
            break
    else:
        operator, bound = "==", text
    semver.parse_core(bound)  # raises ValueError when malformed
    return operator, bound


def _upper_bound(operator, bound):
    major, minor, patch = semver.parse_core(bound)
    if operator == "~":
        return f"{major}.{minor + 1}.0"
    if major > 0:
        return f"{major + 1}.0.0"
    if minor > 0:
        return f"0.{minor + 1}.0"
    return f"0.0.{patch + 1}"


def _holds(version, operator, bound):
    if operator in ("^", "~"):
        upper = _upper_bound(operator, bound)
        return semver.compare(version, bound) >= 0 and semver.compare(version, upper) < 0
    result = semver.compare(version, bound)
    if operator == "==":
        return result == 0
    if operator == "!=":
        return result != 0
    if operator == ">=":
        return result >= 0
    if operator == "<=":
        return result <= 0
    if operator == ">":
        return result > 0
    return result < 0


def satisfies(version, spec):
    clauses = [_parse_clause(part) for part in spec.split(",")]
    semver.parse_core(version)
    return all(_holds(version, operator, bound) for operator, bound in clauses)


def newest(versions, spec):
    best = None
    for version in versions:
        if satisfies(version, spec) and (best is None or semver.compare(version, best) > 0):
            best = version
    return best
