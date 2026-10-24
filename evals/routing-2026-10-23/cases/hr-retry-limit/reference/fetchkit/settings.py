"""Build the effective settings from defaults, environment and explicit overrides."""

from fetchkit.defaults import DEFAULTS

ENV_PREFIX = "FETCHKIT_"


def _from_env(env):
    found = {}
    if not env:
        return found
    raw = env.get(ENV_PREFIX + "MAX_RETRIES")
    if raw not in (None, ""):
        found["max_retries"] = int(raw)
    raw = env.get(ENV_PREFIX + "TIMEOUT")
    if raw not in (None, ""):
        found["timeout"] = float(raw)
    raw = env.get(ENV_PREFIX + "BACKOFF")
    if raw not in (None, ""):
        found["backoff"] = float(raw)
    return found


def load_settings(overrides=None, env=None):
    """Return the effective settings.

    Explicit overrides win over the environment, which wins over the defaults.
    """
    merged = dict(DEFAULTS)
    merged.update(_from_env(env))
    if overrides:
        for key in ("timeout", "backoff", "max_retries"):
            if overrides.get(key) is not None:
                merged[key] = overrides[key]
    return merged
