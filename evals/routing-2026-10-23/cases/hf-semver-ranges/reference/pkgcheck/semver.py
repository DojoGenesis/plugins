"""Version precedence, following the Semantic Versioning rules."""

import re

_CORE = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+")
_NUMERIC = re.compile(r"[0-9]+")


def _split(version):
    """Return ((major, minor, patch), identifiers-or-None). Raises ValueError."""
    if not isinstance(version, str):
        raise ValueError(f"malformed version: {version!r}")
    main, _plus, _build = version.partition("+")
    core, dash, prerelease = main.partition("-")
    if not _CORE.fullmatch(core):
        raise ValueError(f"malformed version: {version!r}")
    numbers = tuple(int(part) for part in core.split("."))
    identifiers = None
    if dash:
        identifiers = prerelease.split(".")
        if any(ident == "" for ident in identifiers):
            raise ValueError(f"malformed version: {version!r}")
    return numbers, identifiers


def parse_core(version):
    """Return (major, minor, patch) as ints. Raises ValueError if malformed."""
    return _split(version)[0]


def _compare_identifier(x, y):
    x_num = bool(_NUMERIC.fullmatch(x))
    y_num = bool(_NUMERIC.fullmatch(y))
    if x_num and y_num:
        a, b = int(x), int(y)
    elif x_num:
        return -1
    elif y_num:
        return 1
    else:
        a, b = x, y
    return (a > b) - (a < b)


def compare(a, b):
    """Return -1, 0 or 1 as version `a` has lower, equal or higher precedence than `b`."""
    core_a, pre_a = _split(a)
    core_b, pre_b = _split(b)
    if core_a != core_b:
        return -1 if core_a < core_b else 1
    if pre_a is None and pre_b is None:
        return 0
    if pre_a is None:
        return 1
    if pre_b is None:
        return -1
    for x, y in zip(pre_a, pre_b):
        result = _compare_identifier(x, y)
        if result:
            return result
    return (len(pre_a) > len(pre_b)) - (len(pre_a) < len(pre_b))
