"""Fixture builder for the doctor tests.

Writes a fake home (a .claude folder and a .claude.json), plugin install folders and transcript files
from hand-written literals. Paths are neutral. Nothing here imports doctor.py, so an expectation can
never be produced by the code under test.
"""
import json
import os
import stat
import time


def iso(seconds_ago=0, zulu=True, fraction=True):
    t = time.time() - seconds_ago
    base = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(t))
    if fraction:
        base += ".%03d" % int((t % 1) * 1000)
    return base + ("Z" if zulu else "+00:00")


def hook_line(atype, session, uuid, event="SessionStart", ts=None, **att):
    """One transcript line holding a hook attachment, in the shape the CLI records."""
    attachment = {
        "type": atype,
        "hookName": "%s:startup" % event,
        "hookEvent": event,
        "toolUseID": "toolu_fixture",
    }
    attachment.update(att)
    return {
        "parentUuid": None,
        "isSidechain": False,
        "attachment": attachment,
        "type": "attachment",
        "uuid": uuid,
        "timestamp": ts or iso(60),
        "sessionId": session,
        "cwd": "/home/tester/proj",
        "version": "2.1.286",
    }


def error_line(session, uuid, command, exit_code=127, stderr="python: command not found", event="SessionStart", ts=None):
    return hook_line(
        "hook_non_blocking_error",
        session,
        uuid,
        event=event,
        ts=ts,
        command=command,
        exitCode=exit_code,
        stderr="Failed with non-blocking status code: /bin/sh: " + stderr,
        stdout="",
        durationMs=12,
    )


def success_line(session, uuid, command, stdout, event="SessionStart", ts=None):
    return hook_line(
        "hook_success",
        session,
        uuid,
        event=event,
        ts=ts,
        command=command,
        exitCode=0,
        stdout=stdout,
        stderr="",
        content=stdout,
        durationMs=30,
    )


def context_line(session, uuid, content, event="SessionStart", ts=None):
    return hook_line("hook_additional_context", session, uuid, event=event, ts=ts, content=content)


class Fixture(object):
    def __init__(self, root):
        self.root = root
        self.home = os.path.join(root, "home")
        self.project = os.path.join(root, "project")
        self.claude = os.path.join(self.home, ".claude")
        self.bin = os.path.join(root, "bin")
        for d in (self.claude, self.project, self.bin, os.path.join(self.claude, "plugins", "cache")):
            os.makedirs(d, exist_ok=True)
        self.installed = {}
        self.settings = {}
        self.enabled = {}

    # -- json plumbing
    def write_json(self, path, data):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            if isinstance(data, str):
                fh.write(data)
            else:
                json.dump(data, fh)

    def write_text(self, path, text, mode=None):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            fh.write(text)
        if mode is not None:
            os.chmod(path, mode)

    def exe(self, path, text="#!/bin/sh\nexit 0\n"):
        self.write_text(path, text, 0o755)

    # -- settings
    def save_settings(self, **extra):
        data = dict(self.settings)
        data.update(extra)
        if self.enabled:
            data["enabledPlugins"] = dict(self.enabled)
        self.write_json(os.path.join(self.claude, "settings.json"), data)

    def project_settings(self, data, local=False):
        name = "settings.local.json" if local else "settings.json"
        self.write_json(os.path.join(self.project, ".claude", name), data)

    def global_config(self, data):
        self.write_json(os.path.join(self.home, ".claude.json"), data)

    # -- plugins
    def plugin(self, name, market="fixture-market", hooks=None, enable=True, scope="user", project_path=None,
               manifest=None, files=None, make_dir=True, hooks_text=None):
        key = "%s@%s" % (name, market)
        root = os.path.join(self.claude, "plugins", "cache", market, name, "1.0.0")
        if make_dir:
            os.makedirs(os.path.join(root, ".claude-plugin"), exist_ok=True)
            mf = {"name": name, "version": "1.0.0", "description": "fixture plugin"}
            if manifest:
                mf.update(manifest)
            self.write_json(os.path.join(root, ".claude-plugin", "plugin.json"), mf)
            if hooks_text is not None:
                self.write_json(os.path.join(root, "hooks", "hooks.json"), hooks_text)
            elif hooks is not None:
                self.write_json(os.path.join(root, "hooks", "hooks.json"), hooks)
            for rel, text in (files or {}).items():
                mode = 0o755 if rel.endswith((".sh", ".py")) and rel.startswith("hooks/") else None
                self.write_text(os.path.join(root, rel), text, mode)
        entry = {"scope": scope, "installPath": root, "version": "1.0.0"}
        if project_path:
            entry["projectPath"] = project_path
        self.installed.setdefault(key, []).append(entry)
        if enable is not None:
            self.enabled[key] = enable
        self.flush_installed()
        return root

    def flush_installed(self):
        self.write_json(
            os.path.join(self.claude, "plugins", "installed_plugins.json"),
            {"version": 2, "plugins": self.installed},
        )

    def hooks_json(self, command, event="SessionStart", status=None, extra=None):
        hook = {"type": "command", "command": command}
        if status:
            hook["statusMessage"] = status
        if extra:
            hook.update(extra)
        return {"hooks": {event: [{"hooks": [hook]}]}}

    # -- transcripts
    def transcript(self, lines, project="-home-tester-proj", session="sess-1", subagent=False, age_days=0.0, raw_lines=None):
        d = os.path.join(self.claude, "projects", project)
        if subagent:
            d = os.path.join(d, session, "subagents")
            name = "agent-%s.jsonl" % session
        else:
            name = "%s.jsonl" % session
        os.makedirs(d, exist_ok=True)
        path = os.path.join(d, name)
        with open(path, "w") as fh:
            for ln in lines:
                fh.write((ln if isinstance(ln, str) else json.dumps(ln)) + "\n")
            for ln in raw_lines or []:
                fh.write(ln + "\n")
        if age_days:
            old = time.time() - age_days * 86400
            os.utime(path, (old, old))
        return path

    # -- fake binaries
    def fake_bin(self, name, text="#!/bin/sh\nexit 0\n", directory=None):
        path = os.path.join(directory or self.bin, name)
        self.exe(path, text)
        return path


def tree_hash(root, skip=("Library",)):
    """sha256 over every path, mode and content under root. Used to prove a run wrote nothing.

    skip: folder names to leave out. The system python caches its own standard-library bytecode
    under HOME/Library when it starts, which is the interpreter, not the doctor.
    """
    import hashlib

    h = hashlib.sha256()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in skip)
        for fn in sorted(filenames):
            p = os.path.join(dirpath, fn)
            h.update(p.encode())
            try:
                st = os.lstat(p)
                h.update(str(stat.S_IMODE(st.st_mode)).encode())
                if stat.S_ISREG(st.st_mode):
                    with open(p, "rb") as fh:
                        h.update(fh.read())
            except OSError:
                pass
        for dn in dirnames:
            h.update(os.path.join(dirpath, dn).encode())
    return h.hexdigest()
