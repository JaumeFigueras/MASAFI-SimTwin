"""Tests for printing a drawn document onto paper, as a PDF.

Three claims are made here and each is read off the file or the pixels rather
than trusted: that a printed page is **black on white whatever the application
is running in**, that it is **vector throughout** with its lettering as text a
reader can copy out, and that what is drawn lands at **true millimetres** on the
paper the settings say.

What is *not* printed is as much of it: the selection and the guides belong to
the session rather than to the net, and both have to be gone from the file and
back on the sheet afterwards.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import zlib

import pytest
from PyQt6.QtCore import QPointF, QRectF, QSizeF, Qt
from PyQt6.QtGui import QColor, QImage, QPageLayout, QPageSize, QPainter

from masafi_simtwin.documents import printing
from masafi_simtwin.documents.arc import ArcKind, ArcShape
from masafi_simtwin.documents.ink import on_paper
from masafi_simtwin.theme import DARK_COLORS, LIGHT_COLORS, PAPER, PAPER_INK, build_palette, paper_palette

#: A page small enough that a whole one can be painted into an image and read
#: back pixel by pixel without the test taking a second over it.
SMALL_PAGE = QSizeF(60.0, 50.0)

#: How many pixels to the millimetre a page is painted at when it is read back.
PRINT_ZOOM = 4.0


# ----------------------------------------------------------------------
# Reading a file back
# ----------------------------------------------------------------------


def streams(data: bytes) -> str:
    """Give everything a file was drawn with, unpacked.

    Parameters
    ----------
    data : bytes
        The file.

    Returns
    -------
    str
        Every stream of it that could be unpacked, run together.
    """

    unpacked = []
    for opened in re.finditer(rb'stream\r?\n', data):
        raw = data[opened.end() : data.find(b'endstream', opened.end())]
        try:
            unpacked.append(zlib.decompress(raw).decode('latin1'))
        except zlib.error:
            continue
    return '\n'.join(unpacked)


def media_boxes(data: bytes) -> list[tuple[float, float]]:
    """Give the size of every page of a file, in points.

    Parameters
    ----------
    data : bytes
        The file.

    Returns
    -------
    list of tuple
        The width and the height of each page.
    """

    found = re.findall(rb'/MediaBox\s*\[\s*0\s+0\s+([\d.]+)\s+([\d.]+)\s*\]', data)
    return [(float(width), float(height)) for width, height in found]


def read_out(path) -> str:
    """Give the text a reader takes out of a file.

    Parameters
    ----------
    path : pathlib.Path
        The file.

    Returns
    -------
    str
        What ``pdftotext`` read.
    """

    return subprocess.run(
        ['pdftotext', str(path), '-'], capture_output=True, text=True, check=True
    ).stdout


def painted(canvas, tile: QRectF, zoom: float = PRINT_ZOOM) -> QImage:
    """Print one page onto an image rather than into a file.

    Everything the page is drawn with is the same; only what it is drawn on
    differs, so what a page comes to can be read pixel by pixel.

    Parameters
    ----------
    canvas : masafi_simtwin.documents.canvas.Canvas
        The sheet.
    tile : PyQt6.QtCore.QRectF
        The page of it to draw, in millimetres.
    zoom : float, optional
        Pixels to the millimetre.

    Returns
    -------
    PyQt6.QtGui.QImage
        The page.
    """

    image = QImage(
        round(tile.width() * zoom), round(tile.height() * zoom), QImage.Format.Format_ARGB32
    )
    image.fill(QColor('red'))  # so that a page that is never filled is obvious
    painter = QPainter(image)
    with printing.as_printed(canvas), on_paper(paper_palette()):
        printing.draw_page(painter, canvas, tile, zoom)
    painter.end()
    return image


def colours_of(image: QImage) -> set[str]:
    """Give every colour an image holds.

    Parameters
    ----------
    image : PyQt6.QtGui.QImage
        The image.

    Returns
    -------
    set of str
        The colours, as ``#rrggbb``.
    """

    return {
        image.pixelColor(across, down).name()
        for down in range(image.height())
        for across in range(image.width())
    }


def ink_box(image: QImage) -> tuple[int, int, int, int]:
    """Give the corners of what was marked on a page, in pixels.

    Parameters
    ----------
    image : PyQt6.QtGui.QImage
        The page.

    Returns
    -------
    tuple
        Left, top, right and bottom.
    """

    marks = [
        (across, down)
        for down in range(image.height())
        for across in range(image.width())
        if image.pixelColor(across, down) != QColor(PAPER)
    ]
    assert marks, 'nothing was drawn on the page at all'
    return (
        min(across for across, _down in marks),
        min(down for _across, down in marks),
        max(across for across, _down in marks),
        max(down for _across, down in marks),
    )


@pytest.fixture
def dark(qapp):
    """Run the application in the dark scheme for the length of a test.

    Parameters
    ----------
    qapp : PyQt6.QtWidgets.QApplication
        The application.

    Yields
    ------
    None
        While the scheme is dark.
    """

    was = qapp.palette()
    qapp.setPalette(build_palette(DARK_COLORS))
    try:
        yield
    finally:
        qapp.setPalette(was)


@pytest.fixture
def sheet(editor):
    """Give a document on a small page, with one place and one transition.

    Parameters
    ----------
    editor : masafi_simtwin.documents.petri_net.PetriNetEditor
        The document.

    Returns
    -------
    masafi_simtwin.documents.petri_net.PetriNetEditor
        The document, its page :data:`SMALL_PAGE`.
    """

    editor.set_page(SMALL_PAGE)
    editor.add_element('pt-petri-net', 'place', QPointF(20.0, 20.0))
    editor.add_element('pt-petri-net', 'transition', QPointF(40.0, 20.0))
    return editor


# ----------------------------------------------------------------------
# Which pages there are
# ----------------------------------------------------------------------


def test_only_the_pages_that_hold_something_are_printed(editor):
    """The sheet is two hundred pages and a net sits in one corner of it, so a
    tile with nothing on it is not a page of the file."""

    editor.set_page(SMALL_PAGE)
    editor.add_element('pt-petri-net', 'place', QPointF(20.0, 20.0))

    assert printing.pages_of(editor) == [QRectF(0.0, 0.0, 60.0, 50.0)]

    editor.add_element('pt-petri-net', 'transition', QPointF(200.0, 120.0))

    assert printing.pages_of(editor) == [
        QRectF(0.0, 0.0, 60.0, 50.0),
        QRectF(180.0, 100.0, 60.0, 50.0),
    ]


def test_the_pages_come_out_in_reading_order(editor):
    """Left to right and then down, which is the order the pages of anything
    else are in."""

    editor.set_page(SMALL_PAGE)
    editor.add_element('pt-petri-net', 'place', QPointF(200.0, 120.0))
    editor.add_element('pt-petri-net', 'place', QPointF(20.0, 120.0))
    editor.add_element('pt-petri-net', 'place', QPointF(20.0, 20.0))

    corners = [(tile.left(), tile.top()) for tile in printing.pages_of(editor)]

    assert corners == [(0.0, 0.0), (0.0, 100.0), (180.0, 100.0)]


def test_a_net_drawn_across_a_seam_is_printed_on_both_pages(editor):
    """An item is clipped to each page it reaches rather than belonging to one
    of them, which is what makes the pages assemble into the drawing."""

    editor.set_page(SMALL_PAGE)
    editor.add_element('pt-petri-net', 'place', QPointF(60.0, 20.0))

    assert [tile.left() for tile in printing.pages_of(editor)] == [0.0, 60.0]


def test_a_sheet_with_nothing_drawn_on_it_has_no_pages(editor, tmp_path):
    """And writes no file: an empty PDF is worse than none."""

    path = tmp_path / 'nothing.pdf'

    assert printing.pages_of(editor) == []
    assert printing.print_to_pdf(editor, path) == 0
    assert not path.exists()


def test_guides_alone_are_not_something_to_print(editor, tmp_path):
    """A guide is what the drawing is lined up against rather than part of it —
    the rule *Copy* already keeps — so a sheet holding guides alone prints
    nothing at all."""

    editor.add_guide(Qt.Orientation.Horizontal, 40.0)
    editor.add_guide(Qt.Orientation.Vertical, 60.0)

    assert printing.pages_of(editor) == []
    assert printing.print_to_pdf(editor, tmp_path / 'guides.pdf') == 0


# ----------------------------------------------------------------------
# What the sheet is while it is being printed
# ----------------------------------------------------------------------


def test_nothing_of_the_session_is_printed(sheet):
    """The selection and the guides are what a person is working *with* rather
    than what they have drawn, and neither goes on the paper."""

    place = sheet.places[0]
    guide = sheet.add_guide(Qt.Orientation.Horizontal, 30.0)
    place.setSelected(True)

    with printing.as_printed(sheet):
        assert sheet.scene().selectedItems() == []
        assert not guide.isVisible()


def test_the_sheet_is_as_it_was_when_the_print_is_over(sheet):
    """A print is something looked at rather than something done to the net, so
    it leaves nothing behind."""

    place, = sheet.places
    guide = sheet.add_guide(Qt.Orientation.Horizontal, 30.0)
    place.setSelected(True)

    with printing.as_printed(sheet):
        pass

    assert sheet.scene().selectedItems() == [place]
    assert guide.isVisible()


def test_a_caption_is_taken_hold_of_again_the_way_it_was(sheet):
    """A label refuses a selection nobody asked for — which is what keeps a
    rubber band from picking one up — so putting one back has to be an asking
    and not a telling.  Told, it would simply not come back."""

    place, = sheet.places
    place.label.select()

    with printing.as_printed(sheet):
        assert sheet.scene().selectedItems() == []

    assert sheet.scene().selectedItems() == [place.label]


def test_the_sheet_is_put_back_even_when_the_print_fails(sheet, tmp_path):
    """One print that could not be written must not leave a sheet with its
    guides hidden and its selection gone."""

    place, = sheet.places
    guide = sheet.add_guide(Qt.Orientation.Horizontal, 30.0)
    place.setSelected(True)

    with pytest.raises(OSError):
        printing.print_to_pdf(sheet, tmp_path / 'no such folder' / 'net.pdf')

    assert sheet.scene().selectedItems() == [place]
    assert guide.isVisible()


# ----------------------------------------------------------------------
# What a page comes to
# ----------------------------------------------------------------------


@pytest.mark.parametrize('colors', [LIGHT_COLORS, DARK_COLORS], ids=['light', 'dark'])
def test_a_page_is_black_on_white_whatever_the_application_is_running_in(
    qapp, sheet, colors
):
    """Paper has no dark mode.  The application's own palette is what a scene
    hands its items, so this is the claim the whole of the printing rests on.

    Every colour on the page is a **grey** — the same in all three channels —
    which is what black on white comes to once the edges are drawn smooth: a
    page read back off a raster is full of the greys between the two, and any
    colour at all would be a tint the scheme had left behind.  The two ends are
    there as well, so it is not a page of nothing but edges.
    """

    was = qapp.palette()
    qapp.setPalette(build_palette(colors))
    try:
        page = painted(sheet, printing.pages_of(sheet)[0])
    finally:
        qapp.setPalette(was)

    colours = colours_of(page)

    assert page.pixelColor(0, 0) == QColor(PAPER)
    assert {PAPER, PAPER_INK} <= colours
    for colour in colours:
        assert QColor(colour).red() == QColor(colour).green() == QColor(colour).blue()


def test_a_colour_of_its_own_is_printed_as_it_is(sheet):
    """What follows the scheme is what printing changes; a colour a person chose
    is the thing's own, and it reaches the paper untouched."""

    from simtwin_core.petri_net import LineStyle

    place, = sheet.places
    place.line_style = LineStyle('#aa0000', 0.6)

    assert '#aa0000' in colours_of(painted(sheet, printing.pages_of(sheet)[0]))


