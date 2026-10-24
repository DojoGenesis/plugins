import unittest

from notesvc import backup, importer, tags
from notesvc.cache import ReadCache
from notesvc.service import NoteService
from notesvc.store import Store


def make():
    store = Store()
    cache = ReadCache()
    return store, cache, NoteService(store, cache)


def prime(svc, *ids):
    for note_id in ids:
        svc.get_note(note_id)


class StaleReadsAreGone(unittest.TestCase):
    def test_edit_body(self):
        _, _, svc = make()
        a = svc.create_note("A", "old")
        prime(svc, a)
        svc.edit_body(a, "new")
        self.assertEqual(svc.get_note(a).body, "new")

    def test_archive_and_unarchive(self):
        _, _, svc = make()
        a = svc.create_note("A")
        prime(svc, a)
        svc.archive_note(a)
        self.assertTrue(svc.get_note(a).archived)
        svc.unarchive_note(a)
        self.assertFalse(svc.get_note(a).archived)

    def test_delete(self):
        _, _, svc = make()
        a = svc.create_note("A")
        prime(svc, a)
        svc.delete_note(a)
        self.assertIsNone(svc.get_note(a))

    def test_add_tag(self):
        _, _, svc = make()
        a = svc.create_note("A")
        prime(svc, a)
        tags.add_tag(svc, a, "urgent")
        self.assertIn("urgent", svc.get_note(a).tags)

    def test_import_replaces_an_existing_note(self):
        _, _, svc = make()
        a = svc.create_note("Old title", "old body")
        prime(svc, a)
        count = importer.import_notes(svc, [{"id": a, "title": "New title", "body": "new body"}])
        self.assertEqual(count, 1)
        note = svc.get_note(a)
        self.assertEqual((note.title, note.body), ("New title", "new body"))

    def test_import_adds_new_notes(self):
        _, _, svc = make()
        importer.import_notes(svc, [{"id": "n50", "title": "Fresh", "tags": ["t"]}])
        note = svc.get_note("n50")
        self.assertEqual((note.title, note.tags), ("Fresh", ["t"]))

    def test_restore_brings_back_old_content_and_removes_extras(self):
        _, _, svc = make()
        a = svc.create_note("A", "original")
        snap = backup.snapshot(svc)
        svc.edit_body(a, "changed")
        extra = svc.create_note("Extra")
        prime(svc, a, extra)
        backup.restore(svc, snap)
        self.assertEqual(svc.get_note(a).body, "original")
        self.assertIsNone(svc.get_note(extra))

    def test_changes_made_after_the_read_are_all_seen(self):
        _, _, svc = make()
        a = svc.create_note("A", "b0")
        prime(svc, a)
        svc.edit_body(a, "b1")
        self.assertEqual(svc.get_note(a).body, "b1")
        svc.edit_body(a, "b2")
        self.assertEqual(svc.get_note(a).body, "b2")
        svc.rename_note(a, "A2")
        note = svc.get_note(a)
        self.assertEqual((note.title, note.body), ("A2", "b2"))


class CacheStillWorks(unittest.TestCase):
    def test_reads_are_still_cached(self):
        store, _, svc = make()
        a = svc.create_note("A")
        before = store.reads
        svc.get_note(a)
        svc.get_note(a)
        svc.get_note(a)
        self.assertEqual(store.reads - before, 1)

    def test_cache_is_used_again_after_a_write(self):
        store, _, svc = make()
        a = svc.create_note("A")
        prime(svc, a)
        svc.edit_body(a, "x")
        before = store.reads
        svc.get_note(a)
        svc.get_note(a)
        self.assertEqual(store.reads - before, 1)

    def test_other_notes_stay_cached_after_edit(self):
        store, _, svc = make()
        a = svc.create_note("A")
        b = svc.create_note("B")
        prime(svc, a, b)
        svc.edit_body(a, "x")
        before = store.reads
        svc.get_note(b)
        self.assertEqual(store.reads, before)

    def test_other_notes_stay_cached_after_archive(self):
        store, _, svc = make()
        a = svc.create_note("A")
        b = svc.create_note("B")
        prime(svc, a, b)
        svc.archive_note(a)
        before = store.reads
        svc.get_note(b)
        self.assertEqual(store.reads, before)

    def test_other_notes_stay_cached_after_delete(self):
        store, _, svc = make()
        a = svc.create_note("A")
        b = svc.create_note("B")
        prime(svc, a, b)
        svc.delete_note(a)
        before = store.reads
        svc.get_note(b)
        self.assertEqual(store.reads, before)

    def test_other_notes_stay_cached_after_add_tag(self):
        store, _, svc = make()
        a = svc.create_note("A")
        b = svc.create_note("B")
        prime(svc, a, b)
        tags.add_tag(svc, a, "t")
        before = store.reads
        svc.get_note(b)
        self.assertEqual(store.reads, before)

    def test_import_only_drops_the_imported_ids(self):
        store, _, svc = make()
        a = svc.create_note("A")
        b = svc.create_note("B")
        c = svc.create_note("C")
        prime(svc, a, b, c)
        importer.import_notes(svc, [{"id": a, "title": "A2"}])
        before = store.reads
        svc.get_note(b)
        svc.get_note(c)
        self.assertEqual(store.reads, before)
        self.assertEqual(svc.get_note(a).title, "A2")

    def test_missing_note_edit_still_raises(self):
        _, _, svc = make()
        with self.assertRaises(KeyError):
            svc.edit_body("nope", "x")

    def test_deleting_a_missing_note_is_quiet(self):
        _, _, svc = make()
        svc.delete_note("nope")
        self.assertIsNone(svc.get_note("nope"))


if __name__ == "__main__":
    unittest.main()
