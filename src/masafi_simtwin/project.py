"""The project file: what a ``.mfstz`` is, and how one is made and recognised.

A project is a single file rather than a directory, so that it can be copied,
sent and versioned as one thing.  The suffix is :data:`PROJECT_SUFFIX` —
*mfstz*, near enough to *manifest*, with the ``z`` for the zip it is.  Inside is
an ordinary zip archive holding :data:`MANIFEST_NAME` and, in time, everything
else a project is made of: the flow model, the sub-models, the block library it
was built against.

The archive holds its manifest and the four directories of :data:`FOLDERS`,
which are empty until there is something to put in them.  The manifest holds
what identifies a project — the format and its version, a UUID generated once
and never again, its name, and who made it — and nothing that can be worked out
from the rest of the archive.  Everything else about the contents is still to be
designed, which is exactly why :data:`FORMAT_VERSION` is written from the first
file onwards.

**The history is not in the manifest.**  The manifest says what a project *is*;
what has *happened* to it is a log, and it is kept with the logs, in
:data:`HISTORY_NAME`: append-only, one chained entry per line.  Each line is the
canonical JSON an entry's identifier is computed over, with the identifier
added, so an entry can be read — and checked, by the tool outside this
repository that checks them — on its own.  :func:`read_history` reads it.

**A damaged log never stops a project being written.**  A line that is not an
entry — not JSON, not an object, not even text — is passed over when the log is
read, the next entry is chained to the last entry that could be read, and the log
is written back **byte for byte as it was found**, with the new line at the end.
The application never verifies a history, so it has no business repairing one
either: what it cannot read is kept, and left for the auditor to see.

A project written before the history moved — format version 2 — still carries
its history in the manifest.  It is read from there, and **moved into the log the
first time the project is written**, entries untouched, so the chain goes on
holding across the move and nothing of what it records is lost.

This module has no Qt in it, on purpose.  It is stdlib only — ``zipfile`` and
``json`` — so that it can move to :mod:`simtwin_core` unchanged once that
package exists, which is where a document format belongs.
"""

from __future__ import annotations

import getpass
import hashlib
import json
import os
import re
import socket
import uuid
import zipfile
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

from masafi_simtwin import __version__

#: What a project file is called at the end.
PROJECT_SUFFIX = '.mfstz'

#: The entry inside the archive that says what the archive is.
MANIFEST_NAME = 'manifest.json'

#: The value of ``format`` in the manifest, so that a zip that merely happens to
#: hold a ``manifest.json`` is not taken for a project.
FORMAT_NAME = 'masafi-simtwin-project'

#: The version of the layout inside the archive.  It is written from the first
#: project onwards so that a reader can always tell what it is looking at.
#: Version 3 moved the history out of the manifest into :data:`HISTORY_NAME`.
FORMAT_VERSION = 3

#: The directories every project carries, whether or not anything is in them
#: yet.  A zip has no directories of its own; these are the empty entries that
#: make one show a project's shape when it is opened with any archive tool.
FOLDERS: tuple[str, ...] = ('models/', 'simulations/', 'statistics/', 'logs/')

#: The log a project's history is kept in.  JSON Lines — one entry to a line —
#: because a history is appended to and read from the top, and a log that is a
#: single JSON array has to be taken apart and put back together to add a line
#: to it.
HISTORY_NAME = 'logs/history.jsonl'

#: The events a project's history records.  A session is a pair: one entry when
#: the project is opened, one when it is closed, so that a run that ends in a
#: crash still leaves the opening behind.
EVENT_CREATED = 'created'
EVENT_OPENED = 'opened'
EVENT_CLOSED = 'closed'

#: How many characters of the digest a ``log_item_id`` keeps.  Far more than is
#: forgeable by hand, and short enough to read out over a desk.
LOG_ITEM_ID_LENGTH = 16

#: Events recorded when a project's models change.
EVENT_MODEL_ADDED = 'model-added'
EVENT_MODEL_UPDATED = 'model-updated'
EVENT_MODEL_REMOVED = 'model-removed'

#: What a model file is called at the end.
MODEL_SUFFIX = '.mfst'

