"""The tool bar a Petri net's arcs are chosen from.

Two choices, one group of buttons each, with a separator between them: the
**shape** an arc is drawn in — straight, curved, S-curved, L-shaped — and the
**kind** of arc it is — normal or inhibitor.  The shape is a way of drawing and
the kind is a rule of the net, which is why they are two groups and not one row.

What a press of a button *means* depends on the selection, and that is the
editor's business rather than the bar's
(:class:`~masafi_simtwin.documents.petri_net.PetriNetEditor`):

* with **arcs selected**, the buttons show their shape and their kind — none
  checked where the selection is mixed — and a press changes all of them;
* with **none**, they show what the next arc drawn will be, and a press sets it.

A press sets the next arc in the first case as well.  Otherwise a person who
reshaped a selection and then put it down would see the bar jump back to a
choice made before, and read that as the press not having taken.

**The bar says in words what the icons cannot.**  Tool bars seldom carry text,
and this one does, for two reasons.  The icons are not symbols anybody already
knows — a curved arrow is not a glyph with a meaning of its own — so each group
is captioned, *Arc Shape* and *Arc Type*.  And a press acts on something that
cannot be seen from the buttons at all, the selection or the next arc, so the
bar **begins with a label saying which**: *New Arc*, or *Selected Arcs* and how
many.  That label is what makes the rule above something to read rather than
something to remember.  The captions are muted so that they read as captions
rather than as buttons; the label saying what a press acts on is not, being the
one piece of text on the bar that changes.

The label is given the width of the widest thing it says, so the buttons after
it do not shift sideways as the selection comes and goes.  It counts in the form
*Selected Arcs: 3* rather than *3 selected arcs*, because a count woven into a
sentence needs a plural form in every language, and the catalogues cannot carry
one yet — see *Plural strings would break the translation gate* in
``FUTURE.md``.

So the bar holds no behaviour at all.  It says what was chosen, through
:attr:`ArcToolBar.shape_chosen` and :attr:`ArcToolBar.kind_chosen`, and it is told
what to show.

**The icons are painted, not taken from Material Symbols.**  Each is the arc it
names, drawn by the same functions that draw an arc on the sheet — the chord's
frame, the default points, the segments, the arrowhead — so an L in the bar is
the L that will be drawn.  The one liberty is the bow of the two curves, which
is exaggerated: on paper a curve bows a fifth of its length, and at twenty
pixels that is a pixel and a half — a curve that has to be looked at twice to be
told from a straight line.  The corner of an L is not exaggerated; it is a right
angle on paper and in the icon.  Painted icons do not follow the theme of their
own accord, so the bar paints them again on every palette change, as
:class:`~masafi_simtwin.library_tree.LibraryTree` does for its own.
"""

from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtCore import QLineF, QPointF, QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QAction, QActionGroup, QColor, QIcon, QPainter, QPalette, QPen, QPixmap
from PyQt6.QtWidgets import QLabel, QToolBar, QWidget

from masafi_simtwin import icons
from masafi_simtwin.documents.arc import (
    DEFAULT_CONTROLS,
    DEFAULT_POINTS,
    ArcKind,
    ArcShape,
    arrowhead,
    chord_point,
    kind_label,
    route_path,
    route_segments,
    shape_label,
)

#: How big an icon is, in pixels: the size of every other icon of the chrome.
ICON_SIZE = icons.CHROME_ICON_SIZE

#: How far in from the edge of an icon the drawing keeps, in pixels.
ICON_MARGIN = 3.5

#: How thick an icon's line is, in pixels.
ICON_PEN = 1.5

#: How long an icon's arrowhead is and how wide across its base, in pixels.
ICON_ARROW_LENGTH = 5.5
ICON_ARROW_WIDTH = 5.0

#: How big the ring of the inhibitor icon is, in pixels of radius.
ICON_RING_RADIUS = 2.75