def test_a_selected_thing_is_not_printed_in_the_accent(dark, sheet):
    """The accent says *this is in hand*, which is a fact about the session.
    The selection is cleared before anything is drawn, and the paper's own
    palette has no accent in it either, so this holds twice over."""

    for item in sheet.scene().items():
        item.setSelected(True)

    page = painted(sheet, printing.pages_of(sheet)[0])

    assert QColor(DARK_COLORS.accent).name() not in colours_of(page)
    assert QColor(LIGHT_COLORS.accent).name() not in colours_of(page)


def test_a_drawing_is_printed_at_true_millimetres(editor):
    """A place drawn ten millimetres across measures ten millimetres on the
    printout.  Qt measures a standard page in whole points, which makes its A4 a
    tenth of a millimetre narrower than A4; mapping the page onto the device
    rectangle would shrink the whole drawing to fit that error, so the painter
    is scaled to the paper's own dots to the millimetre instead."""

    editor.set_page(SMALL_PAGE)
    place = editor.add_element('pt-petri-net', 'place', QPointF(20.0, 25.0))
    place.name = ''  # or the caption under it is measured along with the circle

    left, top, right, bottom = ink_box(painted(editor, QRectF(0.0, 0.0, 60.0, 50.0)))
    radius = 5.0 * PRINT_ZOOM  # what a place is drawn, in pixels

    assert (left + right) / 2.0 == pytest.approx(20.0 * PRINT_ZOOM, abs=1)
    assert (top + bottom) / 2.0 == pytest.approx(25.0 * PRINT_ZOOM, abs=1)
    assert (right - left) / 2.0 == pytest.approx(radius, abs=1)
    assert (bottom - top) / 2.0 == pytest.approx(radius, abs=1)