#: The folder inside a project that models live in.
MODELS_FOLDER = 'models/'

#: What is appended to a project's name to make the file that holds its lock.
LOCK_SUFFIX = '.lock'

#: The value of ``format`` in a model file.
MODEL_FORMAT_NAME = 'masafi-simtwin-model'

#: The version of the layout inside a model file.
MODEL_FORMAT_VERSION = 1

#: What is put in place of anything that has no business in a file name.
_UNSAFE = re.compile(r'[^\w.-]+', re.UNICODE)


class ModelKind(Enum):
    """The kinds of model a project can hold."""

    PETRI_NET = 'petri-net'
    PROCESS_FLOW = 'process-flow'
    PROCESS_2D = 'process-2d'
    PROCESS_3D = 'process-3d'


#: The kinds that are measured in space as well as in time.  A Petri net and a
#: process flow are graphs: their blocks have no position that means anything,
#: so a distance unit would be a setting with nothing to apply to.
KINDS_WITH_DISTANCE: tuple[ModelKind, ...] = (ModelKind.PROCESS_2D, ModelKind.PROCESS_3D)

#: The kinds that can actually be built yet.
IMPLEMENTED_KINDS: tuple[ModelKind, ...] = (ModelKind.PETRI_NET,)


class ProjectError(Exception):
    """Raised when a file is not a project, or cannot be made into one."""


class ProjectLocked(ProjectError):
    """Raised when a project is already open somewhere else.

    Attributes
    ----------
    holder : dict
        Who has it: their ``pid``, ``user``, ``host`` and when they took it.
    """

    def __init__(self, message: str, holder: dict) -> None:
        super().__init__(message)
        self.holder = holder


def path_for(directory: str | Path, name: str) -> Path:
    """Give the file a project of this name in this directory would be.

    Parameters
    ----------
    directory : str or pathlib.Path
        Where the project is to be kept.
    name : str
        What the project is called.

    Returns
    -------
    pathlib.Path
        The path, with :data:`PROJECT_SUFFIX` appended unless the name already
        ends in it.
    """

    stem = name[: -len(PROJECT_SUFFIX)] if name.endswith(PROJECT_SUFFIX) else name
    return Path(directory) / f'{stem}{PROJECT_SUFFIX}'


def current_user() -> str:
    """Give the name of whoever is running the application.

    Returns
    -------
    str
        The login name, or an empty string when the platform will not say —
        which is not an error, only an author that has to be filled in later.
    """

    try:
        return getpass.getuser()
    except (KeyError, OSError):  # pragma: no cover - depends on the environment
        return ''


def manifest(name: str, author: str | None = None, company: str = '') -> dict:
    """Build the manifest of a new project.

    Parameters
    ----------
    name : str
        What the project is called.
    author : str, optional
        Who is making it, the current user by default.
    company : str, optional
        Who they are making it for, blank by default.

    Returns
    -------
    dict
        The manifest, ready to be written as JSON.

    Notes
    -----
    ``uuid`` identifies this project and nothing else.  It is generated once,
    here, and is never regenerated — a copy of a project carries the identity of
    what it was copied from, which is the whole point of having one.
    """

    return {
        'format': FORMAT_NAME,
        'format_version': FORMAT_VERSION,
        'uuid': str(uuid.uuid4()),
        'name': name,
        'author': current_user() if author is None else author,
        'company': company,
        'created': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'created_by': __version__,
    }


def lock_path(path: str | Path) -> Path:
    """Give the file that holds a project's lock.

    Beside the project rather than inside it: a lock written into the archive
    would mean rewriting the archive to take one, and a crash would leave a
    lock that cannot be cleared without opening the project it is blocking.

    Parameters
    ----------
    path : str or pathlib.Path
        The project file.

    Returns
    -------
    pathlib.Path
        The lock file, which need not exist.
    """

    target = Path(path)
    return target.with_name(f'{target.name}{LOCK_SUFFIX}')