#: How wide the bar standing for a transition is in the kind icons, in pixels.
#: A kind is what an arc does *to a transition*, so the icon shows one.
ICON_BAR_WIDTH = 2.0

#: How many times further than on paper each curve bows in its icon.  See the
#: module's own description for why only the curves are exaggerated.
ICON_BOW = {
    ArcShape.CURVED: 2.5,
    ArcShape.S_CURVED: 1.5,
}

#: The device pixel ratios every icon is painted at, so that it is sharp on a
#: high-density screen as well as on an ordinary one.
ICON_SCALES = (1.0, 2.0)

#: The count the label saying what a press acts on is made wide enough for.  A
#: selection of a hundred arcs or more widens it by a digit, which shifts the
#: buttons once in a very long while rather than at every click.
WIDEST_COUNT = 99


def shape_route(shape: ArcShape, size: int = ICON_SIZE) -> tuple[QLineF, list]:
    """Give the arc a shape's icon draws.

    The chord runs corner to corner, up and to the right, so that every shape
    has room to bend and an L turns a real corner: its default point, half way
    along and half way across, lands in the bottom right-hand corner.

    Parameters
    ----------
    shape : masafi_simtwin.documents.arc.ArcShape
        The shape.
    size : int, optional
        The side of the icon, in pixels.

    Returns
    -------
    tuple
        The chord and the segments along it, in the icon's pixels.
    """

    far = size - ICON_MARGIN
    line = QLineF(ICON_MARGIN, far, far, ICON_MARGIN)
    bow = ICON_BOW.get(shape, 1.0)
    controls = [chord_point(line, along, across * bow) for along, across in DEFAULT_CONTROLS]
    points = [
        chord_point(line, along, across * bow)
        for along, across in DEFAULT_POINTS.get(shape, ())
    ]
    return line, route_segments(line, shape, controls, points)


def ink_pen(colour: QColor) -> QPen:
    """Build the pen an icon's line is drawn with.

    The cap is flat so that the line stops where it is told to rather than half
    a pen beyond, which under the point of an arrowhead is a nub; the join is
    mitered, as an arc's is, so the corner of an L is a corner.

    Parameters
    ----------
    colour : PyQt6.QtGui.QColor
        The ink.

    Returns
    -------
    PyQt6.QtGui.QPen
        The pen.
    """

    pen = QPen(colour, ICON_PEN)
    pen.setCapStyle(Qt.PenCapStyle.FlatCap)
    pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
    return pen


def draw_shape(shape: ArcShape) -> Callable[[QPainter, QColor, int], None]:
    """Give what draws a shape's icon.

    Parameters
    ----------
    shape : masafi_simtwin.documents.arc.ArcShape
        The shape.

    Returns
    -------
    collections.abc.Callable
        Something taking a painter, the ink and the size of the icon, which
        draws the arc :func:`shape_route` gives, ending in its arrowhead.
    """

    def draw(painter: QPainter, ink: QColor, size: int) -> None:
        line, segments = shape_route(shape, size)
        path = route_path(line, segments)
        painter.setPen(ink_pen(ink))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(ink)
        painter.drawPath(
            arrowhead(line, path, bool(segments), ICON_ARROW_LENGTH, ICON_ARROW_WIDTH)
        )

    return draw


