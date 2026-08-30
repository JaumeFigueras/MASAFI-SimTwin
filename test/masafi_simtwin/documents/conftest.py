"""What the tests of the net's items share.

The items of a net are tested in three modules that mirror the three the code is
in: :mod:`test_net_item` for everything a place and a transition do the same
way, and one module each for what makes a circle a circle and a bar a bar.  The
fixtures they have in common are here — a document to put items on, and a way of
painting one against a scheme and reading the pixels back.
"""

from __future__ import annotations

import pytest
from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QColor, QImage, QPainter
from PyQt6.QtWidgets import QStyleOptionGraphicsItem

from masafi_simtwin.documents.petri_net import PetriNetEditor
from masafi_simtwin.theme import build_palette

#: The manifest entry the editor is opened over.
MODEL = {
    'uuid': '7f3f9c6a',
    'name': 'Filling Station',
    'kind': 'petri-net',
    'file': 'models/Filling_Station.mfst',
    'units': {'time': 's'},
}

#: How many pixels one millimetre is painted as when the pixels are read back.
#: Big enough that a millimetre is several pixels and a sample lands where it
#: was aimed rather than in the blur beside it.
INK_SCALE = 6.0

#: How big the painted image is, in pixels, which is comfortably wider than the
#: longest item there is.
INK_SIZE = 160

#: How far a pixel may be from a colour and still be taken for it.
#:
#: A hairline is one device pixel wide however big the scene is drawn, and it
#: lands where anti-aliasing puts it — spread over two pixels, neither of which
#: is ever the pen's own colour.  A ring drawn in the accent comes within about
#: 75 of it and no nearer; the ink and the paper of either scheme are more than
#: twice that far away.  So this is loose enough to find a hairline and tight
#: enough that nothing else on the sheet is mistaken for one.
INK_TOLERANCE = 120


