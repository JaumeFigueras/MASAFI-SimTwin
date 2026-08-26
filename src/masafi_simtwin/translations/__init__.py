"""Translation catalogues and the language list of the application.

The directory is a package so that the compiled ``.qm`` files can be reached
through :mod:`importlib.resources`, whether the application runs from ``src/``
or from an installed wheel.

English is the source language: the literals passed to ``tr()`` in the code are
the English text, so ``masafi_simtwin_en.ts`` repeats every source string as its
own translation.  It is filled mechanically by ``tools/update_translations.py``
and is never edited by hand; it exists so that English can be chosen explicitly
and so that the catalogues can be checked the same way in every language.
"""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path

#: The language the source strings are written in.
SOURCE_LANGUAGE = 'en'

#: Every language the application is translated into, source language first.
LANGUAGES = ('en', 'ca')

#: Endonym of each language, for a language chooser.
LANGUAGE_NAMES = {'en': 'English', 'ca': 'Català'}

#: Stem shared by every catalogue; the language follows after ``_``.
CATALOGUE_PREFIX = 'masafi_simtwin'


def directory() -> Path:
    """Return the directory the catalogues live in.

    Returns
    -------
    pathlib.Path
        The directory of this package.
    """

    return Path(str(files(__name__)))


def catalogue(language: str, suffix: str = '.qm') -> Path:
    """Return the path of one catalogue, whether or not it exists.

    Parameters
    ----------
    language : str
        Language code, as in :data:`LANGUAGES`.
    suffix : str, optional
        ``'.qm'`` for the compiled catalogue, ``'.ts'`` for the source.

    Returns
    -------
    pathlib.Path
        Path of the catalogue.
    """

    return directory() / f'{CATALOGUE_PREFIX}_{language}{suffix}'