def draw_kind(kind: ArcKind) -> Callable[[QPainter, QColor, int], None]:
    """Give what draws a kind's icon.

    A line running into a bar, the bar being the transition the kind is about:
    ending in an arrowhead for a normal arc and in a ring for an inhibitor one.
    The ring is left open and the line stops at it, rather than being filled
    with the colour of the paper as it is on the sheet — a button has no paper,
    and a checked one is a different colour from an unchecked one.

    Parameters
    ----------
    kind : masafi_simtwin.documents.arc.ArcKind
        The kind.

    Returns
    -------
    collections.abc.Callable
        Something taking a painter, the ink and the size of the icon.
    """

    def draw(painter: QPainter, ink: QColor, size: int) -> None:
        middle = size / 2.0
        far = size - ICON_MARGIN
        tip = far - ICON_BAR_WIDTH

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(ink)
        painter.drawRect(QRectF(tip, ICON_MARGIN, ICON_BAR_WIDTH, far - ICON_MARGIN))

        painter.setPen(ink_pen(ink))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        if kind is ArcKind.INHIBITOR:
            centre = QPointF(tip - ICON_RING_RADIUS - ICON_PEN / 2.0, middle)
            painter.drawLine(QLineF(ICON_MARGIN, middle, centre.x() - ICON_RING_RADIUS, middle))
            painter.drawEllipse(centre, ICON_RING_RADIUS, ICON_RING_RADIUS)
            return

        line = QLineF(ICON_MARGIN, middle, tip, middle)
        painter.drawLine(QLineF(ICON_MARGIN, middle, tip - ICON_ARROW_LENGTH / 2.0, middle))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(ink)
        painter.drawPath(
            arrowhead(line, route_path(line, []), False, ICON_ARROW_LENGTH, ICON_ARROW_WIDTH)
        )

    return draw


def build_icon(draw: Callable[[QPainter, QColor, int], None], palette: QPalette) -> QIcon:
    """Paint an icon in the colours of a palette.

    The disabled look is painted as well rather than left to the style to
    work out, so that a button that cannot be pressed is drawn in the palette's
    own disabled ink, the way its text would be.

    Parameters
    ----------
    draw : collections.abc.Callable
        What draws it — see :func:`draw_shape` and :func:`draw_kind`.
    palette : PyQt6.QtGui.QPalette
        Whose ink to draw it in.

    Returns
    -------
    PyQt6.QtGui.QIcon
        The icon, at every one of :data:`ICON_SCALES`.
    """

    icon = QIcon()
    for mode, group in (
        (QIcon.Mode.Normal, QPalette.ColorGroup.Active),
        (QIcon.Mode.Disabled, QPalette.ColorGroup.Disabled),
    ):
        ink = palette.color(group, QPalette.ColorRole.ButtonText)
        for scale in ICON_SCALES:
            pixmap = QPixmap(round(ICON_SIZE * scale), round(ICON_SIZE * scale))
            pixmap.setDevicePixelRatio(scale)
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            draw(painter, ink, ICON_SIZE)
            painter.end()
            icon.addPixmap(pixmap, mode)
    return icon


