"""The paper a sheet is ruled into: what sizes there are, and which is default.

Paper is a thing the operating system knows about, and Qt knows how to ask it:
:class:`~PyQt6.QtGui.QPageSize` holds the standard sizes and their dimensions,
and :class:`~PyQt6.QtPrintSupport.QPrinterInfo` says which of them the machine's
printers take and which one they take by default.  Both are Qt, so this works
the same on every desktop and nothing here special-cases one.

A machine with no printer answers nothing, which is ordinary rather than
exceptional — a laptop with no printer set up, a container, a test run.  Then
:data:`FALLBACK_SIZES` is offered instead, and the default comes from the
locale's measurement system, which is the only other thing that has an opinion:
the United States prints on Letter and the rest of the world on A4.

Asking the print subsystem can be slow — on Linux it is a CUPS round trip, and
a badly configured network printer makes it slower — so both answers are worked
out once and kept.  :mod:`~masafi_simtwin.preferences` is what stores a choice;
this module only says what there is to choose from.
"""

from __future__ import annotations

from PyQt6.QtCore import QLocale, QSizeF
from PyQt6.QtGui import QPageSize

#: The upright orientation, and the one on its side.  They are stored as these
#: words, so the settings file says what it means.
PORTRAIT = 'portrait'
LANDSCAPE = 'landscape'

#: Both of them, in the order the settings dialog offers them.
ORIENTATIONS: tuple[str, ...] = (PORTRAIT, LANDSCAPE)

#: What to offer when the machine has no printer to be asked — the sizes a
#: person is likely to want, rather than the hundred and nineteen Qt knows.
FALLBACK_SIZES: tuple[QPageSize.PageSizeId, ...] = (
    QPageSize.PageSizeId.A0,
    QPageSize.PageSizeId.A1,
    QPageSize.PageSizeId.A2,
    QPageSize.PageSizeId.A3,
    QPageSize.PageSizeId.A4,
    QPageSize.PageSizeId.A5,
    QPageSize.PageSizeId.A6,
    QPageSize.PageSizeId.B4,
    QPageSize.PageSizeId.B5,
    QPageSize.PageSizeId.Letter,
    QPageSize.PageSizeId.Legal,
    QPageSize.PageSizeId.Tabloid,
    QPageSize.PageSizeId.Executive,
)

#: The size fallen back on when nothing else has an opinion, and the one the
#: United States falls back on instead.
DEFAULT_SIZE = 'A4'
US_DEFAULT_SIZE = 'Letter'

#: What has been worked out already, so that the print subsystem is asked once.
_installed: list[QPageSize] | None = None
_default: str = ''


def _printer():
    """Give the printer to ask about paper, or ``None`` when there is none.

    Returns
    -------
    PyQt6.QtPrintSupport.QPrinterInfo, optional
        The default printer, the first one there is when no default is set, and
        ``None`` on a machine with no printers at all.

    Notes
    -----
    ``QtPrintSupport`` is imported here rather than at the top of the module so
    that a run which never asks about paper — every test of everything else —
    does not load the print subsystem at all.
    """

    from PyQt6.QtPrintSupport import QPrinterInfo

    default = QPrinterInfo.defaultPrinter()
    if not default.isNull():
        return default
    available = QPrinterInfo.availablePrinters()
    return available[0] if available else None


def installed_sizes() -> list[QPageSize]:
    """List the page sizes this machine offers.

    Returns
    -------
    list of PyQt6.QtGui.QPageSize
        What the printer takes, in the order it gives them, or
        :data:`FALLBACK_SIZES` when there is no printer to ask.  Custom sizes,
        which have no key to store and no dimensions of their own, are left
        out.
    """

    global _installed

    if _installed is not None:
        return list(_installed)

    printer = _printer()
    sizes = printer.supportedPageSizes() if printer is not None else []
    if not sizes:
        sizes = [QPageSize(identifier) for identifier in FALLBACK_SIZES]

    seen: set[str] = set()
    kept: list[QPageSize] = []
    for size in sizes:
        if size.key() and size.key() not in seen:
            seen.add(size.key())
            kept.append(size)

    _installed = kept
    return list(_installed)


def default_key() -> str:
    """Give the key of the page size this machine prints on by default.

    Returns
    -------
    str
        What the default printer says, or — with no printer to ask — ``Letter``
        where the locale measures in US units and :data:`DEFAULT_SIZE`
        everywhere else, which is the difference the two halves of the world
        actually make.
    """

    global _default

    if _default:
        return _default

    printer = _printer()
    if printer is not None and printer.defaultPageSize().key():
        _default = printer.defaultPageSize().key()
    elif QLocale.system().measurementSystem() == QLocale.MeasurementSystem.ImperialUSSystem:
        _default = US_DEFAULT_SIZE
    else:
        _default = DEFAULT_SIZE
    return _default


def size_of(key: str) -> QPageSize | None:
    """Find a page size by the key it is stored under.

    Parameters
    ----------
    key : str
        A key of :meth:`~PyQt6.QtGui.QPageSize.key`, such as ``A4``.

    Returns
    -------
    PyQt6.QtGui.QPageSize, optional
        The size, or ``None`` when no standard size goes by that key — which is
        what a settings file edited by hand can hold.
    """

    if not key:
        return None
    for identifier in QPageSize.PageSizeId:
        size = QPageSize(identifier)
        if size.key() == key:
            return size
    return None


def name_of(key: str) -> str:
    """Give what a page size is called, for showing.

    Parameters
    ----------
    key : str
        A key of :meth:`~PyQt6.QtGui.QPageSize.key`.

    Returns
    -------
    str
        Its name, and the key itself when it names nothing.  The names come
        from Qt, which is where their translations are too.
    """

    size = size_of(key)
    return size.name() if size is not None else key


def dimensions(key: str, orientation: str = PORTRAIT) -> QSizeF:
    """Give a page's size in millimetres, the way round it is to be used.

    Parameters
    ----------
    key : str
        A key of :meth:`~PyQt6.QtGui.QPageSize.key`.  A key that names nothing
        falls back to :func:`default_key`, so a settings file edited by hand
        cannot leave the application without a page.
    orientation : str, optional
        :data:`PORTRAIT` or :data:`LANDSCAPE`.  Anything else is taken as
        portrait, for the same reason.

    Returns
    -------
    PyQt6.QtCore.QSizeF
        The width and height in millimetres, in that orientation.
    """

    size = size_of(key) or size_of(default_key()) or QPageSize(QPageSize.PageSizeId.A4)
    millimetres = size.size(QPageSize.Unit.Millimeter)
    across = min(millimetres.width(), millimetres.height())
    along = max(millimetres.width(), millimetres.height())
    if orientation == LANDSCAPE:
        return QSizeF(along, across)
    return QSizeF(across, along)


def forget() -> None:
    """Ask the machine again next time, rather than repeating what it said.

    The printers of a machine can change while the application is running, and
    a test needs to be able to put a different answer in front of the same
    functions.
    """

    global _installed, _default

    _installed = None
    _default = ''