def test_an_item_is_clipped_to_the_page_it_is_being_drawn_on(editor):
    """Half of it on one page and half on the next, rather than the whole of it
    twice."""

    editor.set_page(SMALL_PAGE)
    place = editor.add_element('pt-petri-net', 'place', QPointF(60.0, 25.0))
    place.name = ''  # the circle alone, so that each half can be measured

    first, second = printing.pages_of(editor)
    on_the_left = ink_box(painted(editor, first))
    on_the_right = ink_box(painted(editor, second))

    assert on_the_left[2] == round(60.0 * PRINT_ZOOM) - 1  # up to the seam
    assert on_the_right[0] == 0  # and on from it


# ----------------------------------------------------------------------
# The file
# ----------------------------------------------------------------------


def test_the_paper_is_the_one_the_settings_say():
    """*A4* is worth more to whoever opens the file than *297mm x 210mm*, so a
    page is named and turned rather than merely measured."""

    upright, turned = printing.page_layout_of(QSizeF(210.0, 297.0))
    across, turned_across = printing.page_layout_of(QSizeF(297.0, 210.0))
    odd, _way = printing.page_layout_of(QSizeF(123.0, 456.0))

    assert upright.id() == QPageSize.PageSizeId.A4
    assert turned == QPageLayout.Orientation.Portrait
    assert across.id() == QPageSize.PageSizeId.A4
    assert turned_across == QPageLayout.Orientation.Landscape
    assert odd.id() == QPageSize.PageSizeId.Custom


