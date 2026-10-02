#!/usr/bin/env python3
"""dojo-router: PreToolUse hook for the Agent (alias Task) tool.

Flags a subagent dispatch that names no model, because such a dispatch runs on whatever the
session runs on. Warns by default (context for the model plus a message for the person),
denies in block mode, silent when off.

A hook cannot see the model pin in a custom agent's own definition, so this script reads
agent files (read-only, bounded) before it speaks: every .claude/agents folder from the
session's folder up to the repository root, and the user config's agents folder, each searched
through its subfolders. Agents it cannot find that way (passed on the command line, set by a
managed policy) stay invisible, so block mode refuses built-in agent types only and merely
warns about custom ones. Fails open on anything unexpected: exit 0, no output.
"""
import os
import stat
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import router_common as rc  # noqa: E402

# Built-in agent types that carry no model pin of their own: warning on them is right.
# Verified against Claude Code 2.1.286. Re-check on upgrade.
UNPINNED_BUILTINS = ("general-purpose", "Explore", "Plan")
# Built-in types that pin a model in their built-in definition (2.1.286): never flag these.
PINNED_BUILTINS = ("statusline-setup",)

MAX_AGENT_FILES = 200  # .md files read per agents folder tree
MAX_AGENT_FILES_TOTAL = 400  # across every folder tree searched
MAX_AGENT_DIRS = 400  # sub-folders visited per agents folder tree
MAX_PARENT_LEVELS = 40  # folders climbed above the session's folder
MAX_AGENT_FILE_BYTES = 64 * 1024  # larger files are not read at all
FRONTMATTER_READ_BYTES = 16 * 1024  # the frontmatter is at the top, so only this much is read
MAX_FRONTMATTER_LINES = 80


def _is_pin(value):
    """A frontmatter model value that really pins a model. Empty and 'inherit' do not."""
    if not isinstance(value, str):
        return False
    cleaned = value.strip().lower()
    return cleaned not in ("", "inherit")


def _frontmatter(text):
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    found = {}
    for line in lines[1:MAX_FRONTMATTER_LINES]:
        if line.strip() == "---":
            return found
        if line[:1] in (" ", "\t") or ":" not in line:
            continue
        key, _, value = line.partition(":")
        found[key.strip().lower()] = value.strip().strip("\"'").strip()
    return None  # never closed: treat as not an agent file


def _agent_dirs(cwd):
    """Agents folders in priority order: the session's own .claude/agents, then each parent's up to and
    including the repository root (the first folder holding .git), then the user config's agents folder.
    Without a repository the climb goes on to the top of the filesystem, bounded: reading a folder too
    many only makes the hook quieter, never louder."""
    dirs = []
    if isinstance(cwd, str) and cwd.strip():
        current = os.path.abspath(cwd)
        for _ in range(MAX_PARENT_LEVELS):
            dirs.append(os.path.join(current, ".claude", "agents"))
            if os.path.exists(os.path.join(current, ".git")):
                break
            parent = os.path.dirname(current)
            if parent == current:
                break
            current = parent
    config = os.environ.get("CLAUDE_CONFIG_DIR")
    if not config or not config.strip():
        config = os.path.expanduser("~/.claude")
    if config and not config.startswith("~"):
        dirs.append(os.path.join(config, "agents"))
    seen = set()
    unique = []
    for directory in dirs:
        key = os.path.normcase(os.path.abspath(directory))
        if key not in seen:
            seen.add(key)
            unique.append(directory)
    return unique


def _agent_files(root, budget):
    """Yield .md paths under root, subfolders included, in a stable order. Symlinked folders are not
    followed. `budget` is a one-item list holding how many files the whole search may still read."""
    files = 0
    dirs = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirs += 1
        if dirs > MAX_AGENT_DIRS:
            return
        dirnames.sort()
        for name in sorted(filenames):
            if not name.endswith(".md"):
                continue
            if files >= MAX_AGENT_FILES or budget[0] <= 0:
                return
            files += 1
            budget[0] -= 1
            yield os.path.join(dirpath, name)


def custom_agent_pins_model(agent_type, cwd):
    """True when an agent file named `agent_type` pins a model in its frontmatter.

    Searches project folders nearest first, then the user's. The first file with that name decides.
    """
    budget = [MAX_AGENT_FILES_TOTAL]
    for directory in _agent_dirs(cwd):
        for path in _agent_files(directory, budget):
            try:
                info = os.stat(path)
                if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_AGENT_FILE_BYTES:
                    continue
                with open(path, "rb") as handle:
                    text = handle.read(FRONTMATTER_READ_BYTES).decode("utf-8", "replace")
                meta = _frontmatter(text)
            except Exception:
                continue
            if meta is None:
                continue
            # An agent's type is its frontmatter name, not its filename.
            name = meta.get("name") or os.path.basename(path)[:-3]
            if name == agent_type:
                return _is_pin(meta.get("model"))
    return False


def _env_pins_everything():
    for name in ("CLAUDE_CODE_SUBAGENT_MODEL", "CLAUDE_CODE_SUBAGENT_MODEL_FORCE"):
        value = os.environ.get(name)
        if isinstance(value, str) and value.strip():
            return True
    return False


def build_text(agent_type, suggest, custom, blocking, block_note=False):
    label = rc.safe_label(agent_type)
    if blocking:
        return (
            "dojo-router: this %s dispatch names no model — it would run on your session's model, "
            "so it was blocked. Retry the call with model set to haiku (look things up), sonnet "
            "(build or review) or opus (judge); suggested here: %s. "
            "Allow unpinned dispatches with DOJO_ROUTER_OFF=1 or mode warn." % (label, suggest)
        )
    extra = "If this agent's definition pins a model, ignore this. " if custom else ""
    note = ("Block mode refuses built-in agent types only, because a custom agent's own pin "
            "can't be seen from here, so this went ahead. ") if block_note else ""
    return (
        "dojo-router: this %s dispatch names no model — it will run on your session's model. "
        "Set model: %s (suggested here: %s). %s%s"
        "Turn off with DOJO_ROUTER_OFF=1 or mode off." % (label, rc.ROLE_TABLE, suggest, extra, note)
    )


def main():
    payload = rc.read_payload()
    if payload is None or rc.killed():
        return
    mode = rc.get_mode()
    if mode == "off":
        return
    if payload.get("tool_name") not in ("Agent", "Task"):
        return
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return

    agent_type = tool_input.get("subagent_type")
    if agent_type is None:
        agent_type = "general-purpose"
    if not isinstance(agent_type, str):
        return
    agent_type = agent_type.strip() or "general-purpose"
    if ":" in agent_type or agent_type == "fork" or agent_type in PINNED_BUILTINS:
        return

    model = tool_input.get("model")
    if model is not None:
        if not isinstance(model, str):
            return  # not something we can judge
        if _is_pin(model):
            return

    if _env_pins_everything():
        return

    custom = agent_type not in UNPINNED_BUILTINS
    if custom_agent_pins_model(agent_type, payload.get("cwd")):
        return

    suggest = rc.get_explore_tier() if agent_type == "Explore" else rc.get_default_tier()
    if mode == "block" and not custom:
        rc.emit_deny(build_text(agent_type, suggest, custom, True))
        return
    # Warn mode, or block mode for a custom type: its pin may sit where this hook cannot read, and a
    # refusal would leave no way through except overriding the pin, so it gets a warning instead.
    if rc.first_time(payload.get("session_id"), "agent:" + agent_type):
        rc.emit_warn(build_text(agent_type, suggest, custom, False, block_note=(mode == "block")))


if __name__ == "__main__":
    rc.run(main)
