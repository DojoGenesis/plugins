#!/bin/sh
# Writes the project files into the current directory.
set -e

mkdir -p 'notesvc'
cat > 'notesvc/__init__.py' <<'__SCAFFOLD_FILE_END__'
"""notesvc: a small note service with an in-memory store and a read cache."""
__SCAFFOLD_FILE_END__

mkdir -p 'notesvc'
cat > 'notesvc/backup.py' <<'__SCAFFOLD_FILE_END__'
"""Snapshot and restore the whole note set."""


def snapshot(service):
    return service.store.all()


def restore(service, notes):
    """Make the store hold exactly `notes`."""
    wanted = {n.id for n in notes}
    for existing in service.store.all():
        if existing.id not in wanted:
            service.delete_note(existing.id)
    for note in notes:
        service._write(note)
__SCAFFOLD_FILE_END__

mkdir -p 'notesvc'
cat > 'notesvc/cache.py' <<'__SCAFFOLD_FILE_END__'
"""A read cache keyed by note id."""

import copy


class ReadCache:
    def __init__(self):
        self._items = {}
        self.hits = 0
        self.misses = 0

    def get(self, key):
        if key in self._items:
            self.hits += 1
            return copy.deepcopy(self._items[key])
        self.misses += 1
        return None

    def put(self, key, value):
        self._items[key] = copy.deepcopy(value)

    def invalidate(self, key):
        self._items.pop(key, None)

    def clear(self):
        self._items.clear()

    def __contains__(self, key):
        return key in self._items
__SCAFFOLD_FILE_END__

mkdir -p 'notesvc'
cat > 'notesvc/importer.py' <<'__SCAFFOLD_FILE_END__'
"""Bulk import from plain dictionaries."""

from notesvc.note import Note


def import_notes(service, rows):
    """Create or replace one note per row. Returns how many rows were imported.

    Each row looks like {"id": "n7", "title": "...", "body": "...", "tags": [...]}.
    """
    count = 0
    for row in rows:
        note = Note(
            id=row["id"],
            title=row["title"],
            body=row.get("body", ""),
            tags=list(row.get("tags", [])),
        )
        service.store.save(note)
        count += 1
    return count
__SCAFFOLD_FILE_END__

mkdir -p 'notesvc'
cat > 'notesvc/note.py' <<'__SCAFFOLD_FILE_END__'
"""The Note record."""

from dataclasses import dataclass, field


@dataclass
class Note:
    id: str
    title: str
    body: str = ""
    tags: list = field(default_factory=list)
    archived: bool = False
__SCAFFOLD_FILE_END__

mkdir -p 'notesvc'
cat > 'notesvc/report.py' <<'__SCAFFOLD_FILE_END__'
"""Read-only summary numbers."""


def summary(service):
    notes = service.store.all()
    return {
        "total": len(notes),
        "archived": sum(1 for n in notes if n.archived),
    }
__SCAFFOLD_FILE_END__

mkdir -p 'notesvc'
cat > 'notesvc/search.py' <<'__SCAFFOLD_FILE_END__'
"""Read-only search helpers."""


def find_by_text(service, text):
    text = text.lower()
    return sorted(
        n.id
        for n in service.store.all()
        if text in n.title.lower() or text in n.body.lower()
    )
__SCAFFOLD_FILE_END__

mkdir -p 'notesvc'
cat > 'notesvc/service.py' <<'__SCAFFOLD_FILE_END__'
"""The note service: reads go through the cache, writes go to the store."""

from notesvc.note import Note


class NoteService:
    def __init__(self, store, cache):
        self.store = store
        self.cache = cache
        self._next = 1

    # ---- reads -------------------------------------------------------

    def get_note(self, note_id):
        cached = self.cache.get(note_id)
        if cached is not None:
            return cached
        note = self.store.get(note_id)
        if note is not None:
            self.cache.put(note_id, note)
        return note

    def _load(self, note_id):
        """Read straight from the store (used before changing a note)."""
        note = self.store.get(note_id)
        if note is None:
            raise KeyError(note_id)
        return note

    # ---- writes ------------------------------------------------------

    def _write(self, note):
        self.store.save(note)
        self.cache.invalidate(note.id)

    def create_note(self, title, body="", tags=()):
        while self.store.exists(f"n{self._next}"):
            self._next += 1
        note = Note(id=f"n{self._next}", title=title, body=body, tags=list(tags))
        self._next += 1
        self._write(note)
        return note.id

    def rename_note(self, note_id, title):
        note = self._load(note_id)
        note.title = title
        self._write(note)

    def edit_body(self, note_id, body):
        note = self._load(note_id)
        note.body = body
        self.store.save(note)

    def archive_note(self, note_id):
        self._set_flag(note_id, "archived", True)

    def unarchive_note(self, note_id):
        self._set_flag(note_id, "archived", False)

    def _set_flag(self, note_id, name, value):
        note = self._load(note_id)
        setattr(note, name, value)
        self.store.save(note)

    def delete_note(self, note_id):
        self.store.delete(note_id)
