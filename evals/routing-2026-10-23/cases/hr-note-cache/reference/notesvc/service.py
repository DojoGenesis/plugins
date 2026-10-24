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
        self._write(note)

    def archive_note(self, note_id):
        self._set_flag(note_id, "archived", True)

    def unarchive_note(self, note_id):
        self._set_flag(note_id, "archived", False)

    def _set_flag(self, note_id, name, value):
        note = self._load(note_id)
        setattr(note, name, value)
        self._write(note)

    def delete_note(self, note_id):
        self.store.delete(note_id)
        self.cache.invalidate(note_id)
