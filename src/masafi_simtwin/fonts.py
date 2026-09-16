"""The fonts this machine has, and the one a net is lettered in by default.

This is to lettering what :mod:`~masafi_simtwin.paper` is to paper: a question
put to the machine, asked through Qt so that it is the same question on every
desktop, and kept once it has been answered.
:mod:`~masafi_simtwin.preferences` is what stores a choice; this module only
says what there is to choose from and what to fall back on.

**Asking whether a font is installed is not the obvious call.**  The obvious
one — whether the family is among :meth:`~PyQt6.QtGui.QFontDatabase.families` —
answers *no* for fonts that are installed and draw perfectly well: on the
machine this was written on, ``Nimbus Sans`` is absent from that list, and
:meth:`~PyQt6.QtGui.QFont.exactMatch` is false for it as well, yet Qt letters in
it correctly when asked.  What is reliable is what Qt says it would *actually*
use: :class:`~PyQt6.QtGui.QFontInfo` resolves ``Nimbus Sans`` to
``Nimbus Sans [UKWN]`` — the family, with the foundry Qt sometimes adds — and
resolves a family nobody has to something else entirely.  So a font is installed
when what Qt would letter in is the family that was asked for, the foundry
dropped and the case folded.

The fallback is **silent**, as agreed: a net drawn on a machine with a font this
one lacks opens here lettered in the default, rather than refusing to open or
saying so every time it is drawn.
"""

from __future__ import annotations

from PyQt6.QtGui import QFont, QFontInfo

#: The family a net is lettered in wherever the machine has it — a grotesque
#: that is metrically one of the usual ones and is installed with the standard
#: PostScript fonts on most Linux machines.  A machine without it letters a net
#: in whatever it letters everything else in.
PREFERRED_FONT = 'Nimbus Sans'

#: What has been worked out already, so that a font is resolved once rather than
#: at every repaint of every caption.
_families: dict[str, bool] = {}
_default: str = ''


def _resolved(family: str) -> str:
    """Give the family Qt would actually letter in when asked for this one.

    Parameters
    ----------
    family : str
        The family asked for.

    Returns
    -------
    str
        What Qt would use, which is the family itself — possibly with a foundry
        after it — when the machine has it, and something else when it has not.
    """

    return QFontInfo(QFont(family)).family()


def _plain(family: str) -> str:
    """Reduce a family name to what two spellings of one font have in common.

    Parameters
    ----------
    family : str
        A family name, with or without the foundry Qt puts after it.

    Returns
    -------
    str
        The name alone, folded for case.
    """

    return family.split('[')[0].strip().casefold()


def installed(family: str) -> bool:
    """Say whether this machine can letter in a family.

    Parameters
    ----------
    family : str
        The family to ask about.  Nothing at all is not a font: an empty name
        resolves to whichever family Qt happens to start from, which would
        answer *yes* to a question nobody asked.

    Returns
    -------
    bool
        Whether Qt would letter in that family rather than in something else.
    """

    if not isinstance(family, str) or not family.strip():
        return False
    name = family.strip()
    if name not in _families:
        _families[name] = _plain(_resolved(name)) == _plain(name)
    return _families[name]


def default_family() -> str:
    """Give the family a net is lettered in when nobody has chosen one.

    Returns
    -------
    str
        :data:`PREFERRED_FONT` where this machine has it, and the font the
        application itself letters in otherwise — which is never nothing, so
        there is always something to draw with.
    """

    global _default

    if not _default:
        _default = (
            PREFERRED_FONT if installed(PREFERRED_FONT) else QFontInfo(QFont()).family()
        )
    return _default


def forget() -> None:
    """Ask the machine again next time, rather than repeating what it said.

    The fonts of a machine can change while the application is running, and a
    test needs to be able to put a different machine in front of the same
    functions.
    """

    global _default

    _families.clear()
    _default = ''