__SCAFFOLD_FILE_END__

mkdir -p 'notesvc'
cat > 'notesvc/store.py' <<'__SCAFFOLD_FILE_END__'
"""In-memory storage. Keeps its own copies so callers cannot change stored notes."""

import copy


class Store:
    def __init__(self):
        self._notes = {}
        self.reads = 0  # number of get() calls, handy for checking cache hits

    def save(self, note):
        self._notes[note.id] = copy.deepcopy(note)

    def get(self, note_id):
        self.reads += 1
        note = self._notes.get(note_id)
        return copy.deepcopy(note) if note is not None else None

    def exists(self, note_id):
        return note_id in self._notes

    def delete(self, note_id):
        self._notes.pop(note_id, None)

    def all(self):
        return [copy.deepcopy(n) for n in self._notes.values()]
__SCAFFOLD_FILE_END__

mkdir -p 'notesvc'
cat > 'notesvc/tags.py' <<'__SCAFFOLD_FILE_END__'
"""Tag helpers."""


def add_tag(service, note_id, tag):
    note = service._load(note_id)
    if tag not in note.tags:
        note.tags.append(tag)
        service.store.save(note)


def notes_with_tag(service, tag):
    return sorted(n.id for n in service.store.all() if tag in n.tags)
__SCAFFOLD_FILE_END__

mkdir -p 'tests'
cat > 'tests/__init__.py' <<'__SCAFFOLD_FILE_END__'
"""Tests for notesvc."""
__SCAFFOLD_FILE_END__

mkdir -p 'tests'
cat > 'tests/test_service.py' <<'__SCAFFOLD_FILE_END__'
import unittest

from notesvc import backup, importer, report, search, tags
from notesvc.cache import ReadCache
from notesvc.service import NoteService
from notesvc.store import Store


def make():
    store = Store()
    cache = ReadCache()
    return store, cache, NoteService(store, cache)


class Basics(unittest.TestCase):
    def test_create_and_get(self):
        _, _, svc = make()
        note_id = svc.create_note("Groceries", "milk", tags=["home"])
        note = svc.get_note(note_id)
        self.assertEqual((note.title, note.body, note.tags), ("Groceries", "milk", ["home"]))

    def test_missing_note_is_none(self):
        _, _, svc = make()
        self.assertIsNone(svc.get_note("nope"))

    def test_second_read_comes_from_the_cache(self):
        store, _, svc = make()
        note_id = svc.create_note("A")
        before = store.reads
        svc.get_note(note_id)
        svc.get_note(note_id)
        self.assertEqual(store.reads - before, 1)

    def test_rename_is_visible_after_a_read(self):
        _, _, svc = make()
        note_id = svc.create_note("Old")
        svc.get_note(note_id)
        svc.rename_note(note_id, "New")
        self.assertEqual(svc.get_note(note_id).title, "New")

    def test_edit_of_a_missing_note_raises(self):
        _, _, svc = make()
        with self.assertRaises(KeyError):
            svc.edit_body("nope", "x")


class Helpers(unittest.TestCase):
    def test_search_and_report(self):
        _, _, svc = make()
        a = svc.create_note("Red apples", "fruit")
        svc.create_note("Blue", "sky")
        svc.archive_note(a)
        self.assertEqual(search.find_by_text(svc, "apple"), [a])
        self.assertEqual(report.summary(svc), {"total": 2, "archived": 1})

    def test_tags_and_import(self):
        _, _, svc = make()
        a = svc.create_note("A")
        tags.add_tag(svc, a, "x")
        self.assertEqual(tags.notes_with_tag(svc, "x"), [a])
        self.assertEqual(importer.import_notes(svc, [{"id": "n9", "title": "Imported"}]), 1)
        self.assertEqual(svc.get_note("n9").title, "Imported")

    def test_snapshot_and_restore_round_trip(self):
        _, _, svc = make()
        a = svc.create_note("A", "one")
        snap = backup.snapshot(svc)
        extra = svc.create_note("Extra")
        backup.restore(svc, snap)
        self.assertIsNotNone(svc.get_note(a))
        self.assertEqual(report.summary(svc)["total"], 1)
        self.assertNotEqual(extra, a)


if __name__ == "__main__":
    unittest.main()
__SCAFFOLD_FILE_END__
