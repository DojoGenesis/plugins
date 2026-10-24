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
        service._write(note)
        count += 1
    return count
