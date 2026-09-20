"""Printing a drawn document onto paper, as a PDF.

**Paper is not a screen, and three things follow.**  It is white and what is
drawn on it is black, whatever scheme the application happens to be running in —
:func:`~masafi_simtwin.theme.paper_palette`, put in front of everything that
draws by :func:`~masafi_simtwin.documents.ink.on_paper`.  A caption is **text**
rather than a path, so a reader can select it, search it and copy it out of the
file.  And nothing of the *session* is on it: not the selection, not the guides,
not the grid.

**The file is vector throughout**, which was the point of doing it this way:
every line is a line and every letter a letter, so a page bears any zoom.  The
lettering is embedded as a subset of the font it was drawn in and comes back out
of the file as the words it says.

**One page of the sheet is one page of the file, at true millimetres.**  The
sheet is already ruled into pages — see :mod:`masafi_simtwin.documents.canvas` —
so a print does not decide a layout, it takes the one the drawing was laid out
against.  The painter is scaled to the paper's own dots to the millimetre rather
than the page being mapped onto the device rectangle: Qt measures a standard
page in whole points, which makes its A4 a tenth of a millimetre narrower than
A4, and mapping onto that would shrink the whole drawing to fit an error.  A
place drawn ten millimetres across measures ten millimetres on the printout.

**Only the pages that hold something are printed.**  The sheet is two hundred
pages and a net usually sits in one corner of it, so a tile with nothing on it
is not a page of the file: a net that fits one page gives one page, and a net
drawn across a seam gives two.

Nothing here knows what a Petri net is.  A :class:`~masafi_simtwin.documents.canvas.Canvas`
is what every drawn document is built on, so this is what the flow and the 2D
tabs will print through as well.
"""

from __future__ import annotations

from contextlib import contextmanager

from PyQt6.QtCore import QMarginsF, QRectF, QSizeF, Qt
from PyQt6.QtGui import QColor, QPageLayout, QPageSize, QPainter, QPdfWriter

from masafi_simtwin.documents.canvas import PAGES_ACROSS, PAGES_DOWN
from masafi_simtwin.documents.guide import Guide
from masafi_simtwin.documents.ink import on_paper
from masafi_simtwin.documents.label import Label
from masafi_simtwin.theme import PAPER, paper_palette

#: How fine the paper is, in dots to the inch.  It is not how good the drawing
#: is — the file is vector and bears any zoom — but how finely a coordinate in
#: it can be written down, which at this is a fiftieth of a millimetre.
PRINT_RESOLUTION = 1200

#: How many millimetres there are to an inch, so that the one place the two
#: systems of measurement meet is named.
MM_TO_INCH = 25.4

#: What the file says made it.  A proper noun, so it is not translated.
CREATOR = 'MASAFI-SimTwin'

#: What a printed file is called by default and the suffix it takes.
PDF_SUFFIX = '.pdf'


def dots_per_mm(resolution: int = PRINT_RESOLUTION) -> float:
    """Give how many dots of the paper one millimetre comes to.

    Parameters
    ----------
    resolution : int, optional
        How fine the paper is, in dots to the inch.

    Returns
    -------
    float
        Dots to the millimetre.
    """

    return resolution / MM_TO_INCH


def page_layout_of(page: QSizeF) -> tuple[QPageSize, QPageLayout.Orientation]:
    """Say what paper a page of the sheet is, and which way round.

    A page of the sheet is a width and a height in millimetres and nothing more,
    because that is all a sheet needs to be ruled; a **file** says what paper it
    is on, and *A4* is worth more to whoever opens it than *297mm x 210mm*.  So
    the size is always given the portrait way round, which is how Qt knows the
    standard sizes, and the way round it actually is becomes the orientation —
    the same page either way, named rather than merely measured.

    Parameters
    ----------
    page : PyQt6.QtCore.QSizeF
        The page, in millimetres and already the way round it is to be printed,
        as :attr:`masafi_simtwin.documents.canvas.Canvas.page` gives it.

    Returns
    -------
    tuple
        The :class:`~PyQt6.QtGui.QPageSize` and the
        :class:`~PyQt6.QtGui.QPageLayout.Orientation`.
    """

    if page.width() > page.height():
        upright = QSizeF(page.height(), page.width())
        turned = QPageLayout.Orientation.Landscape
    else:
        upright = QSizeF(page)
        turned = QPageLayout.Orientation.Portrait
    return QPageSize(upright, QPageSize.Unit.Millimeter), turned


def pages_of(canvas) -> list[QRectF]:
    """Give the pages of the sheet that hold something, in reading order.

    A tile holds something when anything drawn reaches into it.  **Guides are
    not something drawn** — they are what the drawing is lined up against, which
    is the rule *Copy* already keeps — so a sheet holding guides alone prints
    nothing at all.

    Parameters
    ----------
    canvas : masafi_simtwin.documents.canvas.Canvas
        The sheet.

    Returns
    -------
    list of PyQt6.QtCore.QRectF
        The tiles, in millimetres, left to right and top to bottom.
    """

    page = canvas.page
    marks = [
        item.sceneBoundingRect()
        for item in canvas.scene().items()
        if item.isVisible() and not isinstance(item, Guide)
    ]
    if not marks:
        return []

    tiles = []
    for down in range(PAGES_DOWN):
        for across in range(PAGES_ACROSS):
            tile = QRectF(
                across * page.width(),
                down * page.height(),
                page.width(),
                page.height(),
            )
            if any(tile.intersects(mark) for mark in marks):
                tiles.append(tile)
    return tiles


