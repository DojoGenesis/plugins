"""Tag helpers."""


def add_tag(service, note_id, tag):
    note = service._load(note_id)
    if tag not in note.tags:
        note.tags.append(tag)
        service._write(note)


def notes_with_tag(service, tag):
    return sorted(n.id for n in service.store.all() if tag in n.tags)
