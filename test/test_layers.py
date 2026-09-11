"""Tests for the three layers of ``src/`` and the one hard rule between them.

The GUI programs against ``simtwin_core``, and an adapter under
``simtwin_adapters`` is the only place a backend library is named.  A rule about
which package may import which cannot be seen by running the application — a
forbidden import works perfectly well until the seam it crossed is needed — so it
is held here by reading the imports of every module, the way ``test_project``
holds that the project file knows nothing of Qt.

This module sits at the top of the test tree because it is about ``src/`` as a
whole rather than about any one package in it.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

#: The source root the three layers sit in.
SRC = Path(__file__).resolve().parent.parent / 'src'

#: What the GUI must never import: the backend libraries, and the event
#: scheduler they run on.
BACKENDS = ('masafi_sim_petri', 'simpy')

#: What the protocol must never import: Qt in any of its guises, a backend, or
#: either of the layers on each side of it.
NOT_IN_CORE = (
    'PyQt6',
    'qtpy',
    'qt_material_icons',
    'masafi_simtwin',
    'simtwin_adapters',
    *BACKENDS,
)


def modules_of(package: str) -> list[Path]:
    """List every module of a package under ``src/``.

    Parameters
    ----------
    package : str
        The package's directory name.

    Returns
    -------
    list of pathlib.Path
        Its ``.py`` files, sub-packages included, in a stable order.
    """

    return sorted((SRC / package).rglob('*.py'))


def imported_by(path: Path) -> set[str]:
    """Give the top-level names of everything a module imports.

    Every import statement counts wherever it stands — at the top, inside a
    function, behind ``TYPE_CHECKING`` — because a backend imported lazily is a
    backend imported all the same.  A relative import stays inside its own
    package and is not counted.  An import made by name at run time, through
    ``importlib``, is not seen; nothing in ``src/`` makes one.

    Parameters
    ----------
    path : pathlib.Path
        The module.

    Returns
    -------
    set of str
        The first component of every absolute import.
    """

    tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name.partition('.')[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            found.add(node.module.partition('.')[0])
    return found


def offending(package: str, forbidden: tuple[str, ...]) -> list[str]:
    """Say which modules of a package import something they must not.

    Parameters
    ----------
    package : str
        The package's directory name.
    forbidden : tuple of str
        The top-level names it may not import.

    Returns
    -------
    list of str
        One line per module and name, which is what a failure prints.
    """

    return [
        f'{path.relative_to(SRC)} imports {name}'
        for path in modules_of(package)
        for name in sorted(imported_by(path) & set(forbidden))
    ]


def test_an_import_is_found_wherever_it_stands(tmp_path):
    """A lazy import inside a function is still an import, and a relative one
    is not a backend."""

    module = tmp_path / 'lazy.py'
    module.write_text(
        'import os\n'
        '\n'
        'def run():\n'
        '    from simpy.core import Environment\n'
        '    import masafi_sim_petri.io as io\n'
        '    from . import sibling\n',
        encoding='utf-8',
    )

    assert imported_by(module) == {'os', 'simpy', 'masafi_sim_petri'}


def test_the_rule_reads_the_gui_it_is_about():
    """A path gone wrong would make every rule below pass by reading nothing."""

    assert (SRC / 'masafi_simtwin' / 'main_window.py') in modules_of('masafi_simtwin')


def test_the_gui_never_names_a_backend():
    """Nothing under ``src/masafi_simtwin/`` imports a MASAFI library or SimPy;
    that is what an adapter is for."""

    assert offending('masafi_simtwin', BACKENDS) == []


def test_the_protocol_knows_no_qt_and_no_backend():
    """``simtwin_core`` stands between the two, so it imports neither, nor Qt."""

    if not (SRC / 'simtwin_core').is_dir():
        pytest.skip('simtwin_core does not exist yet')

    assert offending('simtwin_core', NOT_IN_CORE) == []
