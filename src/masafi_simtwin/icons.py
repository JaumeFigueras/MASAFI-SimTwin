"""Material Symbols icons that follow the active theme.

``qt-material-icons`` renders an SVG symbol and tints it with the *current*
application palette at the moment the icon is built.  An icon built under the
light theme therefore stays dark grey after the desktop switches to dark.  The
functions here work around that: every icon handed to a widget through
:func:`set_icon` is remembered, and :func:`refresh` rebuilds the lot once the
palette has changed.

Note
----
``qt-material-icons`` reaches for its Qt binding through ``qtpy``, which probes
the installed bindings in order.  Only PyQt6 is a dependency of this project, so
the choice is pinned here before the package is imported rather than left to the
probe.
"""

from __future__ import annotations

import os
import weakref
from typing import Protocol, runtime_checkable

os.environ.setdefault('QT_API', 'pyqt6')

from PyQt6.QtGui import QIcon  # noqa: E402  (import after QT_API is pinned)
from qt_material_icons import MaterialIcon  # noqa: E402

#: Nominal size, in pixels, of the icons drawn in the window chrome.
CHROME_ICON_SIZE = 20

#: The SVG sizes ``qt-material-icons`` ships a resource bundle for.  Asking for
#: any other size fails at import time inside the package, so it is caught here
#: instead.  A widget that needs a size in between takes the next one up and
#: scales it down through ``setIconSize``.
AVAILABLE_SIZES = (20, 24, 40, 48)


@runtime_checkable
class IconTarget(Protocol):
    """Anything that can be given an icon — a ``QAction`` or a ``QAbstractButton``."""

    def setIcon(self, icon: QIcon) -> None:  # noqa: N802  (Qt naming)
        """Set the icon of the target.

        Parameters
        ----------
        icon : PyQt6.QtGui.QIcon
            The icon to display.
        """


_registry: list[tuple[weakref.ReferenceType[IconTarget], str, MaterialIcon.Style, bool, int]] = []


def icon(
    name: str,
    *,
    style: MaterialIcon.Style = MaterialIcon.OUTLINED,
    fill: bool = False,
    size: int = CHROME_ICON_SIZE,
) -> MaterialIcon:
    """Build one Material Symbols icon tinted with the current palette.

    Parameters
    ----------
    name : str
        Name of the Material Symbol, such as ``'play_arrow'``.
    style : qt_material_icons.MaterialIcon.Style, optional
        Symbol style, outlined by default.
    fill : bool, optional
        Whether to use the filled variant of the symbol, by default ``False``.
    size : int, optional
        Nominal size of the underlying SVG, by default :data:`CHROME_ICON_SIZE`.
        It must be one of :data:`AVAILABLE_SIZES`.

    Returns
    -------
    qt_material_icons.MaterialIcon
        The icon.  It is *not* registered for refreshing; use :func:`set_icon`
        for anything that has to survive a theme change.

    Raises
    ------
    ValueError
        If ``size`` is not one of :data:`AVAILABLE_SIZES`.
    """

    if size not in AVAILABLE_SIZES:
        raise ValueError(
            f'no Material Symbols bundle for size {size}; '
            f'available sizes are {AVAILABLE_SIZES}'
        )
    return MaterialIcon(name, style=style, fill=fill, size=size)


def set_icon(
    target: IconTarget,
    name: str,
    *,
    style: MaterialIcon.Style = MaterialIcon.OUTLINED,
    fill: bool = False,
    size: int = CHROME_ICON_SIZE,
) -> None:
    """Give a widget or an action an icon that follows the theme.

    Parameters
    ----------
    target : IconTarget
        The action or button to set the icon on.  It is held weakly, so
        registering it here does not keep it alive.
    name : str
        Name of the Material Symbol.
    style : qt_material_icons.MaterialIcon.Style, optional
        Symbol style, outlined by default.
    fill : bool, optional
        Whether to use the filled variant of the symbol, by default ``False``.
    size : int, optional
        Nominal size of the underlying SVG, by default :data:`CHROME_ICON_SIZE`.
    """

    target.setIcon(icon(name, style=style, fill=fill, size=size))
    _registry.append((weakref.ref(target), name, style, fill, size))


def refresh() -> None:
    """Rebuild every registered icon against the palette in force now.

    Targets that have been destroyed are dropped from the registry as they are
    found, which is what keeps it from growing without bound as tabs and panes
    come and go.
    """

    survivors = []
    for reference, name, style, fill, size in _registry:
        target = reference()
        if target is None:
            continue
        try:
            target.setIcon(icon(name, style=style, fill=fill, size=size))
        except RuntimeError:
            #  The C++ side is gone even though Python still holds the wrapper.
            continue
        survivors.append((reference, name, style, fill, size))

    _registry[:] = survivors