@pytest.mark.parametrize(
    'page, wider',
    [(QSizeF(210.0, 297.0), False), (QSizeF(297.0, 210.0), True)],
    ids=['portrait', 'landscape'],
)
def test_the_file_is_on_the_page_the_sheet_was_ruled_into(editor, tmp_path, page, wider):
    """A sheet ruled into landscape pages prints landscape pages."""

    editor.set_page(page)
    editor.add_element('pt-petri-net', 'place', QPointF(40.0, 40.0))
    path = tmp_path / 'net.pdf'

    assert printing.print_to_pdf(editor, path) == 1

    (width, height), = media_boxes(path.read_bytes())
    assert (width > height) is wider


def test_a_page_of_the_sheet_is_a_page_of_the_file(editor, tmp_path):
    """One tile, one page, in the order the tiles came in."""

    editor.set_page(SMALL_PAGE)
    editor.add_element('pt-petri-net', 'place', QPointF(20.0, 20.0))
    editor.add_element('pt-petri-net', 'place', QPointF(200.0, 120.0))
    path = tmp_path / 'net.pdf'

    assert printing.print_to_pdf(editor, path) == 2
    assert len(media_boxes(path.read_bytes())) == 2


def test_the_file_is_drawn_rather_than_photographed(sheet, tmp_path):
    """The whole point of doing it this way: every line is a line, so a page
    bears any zoom.  A rasterised page would be one image and no paths."""

    path = tmp_path / 'net.pdf'
    printing.print_to_pdf(sheet, path)
    data = path.read_bytes()

    assert not re.search(rb'/Subtype\s*/Image', data)
    assert ' c\n' in streams(data) or ' l\n' in streams(data)


