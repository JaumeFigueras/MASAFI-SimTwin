"""Compile the Qt Designer forms into the modules the dialogs inherit from.

Every ``.ui`` under ``src/masafi_simtwin`` is compiled by ``pyuic6`` into a
``ui_<name>.py`` beside it.  Both the form and the module it generates are
committed, the same arrangement the translation catalogues already use: the
``.ui`` is what a human edits in Qt Designer, the ``ui_*.py`` is what PyCharm
and the interpreter read.

``--check``
    Compile every form to a temporary file and compare it with what is on
    disk, without writing anything.  This is what the test suite runs, so that
    a form saved in Designer without a following ``make ui`` fails the build
    instead of quietly having no effect.

``pyuic6`` writes the path it was given into the header of the module it
generates, so the forms are always compiled from the root of the repository
through a relative path; otherwise the generated file would differ depending
on where the tool was run from and ``--check`` would never agree.

Examples
--------
::

    python tools/build_forms.py            # compile every form
    python tools/build_forms.py --check    # only report the stale ones
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT / 'tools'))

from update_translations import find_tool  # noqa: E402  (needs the path above)

#: The package the forms are looked for in.
SOURCES = ROOT / 'src' / 'masafi_simtwin'

#: What to tell the user when ``pyuic6`` is missing.
PYUIC_HINT = (
    'It ships with PyQt6; install the requirements with `make install`, or '
    'point $PYUIC6 at it.'
)

#: What to tell the user when Qt Designer is missing.
DESIGNER_HINT = (
    'On Debian, install it with `sudo apt install designer-qt6`, or point '
    '$DESIGNER at it.'
)

#: Where Qt Designer is looked for when it is not on the ``PATH``.
DESIGNER_DIRECTORIES = (
    Path('/usr/lib/qt6/bin'),
    Path('/usr/lib/x86_64-linux-gnu/qt6/bin'),
    Path('/usr/lib64/qt6/bin'),
)


def forms() -> list[Path]:
    """List every Qt Designer form of the application.

    Returns
    -------
    list of pathlib.Path
        The ``.ui`` files under :data:`SOURCES`, in a stable order.
    """

    return sorted(SOURCES.rglob('*.ui'))


def generated(form: Path) -> Path:
    """Give the module a form is compiled into.

    Parameters
    ----------
    form : pathlib.Path
        Path of the ``.ui`` file.

    Returns
    -------
    pathlib.Path
        Path of the ``ui_*.py`` module beside it.
    """

    return form.with_name(f'ui_{form.stem}.py')


def compile_form(form: Path, target: Path, pyuic: Path) -> None:
    """Run ``pyuic6`` over one form.

    Parameters
    ----------
    form : pathlib.Path
        Path of the ``.ui`` file.
    target : pathlib.Path
        Where to write the generated module.
    pyuic : pathlib.Path
        The ``pyuic6`` executable.
    """

    subprocess.run(
        [str(pyuic), str(form.relative_to(ROOT)), '-o', str(target)],
        check=True,
        cwd=ROOT,
    )


def build() -> int:
    """Compile every form, overwriting the modules on disk.

    Returns
    -------
    int
        Zero, so the caller can use it as an exit status.
    """

    pyuic = find_tool('pyuic6', hint=PYUIC_HINT)
    for form in forms():
        target = generated(form)
        compile_form(form, target, pyuic)
        print(f'{form.relative_to(ROOT)} -> {target.relative_to(ROOT)}')
    return 0


def check() -> int:
    """Report the forms whose generated module is missing or out of date.

    Returns
    -------
    int
        Zero when every module is in step with its form, one otherwise.
    """

    pyuic = find_tool('pyuic6', hint=PYUIC_HINT)
    stale = [form for form in forms() if not is_current(form, pyuic)]
    for form in stale:
        print(f'stale: {form.relative_to(ROOT)}', file=sys.stderr)
    if stale:
        print('Run `make ui`.', file=sys.stderr)
        return 1
    return 0


def is_current(form: Path, pyuic: Path) -> bool:
    """Say whether the module generated from a form is what is on disk.

    Parameters
    ----------
    form : pathlib.Path
        Path of the ``.ui`` file.
    pyuic : pathlib.Path
        The ``pyuic6`` executable.

    Returns
    -------
    bool
        True when the module beside the form is exactly what compiling it now
        would produce.
    """

    target = generated(form)
    if not target.exists():
        return False
    with tempfile.TemporaryDirectory() as directory:
        fresh = Path(directory) / target.name
        compile_form(form, fresh, pyuic)
        return fresh.read_text(encoding='utf-8') == target.read_text(encoding='utf-8')


def designer(name: str) -> int:
    """Open a form in Qt Designer.

    Parameters
    ----------
    name : str
        Stem of the form, ``about`` for ``about.ui``.  A path to a ``.ui`` file
        is taken as it is.

    Returns
    -------
    int
        Zero once Designer has been started.

    Raises
    ------
    SystemExit
        When no form goes by that name.
    """

    candidates = [form for form in forms() if name in (form.stem, str(form))]
    if not candidates:
        known = ', '.join(form.stem for form in forms()) or 'none'
        raise SystemExit(f'No form called {name!r}.  Known forms: {known}.')
    tool = find_tool('designer', DESIGNER_DIRECTORIES, hint=DESIGNER_HINT)
    subprocess.Popen([str(tool), str(candidates[0])])
    return 0


def main(argv: list[str] | None = None) -> int:
    """Run the tool.

    Parameters
    ----------
    argv : list of str, optional
        Command line arguments, ``sys.argv`` by default.

    Returns
    -------
    int
        Exit status.
    """

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        '--check',
        action='store_true',
        help='report the stale modules instead of rewriting them',
    )
    parser.add_argument(
        '--designer',
        metavar='FORM',
        help='open a form in Qt Designer, by stem or by path',
    )
    arguments = parser.parse_args(argv)

    if arguments.designer:
        return designer(arguments.designer)
    return check() if arguments.check else build()


if __name__ == '__main__':
    raise SystemExit(main())
