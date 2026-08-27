"""Keep the translation catalogues in step with the sources.

Two steps, either of which can be run on its own:

``--update``
    Run ``pylupdate6`` over ``src/masafi_simtwin`` for every language, then
    stamp the language attributes Qt Linguist expects and fill the source
    language catalogue with its own source strings.

``--release``
    Run ``lrelease`` over every ``.ts`` file to produce the ``.qm`` files the
    application loads.

``lrelease`` is not on the ``PATH`` on Debian; it is looked for in the usual Qt
6 directories, and ``$LRELEASE`` overrides the search.

Examples
--------
::

    python tools/update_translations.py            # both steps
    python tools/update_translations.py --update   # extract only
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT / 'src'))

from masafi_simtwin.translations import (  # noqa: E402  (needs the path above)
    LANGUAGES,
    SOURCE_LANGUAGE,
    catalogue,
)

#: The package the strings are extracted from.
SOURCES = ROOT / 'src' / 'masafi_simtwin'

#: Where ``lrelease`` is looked for when it is not on the ``PATH``.
LRELEASE_DIRECTORIES = (
    Path('/usr/lib/qt6/bin'),
    Path('/usr/lib/x86_64-linux-gnu/qt6/bin'),
    Path('/usr/lib64/qt6/bin'),
)

#: Locale written into the catalogues, so Linguist knows the plural rules.
LOCALES = {'en': 'en_US', 'ca': 'ca_ES'}


def find_tool(name: str, directories: tuple[Path, ...] = (), hint: str = '') -> Path:
    """Locate one of the Qt Linguist tools.

    Parameters
    ----------
    name : str
        Name of the executable.
    directories : tuple of pathlib.Path, optional
        Directories to look in besides the virtualenv and the ``PATH``.  The
        environment variable named after the tool, ``$LRELEASE``, wins over
        the search.
    hint : str, optional
        What to tell the user when the tool is missing, appended to the error.

    Returns
    -------
    pathlib.Path
        Path of the executable.

    Raises
    ------
    SystemExit
        When the tool is nowhere to be found.
    """

    override = os.environ.get(name.upper())
    if override:
        return Path(override)
    for directory in (Path(sys.executable).parent, *directories):
        candidate = directory / name
        if candidate.exists():
            return candidate
    found = shutil.which(name)
    if found:
        return Path(found)
    advice = hint or (
        'On Debian, install it with `sudo apt install qt6-l10n-tools`, or point '
        f'${name.upper()} at it.'
    )
    raise SystemExit(f'{name} was not found.  {advice}')


def update(language: str, pylupdate: Path) -> None:
    """Extract the source strings into the catalogue of one language.

    Parameters
    ----------
    language : str
        Language code.
    pylupdate : pathlib.Path
        The ``pylupdate6`` executable.

    Notes
    -----
    Obsolete messages are dropped rather than kept: the catalogues mirror the
    strings the code has now, which is what the tests marked ``i18n`` check.
    The cost is that renaming a string loses its translation, so rename with
    Linguist open if the translation is worth keeping.
    """

    target = catalogue(language, '.ts')
    subprocess.run(
        [str(pylupdate), '--no-obsolete', '--ts', str(target), str(SOURCES)],
        check=True,
    )
    stamp(target, language)
    if language == SOURCE_LANGUAGE:
        fill_from_source(target)


def stamp(path: Path, language: str) -> None:
    """Write the language attributes into a catalogue.

    ``pylupdate6`` leaves them out, and without them Qt Linguist asks for the
    language every time the file is opened.

    Parameters
    ----------
    path : pathlib.Path
        The ``.ts`` file.
    language : str
        Language code.
    """

    text = path.read_text(encoding='utf-8')
    header = re.search(r'<TS\b[^>]*>', text)
    if header is None:
        raise SystemExit(f'{path} does not look like a catalogue')
    version = re.search(r'version="([^"]*)"', header.group(0))
    attributes = f'version="{version.group(1)}"' if version else ''
    path.write_text(
        text.replace(
            header.group(0),
            f'<TS {attributes} language="{LOCALES.get(language, language)}" '
            f'sourcelanguage="{LOCALES[SOURCE_LANGUAGE]}">',
            1,
        ),
        encoding='utf-8',
    )


def fill_from_source(path: Path) -> None:
    """Translate a catalogue into its own source language.

    Every message of the source language catalogue is its own translation, so
    the file is generated rather than typed.  The source text is copied across
    exactly as it is written in the file, which keeps it escaped as XML.

    Parameters
    ----------
    path : pathlib.Path
        The ``.ts`` file of the source language.

    Notes
    -----
    Messages with plural forms are left alone: which forms a language needs is
    not something this can decide.
    """

    def translate(match: re.Match[str]) -> str:
        message = match.group(0)
        if '<numerusform' in message:
            return message
        source = re.search(r'<source>(.*?)</source>', message, re.DOTALL)
        if source is None:
            return message
        return re.sub(
            r'<translation\b[^>]*?(?:/>|>.*?</translation>)',
            f'<translation>{source.group(1)}</translation>',
            message,
            count=1,
            flags=re.DOTALL,
        )

    text = path.read_text(encoding='utf-8')
    path.write_text(
        re.sub(r'<message\b.*?</message>', translate, text, flags=re.DOTALL), encoding='utf-8'
    )


def release(language: str, lrelease: Path) -> None:
    """Compile the catalogue of one language.

    Parameters
    ----------
    language : str
        Language code.
    lrelease : pathlib.Path
        The ``lrelease`` executable.
    """

    subprocess.run(
        [
            str(lrelease),
            str(catalogue(language, '.ts')),
            '-qm',
            str(catalogue(language, '.qm')),
        ],
        check=True,
    )


def main(argv: list[str] | None = None) -> int:
    """Run the steps asked for on the command line.

    Parameters
    ----------
    argv : list of str, optional
        Arguments, ``sys.argv[1:]`` by default.

    Returns
    -------
    int
        ``0`` on success.
    """

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--update', action='store_true', help='extract the source strings')
    parser.add_argument('--release', action='store_true', help='compile the catalogues')
    parser.add_argument(
        '--language',
        action='append',
        choices=LANGUAGES,
        help='only this language; repeatable, every language by default',
    )
    arguments = parser.parse_args(argv)

    steps = (arguments.update, arguments.release)
    if not any(steps):
        steps = (True, True)
    languages = arguments.language or list(LANGUAGES)

    if steps[0]:
        pylupdate = find_tool('pylupdate6')
        for language in languages:
            update(language, pylupdate)
    if steps[1]:
        lrelease = find_tool('lrelease', LRELEASE_DIRECTORIES)
        for language in languages:
            release(language, lrelease)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