def _alive(pid: int) -> bool:
    """Say whether a process is still running.

    Only asked on POSIX.  On Windows ``os.kill`` with signal 0 terminates the
    process rather than testing it, so a lock left behind by a crash is cleared
    by hand there — which is what the message says.

    Parameters
    ----------
    pid : int
        The process to ask about.

    Returns
    -------
    bool
        Whether it is running, and ``True`` whenever that cannot be told.
    """

    if os.name != 'posix':
        return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except OSError:
        return True
    return True


def holder_of(path: str | Path) -> dict | None:
    """Say who has a project open, if anyone.

    Parameters
    ----------
    path : str or pathlib.Path
        The project file.

    Returns
    -------
    dict, optional
        The lock's contents, or ``None`` when the project is free.
    """

    lock = lock_path(path)
    try:
        return json.loads(lock.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None


def acquire(path: str | Path) -> dict:
    """Take a project's lock, so that nothing else can open it.

    A lock left behind by a process that is no longer running is taken over
    rather than obeyed, so a crash does not make a project unopenable.

    Parameters
    ----------
    path : str or pathlib.Path
        The project file.

    Returns
    -------
    dict
        What was written into the lock.

    Raises
    ------
    ProjectLocked
        When the project is open somewhere else.
    ProjectError
        When the lock cannot be written at all.
    """

    lock = lock_path(path)
    mine = {
        'pid': os.getpid(),
        'user': current_user(),
        'host': socket.gethostname(),
        'at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
    }
    for attempt in (1, 2):
        try:
            handle = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            held = holder_of(path) or {}
            stale = held.get('host') == mine['host'] and not _alive(held.get('pid', -1))
            if stale and attempt == 1:
                lock.unlink(missing_ok=True)
                continue
            raise ProjectLocked(f'{Path(path)} is already open', held) from None
        except OSError as error:
            raise ProjectError(f'{lock} could not be written: {error}') from error
        with os.fdopen(handle, 'w', encoding='utf-8') as written:
            json.dump(mine, written)
        return mine
    raise ProjectLocked(f'{Path(path)} is already open', holder_of(path) or {})


def release(path: str | Path) -> None:
    """Give up a project's lock, if it is ours to give up.

    Parameters
    ----------
    path : str or pathlib.Path
        The project file.
    """

    held = holder_of(path)
    if held is not None and held.get('pid') == os.getpid():
        lock_path(path).unlink(missing_ok=True)


def file_name_for(name: str) -> str:
    """Give the file a model of this name is kept in.

    Spaces become underscores, as asked; anything else that has no business in
    a file name — a slash above all — goes the same way, so that a model called
    ``a/b`` cannot write outside the folder it belongs in.

    Parameters
    ----------
    name : str
        What the model is called.

    Returns
    -------
    str
        The file name, with :data:`MODEL_SUFFIX` on the end.
    """

    stem = _UNSAFE.sub('_', name.strip()).strip('_.') or 'model'
    return f'{stem}{MODEL_SUFFIX}'


def model_document(name: str, kind: ModelKind, units: dict, identifier: str) -> dict:
    """Build the contents of a new model file.

    Parameters
    ----------
    name : str
        What the model is called.
    kind : ModelKind
        What kind of model it is.
    units : dict
        The units it is expressed in, ``time`` and possibly ``distance``.
    identifier : str
        The model's UUID, which is also its entry in the manifest.

    Returns
    -------
    dict
        The document, ready to be written as JSON.

    Notes
    -----
    ``content`` is empty and its shape is still to be designed — that is the
    next piece of work.  ``format_version`` is written from the first model
    onwards so that whatever shape it takes can be recognised later.
    """

    return {
        'format': MODEL_FORMAT_NAME,
        'format_version': MODEL_FORMAT_VERSION,
        'uuid': identifier,
        'name': name,
        'kind': kind.value,
        'units': dict(units),
        'created': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'content': {},
    }


def _canonical(entry: dict) -> str:
    """Render a history entry so that hashing it is reproducible.

    Sorted keys and fixed separators, so that an entry reformatted by any tool
    still hashes to what it hashed to when it was written.  It is also exactly
    how an entry is written into the history log, one to a line.

    Parameters
    ----------
    entry : dict
        The entry.

    Returns
    -------
    str
        Its canonical JSON.
    """

    return json.dumps(entry, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def link(entry: dict, previous: str | None) -> dict:
    """Chain one history entry to the one before it.

    The identifier covers the entry *and* the identifier of the entry before,
    which in turn covers everything before that: one link deep is the whole
    history deep.  Altering or removing any entry therefore invalidates every
    entry after it, not only its own.

    Parameters
    ----------
    entry : dict
        What is being recorded.
    previous : str, optional
        The ``log_item_id`` of the entry before, ``None`` for the first.

    Returns
    -------
    dict
        The entry with ``previous`` and ``log_item_id`` added.
    """

    body = dict(entry, previous=previous)
    digest = hashlib.sha256(_canonical(body).encode('utf-8')).hexdigest()
    return dict(body, log_item_id=digest[:LOG_ITEM_ID_LENGTH])


def history_entry(
    event: str,
    project: str,
    author: str,
    install: str,
    duration: int | None = None,
    details: dict | None = None,
) -> dict:
    """Build an unchained history entry.

    The project's UUID is in every entry on purpose: a copy whose UUID has been
    regenerated then carries a history that does not belong to it, so defeating
    one of the two mechanisms means defeating both.

    Parameters
    ----------
    event : str
        One of :data:`EVENT_CREATED`, :data:`EVENT_OPENED`,
        :data:`EVENT_CLOSED`.
    project : str
        The UUID of the project this happened to.
    author : str
        Whoever was at the keyboard.
    install : str
        Which installation of the application they were using.
    duration : int, optional
        Seconds the session lasted, on a closing entry.
    details : dict, optional
        What the event was about — which model was added, and under what name.

    Returns
    -------
    dict
        The entry, ready to be chained by :func:`link`.
    """

    entry = {
        'event': event,
        'at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'project': project,
        'author': author,
        'install': install,
        'app_version': __version__,
    }
    if duration is not None:
        entry['duration'] = duration
    if details:
        entry.update(details)
    return entry


def history_text(entries: list[dict]) -> str:
    """Write a history out as the log it is kept in.

    Parameters
    ----------
    entries : list of dict
        The chained entries, oldest first.

    Returns
    -------
    str
        One canonical line per entry, each ended by a newline — so that the
        next entry is a line added at the end and nothing before it is touched.
    """

    return ''.join(f'{_canonical(entry)}\n' for entry in entries)


def _parse_history(data: bytes) -> list[dict]:
    """Read the entries out of a history log, passing over what is not one.

    A line that is not text, not JSON or not a JSON object is not an entry, and
    it is **passed over rather than refused**: a damaged log must not stop a
    project being worked on.  Nor is the line lost — the log is written back as
    it was found, with the new entries after it (see :func:`_appended`).

    Parameters
    ----------
    data : bytes
        What the log holds.

    Returns
    -------
    list of dict
        The entries that could be read, oldest first.  Blank lines are passed
        over too.
    """

    entries = []
    for line in data.splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line.decode('utf-8'))
        except (UnicodeDecodeError, ValueError):
            continue
        if isinstance(entry, dict):
            entries.append(entry)
    return entries


def _read_log(path: str | Path, content: dict) -> tuple[bytes, list[dict]]:
    """Read a project's history log as it is stored, and the entries in it.

    Parameters
    ----------
    path : str or pathlib.Path
        The project file.
    content : dict
        Its manifest, already read.

    Returns
    -------
    tuple
        The log's bytes, exactly as they are stored, and the entries that
        could be read out of them.  A project with no log gives the history its
        manifest still holds, written out as the log it will become — which is a
        project written before the history moved — or nothing at all, from which
        a new log starts.

    Raises
    ------
    ProjectError
        When the archive itself cannot be read.  A damaged *log* is not an
        error; see :func:`_parse_history`.
    """

    target = Path(path)
    try:
        with zipfile.ZipFile(target) as archive:
            if HISTORY_NAME in archive.namelist():
                data = archive.read(HISTORY_NAME)
                return data, _parse_history(data)
    except (OSError, KeyError, zipfile.BadZipFile) as error:
        raise ProjectError(f'{target} could not be read: {error}') from error

    kept = content.get('history')
    entries = [entry for entry in kept if isinstance(entry, dict)] if isinstance(kept, list) else []
    return history_text(entries).encode('utf-8'), entries


def _appended(log: bytes, entry: dict) -> bytes:
    """Put one entry at the end of a history log.

    Everything already there is kept as it is, damage and all.  A log that does
    not end in a newline — one cut off in the middle of a line — is given one
    first, so that the new entry is a line of its own rather than the tail of a
    broken one.

    Parameters
    ----------
    log : bytes
        The log as it is stored.
    entry : dict
        The chained entry to add.

    Returns
    -------
    bytes
        The log with the entry at the end.
    """

    if log and not log.endswith(b'\n'):
        log += b'\n'
    return log + history_text([entry]).encode('utf-8')


def _last_link(entries: list[dict]) -> str | None:
    """Give what the next entry of a history is chained to.

    Parameters
    ----------
    entries : list of dict
        The entries that could be read, oldest first.

    Returns
    -------
    str, optional
        The ``log_item_id`` of the last of them, or ``None`` when there are none
        and the next entry begins the chain.
    """

    return entries[-1].get('log_item_id') if entries else None


def read_history(path: str | Path) -> list[dict]:
    """Read a project's history.

    Parameters
    ----------
    path : str or pathlib.Path
        The project file.

    Returns
    -------
    list of dict
        The entries that can be read, oldest first — out of the history log, or
        out of the manifest of a project written before the log existed.  A
        damaged line is passed over here and kept in the log as it is.

    Raises
    ------
    ProjectError
        When the file is not a project.
    """

    return _read_log(path, read_manifest(path))[1]


def _directory_entry(name: str) -> zipfile.ZipInfo:
    """Build the archive entry that stands for an empty directory.

    A zip holds a flat list of names, so a directory is an entry whose name ends
    in a slash and which carries the directory bit.  Without the bit an archive
    tool shows a nought byte file rather than a folder.

    Parameters
    ----------
    name : str
        The directory's name, ending in ``/``.

    Returns
    -------
    zipfile.ZipInfo
        The entry, dated so that two projects made from the same manifest are
        byte for byte comparable.
    """

    info = zipfile.ZipInfo(name)
    info.external_attr = (0o40755 << 16) | 0x10
    return info


def create(
    path: str | Path,
    name: str,
    author: str | None = None,
    company: str = '',
    install: str = '',
) -> Path:
    """Write a new, empty project.

    The archive holds its manifest, the directories of :data:`FOLDERS` — empty
    for now, so a project opened in any archive tool shows the shape it will
    fill — and the history log, begun with the entry that says who made it.

    Parameters
    ----------
    path : str or pathlib.Path
        The file to write.
    name : str
        What the project is called, which goes into the manifest.
    author : str, optional
        Who is making it, the current user by default.
    company : str, optional
        Who they are making it for, blank by default.
    install : str, optional
        Which installation of the application is making it, for the first entry
        of the history.

    Returns
    -------
    pathlib.Path
        The file that was written.

    Raises
    ------
    ProjectError
        When the file is already there, or cannot be written.
    """

    target = Path(path)
    if target.exists():
        raise ProjectError(f'{target} is already there')

    content = manifest(name, author, company)
    history = [
        link(
            history_entry(
                EVENT_CREATED, content['uuid'], content['author'], install
            ),
            None,
        )
    ]

    try:
        with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(MANIFEST_NAME, json.dumps(content, indent=2))
            for folder in FOLDERS:
                archive.writestr(_directory_entry(folder), b'')
            archive.writestr(HISTORY_NAME, history_text(history))
    except OSError as error:
        raise ProjectError(str(error)) from error
    return target


def record(
    path: str | Path,
    event: str,
    author: str,
    install: str,
    duration: int | None = None,
) -> dict:
    """Append one entry to a project's history.

    The entry goes into the history log.  The manifest is written back as it
    was — unless it still holds a history of its own, which is then moved into
    the log with this entry at the end of it.

    Parameters
    ----------
    path : str or pathlib.Path
        The project file.
    event : str
        One of :data:`EVENT_CREATED`, :data:`EVENT_OPENED`,
        :data:`EVENT_CLOSED`.
    author : str
        Whoever was at the keyboard.
    install : str
        Which installation of the application they were using.
    duration : int, optional
        Seconds the session lasted, on a closing entry.

    Returns
    -------
    dict
        The entry that was appended, chained.

    Raises
    ------
    ProjectError
        When the project cannot be read, or cannot be written back.
    """

    content = read_manifest(path)
    log, entries = _read_log(path, content)
    entry = link(
        history_entry(event, content.get('uuid', ''), author, install, duration),
        _last_link(entries),
    )
    _rewrite_manifest(path, content, log=_appended(log, entry))
    return entry


def models_of(path: str | Path) -> list[dict]:
    """List the models a project holds.

    Parameters
    ----------
    path : str or pathlib.Path
        The project file.

    Returns
    -------
    list of dict
        The models, in the order they were added.
    """

    return read_manifest(path).get('models') or []


def _free_file_name(name: str, taken: set[str]) -> str:
    """Give a file name for a model that no other model is using.

    Two models may be called the same thing; two entries of a zip may not.

    Parameters
    ----------
    name : str
        What the model is called.
    taken : set of str
        The file names already in use.

    Returns
    -------
    str
        A file name not in ``taken``.
    """

    candidate = file_name_for(name)
    if candidate not in taken:
        return candidate
    stem = candidate[: -len(MODEL_SUFFIX)]
    number = 2
    while f'{stem}_{number}{MODEL_SUFFIX}' in taken:
        number += 1
    return f'{stem}_{number}{MODEL_SUFFIX}'


def add_model(
    path: str | Path,
    name: str,
    kind: ModelKind,
    units: dict,
    author: str = '',
    install: str = '',
) -> dict:
    """Add a model to a project, writing its file and recording it.

    Parameters
    ----------
    path : str or pathlib.Path
        The project file.
    name : str
        What the model is called.
    kind : ModelKind
        What kind of model it is.
    units : dict
        The units it is expressed in.
    author : str, optional
        Whoever is adding it, for the history.
    install : str, optional
        Which installation they are using, for the history.

    Returns
    -------
    dict
        The model's entry in the manifest.

    Raises
    ------
    ProjectError
        When the project cannot be read or written back.
    """

    content = read_manifest(path)
    log, entries = _read_log(path, content)
    models = content.get('models') or []
    model = {
        'uuid': str(uuid.uuid4()),
        'name': name,
        'kind': kind.value,
        'file': MODELS_FOLDER + _free_file_name(name, {m['file'].rpartition('/')[2] for m in models}),
        'units': dict(units),
        'created': datetime.now(timezone.utc).isoformat(timespec='seconds'),
    }
    content['models'] = [*models, model]
    entry = _record_into(entries, content, EVENT_MODEL_ADDED, author, install, model)
    _rewrite_manifest(
        path,
        content,
        log=_appended(log, entry),
        added={model['file']: json.dumps(
            model_document(name, kind, units, model['uuid']), indent=2
        )},
    )
    return model


def update_model(
    path: str | Path,
    identifier: str,
    name: str | None = None,
    units: dict | None = None,
    author: str = '',
    install: str = '',
) -> dict:
    """Change a model's name or units, leaving its kind and its file alone.

    The file keeps the name it was created with.  A model's identity is its
    UUID, and renaming the entry inside the archive on every rename would make
    a project's history harder to follow, not easier.

    Parameters
    ----------
    path : str or pathlib.Path
        The project file.
    identifier : str
        The model's UUID.
    name : str, optional
        Its new name, unchanged when omitted.
    units : dict, optional
        Its new units, unchanged when omitted.
    author : str, optional
        Whoever is changing it, for the history.
    install : str, optional
        Which installation they are using, for the history.

    Returns
    -------
    dict
        The model's entry as it now stands.

    Raises
    ------
    ProjectError
        When the project holds no such model, or cannot be written back.
    """

    content = read_manifest(path)
    log, entries = _read_log(path, content)
    models = content.get('models') or []
    model = next((m for m in models if m.get('uuid') == identifier), None)
    if model is None:
        raise ProjectError(f'{Path(path)} holds no model {identifier}')

    if name is not None:
        model['name'] = name
    if units is not None:
        model['units'] = dict(units)

    document = json.loads(_read_entry(path, model['file']))
    document['name'] = model['name']
    document['units'] = dict(model['units'])

    entry = _record_into(entries, content, EVENT_MODEL_UPDATED, author, install, model)
    _rewrite_manifest(
        path,
        content,
        log=_appended(log, entry),
        added={model['file']: json.dumps(document, indent=2)},
    )
    return model


def remove_model(
    path: str | Path, identifier: str, author: str = '', install: str = ''
) -> dict:
    """Take a model out of a project, file and all.

    Parameters
    ----------
    path : str or pathlib.Path
        The project file.
    identifier : str
        The model's UUID.
    author : str, optional
        Whoever is removing it, for the history.
    install : str, optional
        Which installation they are using, for the history.

    Returns
    -------
    dict
        The entry of the model that was removed.

    Raises
    ------
    ProjectError
        When the project holds no such model, or cannot be written back.
    """

    content = read_manifest(path)
    log, entries = _read_log(path, content)
    models = content.get('models') or []
    model = next((m for m in models if m.get('uuid') == identifier), None)
    if model is None:
        raise ProjectError(f'{Path(path)} holds no model {identifier}')

    content['models'] = [m for m in models if m.get('uuid') != identifier]
    entry = _record_into(entries, content, EVENT_MODEL_REMOVED, author, install, model)
    _rewrite_manifest(path, content, log=_appended(log, entry), dropped={model['file']})
    return model


def _record_into(
    entries: list[dict], content: dict, event: str, author: str, install: str, model: dict
) -> dict:
    """Make the chained entry about a model, for a history already in hand.

    Adding a model is one write of the archive, not two, so the entry is made
    here and written with the model rather than through :func:`record`.

    Parameters
    ----------
    entries : list of dict
        The entries of the history that could be read, which the new one is
        chained after.
    content : dict
        The manifest, for the project's UUID.
    event : str
        What happened.
    author : str
        Whoever it was.
    install : str
        Which installation they were using.
    model : dict
        The model the event is about.

    Returns
    -------
    dict
        The entry, chained, to be put at the end of the log.
    """

    return link(
        history_entry(
            event,
            content.get('uuid', ''),
            author,
            install,
            details={'model': model['uuid'], 'model_name': model['name']},
        ),
        _last_link(entries),
    )


def _read_entry(path: str | Path, name: str) -> bytes:
    """Read one entry out of a project archive.

    Parameters
    ----------
    path : str or pathlib.Path
        The project file.
    name : str
        The entry to read.

    Returns
    -------
    bytes
        Its contents.

    Raises
    ------
    ProjectError
        When the entry is not there.
    """

    try:
        with zipfile.ZipFile(Path(path)) as archive:
            return archive.read(name)
    except (OSError, KeyError, zipfile.BadZipFile) as error:
        raise ProjectError(f'{Path(path)} has no {name}: {error}') from error


def _rewrite_manifest(
    path: str | Path,
    content: dict,
    added: dict[str, str | bytes] | None = None,
    dropped: set[str] | None = None,
    log: bytes | None = None,
) -> None:
    """Write a project back with a new manifest, its history, and files added or
    removed.

    A zip entry cannot be replaced where it lies, so the archive is written
    afresh beside the original and moved over it.  The move is what makes this
    safe: an interrupted write leaves the original project untouched rather
    than half of a new one.  Everything not named in ``added`` or ``dropped``
    is carried across as it was.

    **Every write leaves the project in the current format.**  A manifest still
    holding a history of its own — a project written before the history moved —
    loses it here, and the history goes into the log instead: the one given, or
    the manifest's own when none is.  The version is raised to
    :data:`FORMAT_VERSION` at the same time, and never lowered, so a project
    from a later version of the application is not marked as an older one.

    Parameters
    ----------
    path : str or pathlib.Path
        The project file.
    content : dict
        The manifest to write in place of the one that is there.  It is not
        changed; what is written is a copy.
    added : dict, optional
        Entries to write, by name; an entry already there is replaced.
    dropped : set of str, optional
        Entries to leave out.
    log : bytes, optional
        The history log to write, exactly as it is to be stored.

    Raises
    ------
    ProjectError
        When the project cannot be written back.
    """

    added = dict(added or {})
    dropped = set(dropped or ())
    content = dict(content)
    kept = content.pop('history', None)
    if log is None and isinstance(kept, list):
        log = history_text([entry for entry in kept if isinstance(entry, dict)]).encode('utf-8')
    if log is not None:
        added[HISTORY_NAME] = log
    version = content.get('format_version')
    if not isinstance(version, int) or version < FORMAT_VERSION:
        content['format_version'] = FORMAT_VERSION
    target = Path(path)
    beside = target.with_name(f'{target.name}.writing')
    try:
        with zipfile.ZipFile(target) as source:
            entries = [
                (info, b'' if info.is_dir() else source.read(info.filename))
                for info in source.infolist()
                if info.filename not in dropped
            ]
        with zipfile.ZipFile(beside, 'w', zipfile.ZIP_DEFLATED) as written:
            for info, data in entries:
                if info.filename == MANIFEST_NAME:
                    written.writestr(info, json.dumps(content, indent=2))
                elif info.filename in added:
                    written.writestr(info, added.pop(info.filename))
                else:
                    written.writestr(info, data)
            for name, data in added.items():
                written.writestr(name, data)
        os.replace(beside, target)
    except (OSError, zipfile.BadZipFile) as error:
        beside.unlink(missing_ok=True)
        raise ProjectError(f'{target} could not be written: {error}') from error


def read_manifest(path: str | Path) -> dict:
    """Read the manifest of a project.

    Parameters
    ----------
    path : str or pathlib.Path
        The project file.

    Returns
    -------
    dict
        What the manifest holds.

    Raises
    ------
    ProjectError
        When the file is not a zip, holds no manifest, holds one that is not
        JSON, or holds one that says it is something else.
    """

    target = Path(path)
    try:
        with zipfile.ZipFile(target) as archive:
            content = archive.read(MANIFEST_NAME)
    except (OSError, KeyError, zipfile.BadZipFile) as error:
        raise ProjectError(f'{target} is not a project file: {error}') from error

    try:
        found = json.loads(content)
    except json.JSONDecodeError as error:
        raise ProjectError(f'{target} has an unreadable manifest: {error}') from error

    if not isinstance(found, dict) or found.get('format') != FORMAT_NAME:
        raise ProjectError(f'{target} is not a project file')
    return found


def label_for(path: str | Path) -> str:
    """Give the name to show for a project in a list of them.

    Parameters
    ----------
    path : str or pathlib.Path
        The project file.

    Returns
    -------
    str
        The name in the manifest, falling back to the file's own stem when the
        manifest cannot be read.  A file that is there but unreadable keeps its
        place in a history — it is a broken project rather than a missing one,
        and opening it is what reports why.
    """

    try:
        return name_of(path)
    except ProjectError:
        return Path(path).stem


def labels_for(paths: list[str]) -> list[tuple[str, str]]:
    """Name every project of a list, telling apart the ones that share a name.

    Two projects of the same name in different places would otherwise be one
    entry repeated, so those — and only those — carry their path after the name.

    Parameters
    ----------
    paths : list of str
        The project files, in the order they are to be shown.

    Returns
    -------
    list of tuple of str
        A ``(label, path)`` pair for each, in the order given.
    """

    names = [label_for(path) for path in paths]
    repeated = {name for name in names if names.count(name) > 1}
    return [
        (f'{name} ({path})' if name in repeated else name, path)
        for name, path in zip(names, paths)
    ]


def name_of(path: str | Path) -> str:
    """Give the name a project goes by.

    Parameters
    ----------
    path : str or pathlib.Path
        The project file.

    Returns
    -------
    str
        The name in the manifest, falling back to the file's own stem when the
        manifest does not carry one.
    """

    return read_manifest(path).get('name') or Path(path).stem
