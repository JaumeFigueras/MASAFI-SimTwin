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

This module has no Qt in it, on purpose.  It is stdlib only — ``zipfile`` and
``json`` — so that it can move to :mod:`simtwin_core` unchanged once that
package exists, which is where a document format belongs.
"""

from __future__ import annotations

import getpass
import hashlib
import json
import os
import uuid
import zipfile
from datetime import datetime, timezone
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
FORMAT_VERSION = 2

#: The directories every project carries, whether or not anything is in them
#: yet.  A zip has no directories of its own; these are the empty entries that
#: make one show a project's shape when it is opened with any archive tool.
FOLDERS: tuple[str, ...] = ('models/', 'simulations/', 'statistics/', 'logs/')

#: The events a project's history records.  A session is a pair: one entry when
#: the project is opened, one when it is closed, so that a run that ends in a
#: crash still leaves the opening behind.
EVENT_CREATED = 'created'
EVENT_OPENED = 'opened'
EVENT_CLOSED = 'closed'

#: How many characters of the digest a ``log_item_id`` keeps.  Far more than is
#: forgeable by hand, and short enough to read out over a desk.
LOG_ITEM_ID_LENGTH = 16


class ProjectError(Exception):
    """Raised when a file is not a project, or cannot be made into one."""


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


def _canonical(entry: dict) -> str:
    """Render a history entry so that hashing it is reproducible.

    Sorted keys and fixed separators, so that a manifest reformatted by any
    tool still hashes to what it hashed to when it was written.

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
    return entry


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

    The archive holds its manifest and the directories of :data:`FOLDERS`, empty
    for now: a project opened in any archive tool shows the shape it will fill
    rather than a single file.

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
    content['history'] = [
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
    history = content.get('history') or []
    previous = history[-1].get('log_item_id') if history else None
    entry = link(
        history_entry(event, content.get('uuid', ''), author, install, duration),
        previous,
    )
    content['history'] = [*history, entry]
    _rewrite_manifest(path, content)
    return entry


def _rewrite_manifest(path: str | Path, content: dict) -> None:
    """Put a manifest back into a project, leaving everything else alone.

    A zip entry cannot be replaced where it lies, so the archive is written
    afresh beside the original and moved over it.  The move is what makes this
    safe: an interrupted write leaves the original project untouched rather
    than half of a new one.

    Parameters
    ----------
    path : str or pathlib.Path
        The project file.
    content : dict
        The manifest to write in place of the one that is there.

    Raises
    ------
    ProjectError
        When the project cannot be written back.
    """

    target = Path(path)
    beside = target.with_name(f'{target.name}.writing')
    try:
        with zipfile.ZipFile(target) as source:
            entries = [
                (info, b'' if info.is_dir() else source.read(info.filename))
                for info in source.infolist()
            ]
        with zipfile.ZipFile(beside, 'w', zipfile.ZIP_DEFLATED) as written:
            for info, data in entries:
                if info.filename == MANIFEST_NAME:
                    written.writestr(info, json.dumps(content, indent=2))
                else:
                    written.writestr(info, data)
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