class ArcToolBar(QToolBar):
    """The shapes and the kinds of arc, as two captioned groups of buttons.

    Parameters
    ----------
    parent : PyQt6.QtWidgets.QWidget, optional
        Parent widget.

    Attributes
    ----------
    shape_chosen : PyQt6.QtCore.pyqtSignal
        Emitted with the :class:`~masafi_simtwin.documents.arc.ArcShape` of a
        shape button that was pressed.
    kind_chosen : PyQt6.QtCore.pyqtSignal
        Emitted with the :class:`~masafi_simtwin.documents.arc.ArcKind` of a
        kind button that was pressed.
    """

    shape_chosen = pyqtSignal(object)
    kind_chosen = pyqtSignal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName('ArcToolBar')
        self.setMovable(False)
        self.setFloatable(False)
        self.setIconSize(QSize(ICON_SIZE, ICON_SIZE))
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)

        self._target_label = self._add_label('ArcTargetLabel')
        self.addSeparator()

        self._shape_caption = self._add_label('ArcShapeCaption', self.tr('Arc Shape'))
        self._shape_group = self._build_group()
        self._shape_actions = {
            shape: self._add_choice(shape, shape_label(shape), self._shape_group)
            for shape in ArcShape
        }
        self.addSeparator()

        self._kind_caption = self._add_label('ArcKindCaption', self.tr('Arc Type'))
        self._kind_group = self._build_group()
        self._kind_actions = {
            kind: self._add_choice(kind, kind_label(kind), self._kind_group)
            for kind in ArcKind
        }

        self._shape_group.triggered.connect(self._on_shape_triggered)
        self._kind_group.triggered.connect(self._on_kind_triggered)
        self.show_target(0)
        self._reserve_target_width()
        self._apply_icons()

    # ------------------------------------------------------------------
    # The buttons and their words
    # ------------------------------------------------------------------

    def _add_label(self, name: str, text: str = '') -> QLabel:
        """Add a piece of text to the bar.

        Parameters
        ----------
        name : str
            Its object name, which is what the style sheet tells the captions
            and the label saying what a press acts on apart by.
        text : str, optional
            What it says.

        Returns
        -------
        PyQt6.QtWidgets.QLabel
            The label.
        """

        label = QLabel(text, self)
        label.setObjectName(name)
        self.addWidget(label)
        return label

    def _build_group(self) -> QActionGroup:
        """Build one exclusive group of buttons.

        Exclusive, so a press checks one and puts the other down; but Qt lets a
        group be left with **nothing** checked when it is told to, which is what
        a selection holding arcs of two shapes needs to be shown as.

        Returns
        -------
        PyQt6.QtGui.QActionGroup
            The group.
        """

        group = QActionGroup(self)
        group.setExclusive(True)
        return group

    def _add_choice(self, value, label: str, group: QActionGroup) -> QAction:
        """Add one checkable button standing for a value.

        Parameters
        ----------
        value : masafi_simtwin.documents.arc.ArcShape or masafi_simtwin.documents.arc.ArcKind
            What the button stands for, kept as the action's data.
        label : str
            What it is called, which is its tool tip: the button shows only its
            icon, and the caption before its group says what it is one of.
        group : PyQt6.QtGui.QActionGroup
            The group it is one of.

        Returns
        -------
        PyQt6.QtGui.QAction
            The action behind the button.
        """

        action = QAction(label, self)
        action.setCheckable(True)
        action.setData(value)
        action.setToolTip(label)
        group.addAction(action)
        self.addAction(action)
        return action

    def shape_action(self, shape: ArcShape) -> QAction:
        """Give the button of one shape.

        Parameters
        ----------
        shape : masafi_simtwin.documents.arc.ArcShape
            The shape.

        Returns
        -------
        PyQt6.QtGui.QAction
            Its action.
        """

        return self._shape_actions[ArcShape(shape)]

    def kind_action(self, kind: ArcKind) -> QAction:
        """Give the button of one kind of arc.

        Parameters
        ----------
        kind : masafi_simtwin.documents.arc.ArcKind
            The kind.

        Returns
        -------
        PyQt6.QtGui.QAction
            Its action.
        """

        return self._kind_actions[ArcKind(kind)]

    @property
    def captions(self) -> tuple[str, str]:
        """tuple of str: What the shapes and the kinds are captioned, in order."""

        return self._shape_caption.text(), self._kind_caption.text()

    # ------------------------------------------------------------------
    # What is shown
    # ------------------------------------------------------------------

    @property
    def target_text(self) -> str:
        """str: What the bar says a press acts on."""

        return self._target_label.text()

    def target_label_text(self, selected: int) -> str:
        """Give what the bar says a press acts on, for a number of selected arcs.

        Parameters
        ----------
        selected : int
            How many arcs are selected.

        Returns
        -------
        str
            *New Arc* for none — a press sets the arc drawn next — and
            *Selected Arcs* with the count otherwise.  A label and a number
            rather than a sentence, because a sentence counting something needs
            a plural the catalogues cannot carry yet.
        """

        if selected <= 0:
            return self.tr('New Arc')
        return self.tr('Selected Arcs: {0}').format(selected)

    def show_target(self, selected: int) -> None:
        """Say what a press of the bar acts on.

        Parameters
        ----------
        selected : int
            How many arcs are selected; nought means the next arc to be drawn.
        """

        self._target_label.setText(self.target_label_text(selected))

    def _reserve_target_width(self) -> None:
        """Make the label saying what a press acts on as wide as it will get.

        Every button on the bar comes after it, so a label that grew and shrank
        with its text would move them all sideways each time an arc was
        selected — a button that is not where it was a moment ago is a button
        pressed by mistake.  The width is taken from the label's own size hint
        for each thing it can say, which counts the style sheet's padding as
        well as the font.
        """

        label = self._target_label
        shown = label.text()
        label.ensurePolished()
        widest = 0
        for selected in (0, WIDEST_COUNT):
            label.setText(self.target_label_text(selected))
            widest = max(widest, label.sizeHint().width())
        label.setText(shown)
        label.setMinimumWidth(widest)

    @property
    def checked_shape(self) -> ArcShape | None:
        """ArcShape, optional: The shape whose button is checked, if one is."""

        action = self._shape_group.checkedAction()
        return None if action is None else action.data()

    @property
    def checked_kind(self) -> ArcKind | None:
        """ArcKind, optional: The kind whose button is checked, if one is."""

        action = self._kind_group.checkedAction()
        return None if action is None else action.data()

    def show_choice(self, shape: ArcShape | None, kind: ArcKind | None) -> None:
        """Check the buttons of a shape and a kind.

        Parameters
        ----------
        shape : masafi_simtwin.documents.arc.ArcShape, optional
            The shape to check, or ``None`` to check no shape at all — which is
            how a selection of arcs of more than one shape is shown.
        kind : masafi_simtwin.documents.arc.ArcKind, optional
            The same, for the kind.
        """

        for value, action in self._shape_actions.items():
            action.setChecked(value is shape)
        for value, action in self._kind_actions.items():
            action.setChecked(value is kind)

    def allow_kind(self, kind: ArcKind, allowed: bool) -> None:
        """Say whether a kind's button may be pressed.

        Parameters
        ----------
        kind : masafi_simtwin.documents.arc.ArcKind
            The kind.
        allowed : bool
            Whether it may.  A kind is refused where a selected arc could not be
            of it — an arc from a transition to a place cannot be an inhibitor —
            and a button that is refused is a button greyed out rather than one
            that is pressed and does nothing.
        """

        self.kind_action(kind).setEnabled(bool(allowed))

    # ------------------------------------------------------------------
    # What is said
    # ------------------------------------------------------------------

    def _on_shape_triggered(self, action: QAction) -> None:
        """Say which shape was pressed.

        Connected as a bound method, the group being a child of the bar: see
        *Signals and teardown*.

        Parameters
        ----------
        action : PyQt6.QtGui.QAction
            The button.
        """

        self.shape_chosen.emit(action.data())

    def _on_kind_triggered(self, action: QAction) -> None:
        """Say which kind was pressed.

        Parameters
        ----------
        action : PyQt6.QtGui.QAction
            The button.
        """

        self.kind_chosen.emit(action.data())

    # ------------------------------------------------------------------
    # The icons, and keeping up with the theme
    # ------------------------------------------------------------------

    def _apply_icons(self) -> None:
        """Paint every button's icon in the colours of the bar's palette."""

        palette = self.palette()
        for shape, action in self._shape_actions.items():
            action.setIcon(build_icon(draw_shape(shape), palette))
        for kind, action in self._kind_actions.items():
            action.setIcon(build_icon(draw_kind(kind), palette))

    def changeEvent(self, event) -> None:  # noqa: N802  (Qt naming)
        """Keep up with the theme and the font changing under the bar.

        The icons are painted again on a palette change, a painted icon not
        following the palette of its own accord; and the label saying what a
        press acts on is measured again on a font or a style change, either of
        which changes how wide its widest text is.

        Parameters
        ----------
        event : PyQt6.QtCore.QEvent
            The event that changed the widget.
        """

        super().changeEvent(event)
        if event.type() == event.Type.PaletteChange:
            self._apply_icons()
        elif event.type() in (event.Type.FontChange, event.Type.StyleChange):
            self._reserve_target_width()