def test_a_caption_is_text_in_the_file(sheet, tmp_path):
    """Which is what a reader selects, searches and copies out.  The font is
    embedded as a subset, so the file letters the same on a machine that has not
    got it."""

    path = tmp_path / 'net.pdf'
    printing.print_to_pdf(sheet, path)
    data = path.read_bytes()

    assert re.search(rb'/FontFile', data)
    assert 'BT' in streams(data)


@pytest.mark.skipif(shutil.which('pdftotext') is None, reason='no pdftotext here')
def test_a_reader_takes_the_words_back_out_of_the_file(sheet, tmp_path):
    """The claim itself, made by something that is not Qt: a name written on the
    sheet comes back out of the file as that name."""

    place, = sheet.places
    place.description = 'bottles waiting to be filled'
    path = tmp_path / 'net.pdf'
    printing.print_to_pdf(sheet, path)

    read = read_out(path)

    assert place.name in read
    assert 'bottles' in read


def test_the_file_says_what_it_is(sheet, tmp_path):
    """A model's name is the file's title, so a reader shows the model rather
    than the path it was written to."""

    path = tmp_path / 'net.pdf'
    printing.print_to_pdf(sheet, path, title='Filling Station')
    data = path.read_bytes()

    assert b'Filling Station' in data
    assert printing.CREATOR.encode() in data


def test_a_file_that_cannot_be_written_says_so(sheet, tmp_path):
    """Qt refuses to begin painting rather than raising, so that has to become
    an error like any other file error — there is a window to report it on."""

    with pytest.raises(OSError):
        printing.print_to_pdf(sheet, tmp_path / 'no such folder' / 'net.pdf')


def test_the_pages_are_drawn_at_the_papers_own_dots(sheet, tmp_path, monkeypatch):
    """The file is written the same way the pixel tests above read it: page by
    page, scaled to the paper's own dots to the millimetre.

    This is what keeps the file honest where the pixels cannot see: mapping each
    page onto the device rectangle instead would draw the same picture, a
    twentieth of a percent small, and no image read back at four pixels to the
    millimetre would ever show it.
    """

    drawn = []
    really = printing.draw_page

    def watched(painter, canvas, tile, dots):
        drawn.append((tile, dots))
        really(painter, canvas, tile, dots)

    monkeypatch.setattr(printing, 'draw_page', watched)
    printing.print_to_pdf(sheet, tmp_path / 'net.pdf')

    assert [tile for tile, _dots in drawn] == printing.pages_of(sheet)
    assert {dots for _tile, dots in drawn} == {printing.PRINT_RESOLUTION / 25.4}