@contextmanager
def as_printed(canvas):
    """Put the sheet into the state a print draws it in, and put it back after.

    **Nothing of the session is printed.**  The selection is what a person is
    working on rather than part of the net, and it reaches the drawing in eleven
    places — the accent, a thicker line, a caption's frame, an arc's handles —
    so it is cleared for the duration rather than asked about eleven times.  The
    guides go the same way, and both come back exactly as they were.

    A caption is put back through :meth:`~masafi_simtwin.documents.label.Label.select`
    rather than by being told it is selected: a label refuses a selection nobody
    asked for, which is what keeps a rubber band from picking one up, and this
    is an asking.

    **The scene's signals are left alone.**  Blocking them would stop the
    ``selectionChanged`` the Properties pane and the arc tool bar listen to —
    and stop the ``changed`` the *view* listens to, which is how it learns to
    repaint what the print disturbed.  Nothing flashes without that: a print is
    one synchronous stretch of work with no event loop inside it, so the pane is
    asked twice and both times after the selection is back.

    Parameters
    ----------
    canvas : masafi_simtwin.documents.canvas.Canvas
        The sheet.

    Yields
    ------
    None
        While the sheet is as a print draws it.
    """

    scene = canvas.scene()
    selected = scene.selectedItems()
    guides = [guide for guide in canvas.guides if guide.isVisible()]
    try:
        scene.clearSelection()
        for guide in guides:
            guide.setVisible(False)
        yield
    finally:
        for guide in guides:
            guide.setVisible(True)
        for item in selected:
            if isinstance(item, Label):
                item.select()
            else:
                item.setSelected(True)


def draw_page(painter: QPainter, canvas, tile: QRectF, dots: float) -> None:
    """Draw one page of the sheet onto a painter, at true millimetres.

    The painter is scaled to the paper's own dots to the millimetre and moved so
    that the tile's top left corner is the corner of the page; the scene is then
    rendered onto itself, which is to say with no scaling of its own — Qt maps
    the source onto the target, and the two being one rectangle leaves the
    millimetres the painter was given.

    Everything outside the tile is clipped, so an item lying across a seam is
    drawn in part on each of the two pages it reaches.

    Parameters
    ----------
    painter : PyQt6.QtGui.QPainter
        What to draw with.  It is left as it was found.
    canvas : masafi_simtwin.documents.canvas.Canvas
        The sheet.
    tile : PyQt6.QtCore.QRectF
        The page of the sheet to draw, in millimetres.
    dots : float
        How many dots of what is being drawn on one millimetre comes to.
    """

    painter.save()
    painter.scale(dots, dots)
    painter.translate(-tile.left(), -tile.top())
    painter.fillRect(tile, QColor(PAPER))
    canvas.scene().render(painter, tile, tile, Qt.AspectRatioMode.IgnoreAspectRatio)
    painter.restore()


def print_to_pdf(canvas, path, title: str = '') -> int:
    """Print a sheet to a PDF file, and say how many pages it came to.

    Parameters
    ----------
    canvas : masafi_simtwin.documents.canvas.Canvas
        The sheet.
    path : str or pathlib.Path
        Where to write the file.
    title : str, optional
        What the file calls itself, which is the model's name.

    Returns
    -------
    int
        How many pages were written.  **Nought writes no file**: a sheet with
        nothing drawn on it has no pages that hold something, and an empty file
        would be worse than none.

    Raises
    ------
    OSError
        When the file cannot be written.  Qt says so by refusing to begin
        painting rather than by raising, so this is where that becomes an error
        like any other file error.
    """

    with as_printed(canvas):
        tiles = pages_of(canvas)
        if not tiles:
            return 0

        size, orientation = page_layout_of(canvas.page)
        writer = QPdfWriter(str(path))
        writer.setPageSize(size)
        writer.setPageOrientation(orientation)
        writer.setPageMargins(QMarginsF(0.0, 0.0, 0.0, 0.0), QPageLayout.Unit.Millimeter)
        writer.setResolution(PRINT_RESOLUTION)
        writer.setCreator(CREATOR)
        if title:
            writer.setTitle(title)

        painter = QPainter()
        if not painter.begin(writer):
            raise OSError(f'the drawing could not be written to {path}')
        try:
            with on_paper(paper_palette()):
                for number, tile in enumerate(tiles):
                    if number:
                        writer.newPage()
                    draw_page(painter, canvas, tile, dots_per_mm())
        finally:
            painter.end()
    return len(tiles)