class Ink:
    """Paints one item against a scheme and reads the pixels back.

    The *item* is painted rather than the view, so that a scheme can be put in
    front of it without touching the palette of the application the whole suite
    shares.  Positions are given in millimetres from the item's centre, which is
    how everything on the sheet is measured.

    Parameters
    ----------
    scale : float, optional
        How many pixels a millimetre is drawn as.
    across : float, optional
        Which millimetre of the item lands at the middle of the image, across.
    down : float, optional
        The same, down.

    Attributes
    ----------
    scale : float
        Pixels to the millimetre.
    across, down : float
        Where the image is aimed, in the item's own millimetres.
    """

    def __init__(self, scale: float = INK_SCALE, across: float = 0.0, down: float = 0.0):
        self.scale = scale
        self.across = across
        self.down = down

    def close_up(self, across: float, down: float, scale: float) -> Ink:
        """Aim at one part of an item, drawn larger.

        A corner is a tenth of a millimetre of detail, and at the scale the
        whole item is read at that is less than a pixel.  This paints the same
        item again with a different part of it in the middle of the image and
        more pixels to the millimetre, so that a corner can be read the way an
        outline can.

        Parameters
        ----------
        across : float
            Which millimetre of the item to put at the middle, across.
        down : float
            The same, down.
        scale : float
            Pixels to the millimetre.

        Returns
        -------
        Ink
            A painter aimed there.  The original is unchanged.
        """

        return Ink(scale, across, down)

    def painted(self, item, colors) -> QImage:
        """Draw an item on the ground of a scheme.

        Parameters
        ----------
        item : masafi_simtwin.documents.net_item.NetItem
            The item to draw.
        colors : masafi_simtwin.theme.ThemeColors
            The scheme to draw it in.

        Returns
        -------
        PyQt6.QtGui.QImage
            The image, aimed where this painter is aimed.
        """

        image = QImage(INK_SIZE, INK_SIZE, QImage.Format.Format_ARGB32)
        image.fill(QColor(colors.editor))

        option = QStyleOptionGraphicsItem()
        option.palette = build_palette(colors)

        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.translate(INK_SIZE / 2.0, INK_SIZE / 2.0)
        painter.scale(self.scale, self.scale)
        painter.translate(-self.across, -self.down)
        item.paint(painter, option, None)
        painter.end()
        return image

    def at(self, image: QImage, across: float = 0.0, down: float = 0.0) -> QColor:
        """Give the colour at a point of the item, in millimetres.

        The point is measured from wherever this painter is aimed, which is the
        item's centre unless :meth:`close_up` moved it.

        Parameters
        ----------
        image : PyQt6.QtGui.QImage
            What was painted.
        across : float, optional
            Millimetres to the right.
        down : float, optional
            Millimetres below.

        Returns
        -------
        PyQt6.QtGui.QColor
            The pixel.
        """

        return QColor(
            image.pixel(
                int(INK_SIZE / 2.0 + across * self.scale),
                int(INK_SIZE / 2.0 + down * self.scale),
            )
        )

    def window(
        self, image: QImage, across: float, down: float, reach: float
    ) -> list[QColor]:
        """Give every pixel within a square of a point, in millimetres.

        A hairline is one pixel wide and lands where anti-aliasing puts it, so a
        test that reads a single pixel of one is a test of the rasteriser.  This
        reads the neighbourhood instead, and the assertion becomes *is any of
        this the accent* rather than *is this exact pixel*.

        Parameters
        ----------
        image : PyQt6.QtGui.QImage
            What was painted.
        across : float
            Millimetres to the right of the centre.
        down : float
            Millimetres below it.
        reach : float
            How far each way, in millimetres.

        Returns
        -------
        list of PyQt6.QtGui.QColor
            The pixels.
        """

        span = range(int(-reach * self.scale), int(reach * self.scale) + 1)
        return [
            self.at(image, across + x / self.scale, down + y / self.scale)
            for x in span
            for y in span
        ]

    @staticmethod
    def distance(first: QColor, second: QColor) -> int:
        """Give how far apart two colours are, summed over the channels.

        Parameters
        ----------
        first : PyQt6.QtGui.QColor
            One colour.
        second : PyQt6.QtGui.QColor
            The other.

        Returns
        -------
        int
            The distance between them.
        """

        return (
            abs(first.red() - second.red())
            + abs(first.green() - second.green())
            + abs(first.blue() - second.blue())
        )

    def holds(self, pixels: list[QColor], colour: QColor) -> bool:
        """Say whether any of some pixels is that colour, near enough.

        Parameters
        ----------
        pixels : list of PyQt6.QtGui.QColor
            What was read, usually from :meth:`window`.
        colour : PyQt6.QtGui.QColor
            What to look for.

        Returns
        -------
        bool
            Whether one of them is within :data:`INK_TOLERANCE` of it.
        """

        return any(self.distance(pixel, colour) <= INK_TOLERANCE for pixel in pixels)

    def nearest(self, colour: QColor, *candidates: QColor) -> QColor:
        """Say which of some colours a pixel is closest to.

        Reading the *nearest* colour rather than an exact one is what makes a
        test survive the anti-aliasing along an edge, and what makes it say
        something — that the ink is this colour and not that one — rather than
        only that something was painted.

        Parameters
        ----------
        colour : PyQt6.QtGui.QColor
            The pixel.
        *candidates : PyQt6.QtGui.QColor
            What it might be.

        Returns
        -------
        PyQt6.QtGui.QColor
            The closest of them.
        """

        return min(candidates, key=lambda candidate: self.distance(colour, candidate))


@pytest.fixture
def ink():
    """Give the painter the pixel tests read back.

    Returns
    -------
    Ink
        The helper.
    """

    return Ink()


@pytest.fixture
def editor(qtbot):
    """Build a Petri net document, shown, so that things can be dropped on it.

    Parameters
    ----------
    qtbot : pytestqt.qtbot.QtBot
        The pytest-qt bot.

    Returns
    -------
    masafi_simtwin.documents.petri_net.PetriNetEditor
        The document.
    """

    widget = PetriNetEditor(MODEL)
    qtbot.addWidget(widget)
    widget.resize(600, 400)
    widget.show()
    return widget


@pytest.fixture
def place(editor):
    """Put one place on the sheet, the way a drop does.

    Parameters
    ----------
    editor : masafi_simtwin.documents.petri_net.PetriNetEditor
        The document.

    Returns
    -------
    masafi_simtwin.documents.place.Place
        The place, already on the scene.
    """

    return editor.add_element('pt-petri-net', 'place', QPointF(100.0, 80.0))


@pytest.fixture
def transition(editor):
    """Put one transition on the sheet, the way a drop does.

    Parameters
    ----------
    editor : masafi_simtwin.documents.petri_net.PetriNetEditor
        The document.

    Returns
    -------
    masafi_simtwin.documents.transition.Transition
        The transition, already on the scene.
    """

    return editor.add_element('pt-petri-net', 'transition', QPointF(100.0, 80.0))
