"""The project file: what a ``.mfstz`` is, and how one is made and recognised.

A project is a single file rather than a directory, so that it can be copied,
sent and versioned as one thing.  The suffix is :data:`PROJECT_SUFFIX` —
*mfstz*, near enough to *manifest*, with the ``z`` for the zip it is.  Inside is
an ordinary zip archive holding :data:`MANIFEST_NAME` and, in time, everything
else a project is made of: the flow model, the sub-models, the block library it
was built against.

**There is nothing but the manifest in there yet**, and the manifest holds only
what cannot be added afterwards: which format this is and which version of it.
Everything else about the contents is still to be designed, which is exactly why
:data:`FORMAT_VERSION` is written from the first file onwards.

This module has no Qt in it, on purpose.  It is stdlib only — ``zipfile`` and
``json`` — so that it can move to :mod:`simtwin_core` unchanged once that
package exists, which is where a document format belongs.
"""

from __future__ import annotations

import json
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
FORMAT_VERSION = 1


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


def manifest(name: str) -> dict:
    """Build the manifest of a new project.

    Parameters
    ----------
    name : str
        What the project is called.

    Returns
    -------
    dict
        The manifest, ready to be written as JSON.
    """

    return {
        'format': FORMAT_NAME,
        'format_version': FORMAT_VERSION,
        'name': name,
        'created': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'created_by': __version__,
    }


def create(path: str | Path, name: str) -> Path:
    """Write a new, empty project.

    Parameters
    ----------
    path : str or pathlib.Path
        The file to write.
    name : str
        What the project is called, which goes into the manifest.

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
    try:
        with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(MANIFEST_NAME, json.dumps(manifest(name), indent=2))
    except OSError as error:
        raise ProjectError(str(error)) from error
    return target


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
