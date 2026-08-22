"""The dockable tool panes opened from the tool stripes.

A pane is a ``QDockWidget`` drawn as a rounded card: title and close button
along the top, content below, the whole thing inset from the dock it occupies by
:data:`~masafi_simtwin.theme.PANE_GAP` so the ground shows around it.  The dock's
own title bar is given away to an empty widget, because a header that Qt lays out
above the card would sit outside the rounded corners.  A pane can be resized by
dragging its edge and closed from its header, but it cannot be dragged out into a
window of its own — a floating tool window is not part of the layout this
application is modelled on.

A pane is pinned to the one dock area it was built for, and the edge it is
resized by follows from that: a pane at the side has a smallest width, one at the
bottom a smallest height.

The pane that a stripe button opens is chosen by the window; a pane knows only
its own title, its area and the widget it holds.
"""

from __future__ import annotations

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtWidgets import (
    QDockWidget,
    QFrame,
    QHBoxLayout,
    QLabel,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from masafi_simtwin import icons
from masafi_simtwin.theme import PANE_GAP

#: Side, in pixels, of the close button drawn in the header of a pane.
CLOSE_ICON_SIZE = 16

#: Width, in pixels, a pane at the side is given the first time it is opened.
DEFAULT_PANE_WIDTH = 260

#: Width, in pixels, below which a pane at the side cannot be dragged.
MINIMUM_PANE_WIDTH = 160

#: Height, in pixels, a pane at the bottom is given the first time it is opened.
DEFAULT_PANE_HEIGHT = 220

#: Height, in pixels, below which a pane at the bottom cannot be dragged.
MINIMUM_PANE_HEIGHT = 96

#: The areas whose panes are resized by their width rather than their height.
_HORIZONTAL_AREAS = (
    Qt.DockWidgetArea.LeftDockWidgetArea,
    Qt.DockWidgetArea.RightDockWidgetArea,
)


class ToolPane(QDockWidget):
    """One tool pane.

    Parameters
    ----------
    title : str
        Translated title, shown in the header.
    content : PyQt6.QtWidgets.QWidget, optional
        The widget the pane holds.  A muted placeholder is used when it is
        omitted, which is what every pane shows while the tool behind it is
        still to be written.
    area : PyQt6.QtCore.Qt.DockWidgetArea, optional
        The dock area the pane belongs to, the left one by default.  It is the
        only area the pane is allowed in, and it decides which of the two
        smallest sizes applies.
    parent : PyQt6.QtWidgets.QWidget, optional
        Parent widget.
    """

    def __init__(
        self,
        title: str,
        content: QWidget | None = None,
        area: Qt.DockWidgetArea = Qt.DockWidgetArea.LeftDockWidgetArea,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(title, parent)
        self.setObjectName(f'ToolPane_{title}')
        self.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetClosable)
        self.setAllowedAreas(area)

        self._area = area
        if area in _HORIZONTAL_AREAS:
            self.setMinimumWidth(MINIMUM_PANE_WIDTH)
        else:
            self.setMinimumHeight(MINIMUM_PANE_HEIGHT)

        self._title_label = QLabel(title)
        self._title_label.setObjectName('ToolPaneTitle')
        self._header = self._build_header()

        self.setTitleBarWidget(QWidget(self))
        self.setWidget(
            self._build_card(content if content is not None else self._build_placeholder())
        )

    @property
    def header(self) -> QWidget:
        """PyQt6.QtWidgets.QWidget: The row holding the title and the close button."""

        return self._header

    @property
    def title(self) -> str:
        """str: The title shown in the header."""

        return self._title_label.text()

    @property
    def area(self) -> Qt.DockWidgetArea:
        """PyQt6.QtCore.Qt.DockWidgetArea: The dock area the pane belongs to."""

        return self._area

    @property
    def default_size(self) -> int:
        """int: The width, or the height, the pane is given when it first opens."""

        return DEFAULT_PANE_WIDTH if self._area in _HORIZONTAL_AREAS else DEFAULT_PANE_HEIGHT

    @property
    def resize_orientation(self) -> Qt.Orientation:
        """PyQt6.QtCore.Qt.Orientation: The direction the pane is resized in."""

        if self._area in _HORIZONTAL_AREAS:
            return Qt.Orientation.Horizontal
        return Qt.Orientation.Vertical

    def _build_header(self) -> QWidget:
        """Build the header that replaces the title bar drawn by the style.

        Returns
        -------
        PyQt6.QtWidgets.QWidget
            A row holding the title and the close button.
        """

        header = QWidget(self)
        header.setObjectName('ToolPaneHeader')

        layout = QHBoxLayout(header)
        layout.setContentsMargins(8, 4, 4, 4)
        layout.setSpacing(4)
        layout.addWidget(self._title_label)
        layout.addStretch(1)
        layout.addWidget(self._build_close_button(header))

        return header

    def _build_close_button(self, parent: QWidget) -> QToolButton:
        """Build the button that closes the pane.

        Parameters
        ----------
        parent : PyQt6.QtWidgets.QWidget
            The header the button belongs to.

        Returns
        -------
        PyQt6.QtWidgets.QToolButton
            The close button, wired to close the pane.  The stripe button
            follows through the dock's own visibility signal, so there is
            nothing else to keep in step here.
        """

        button = QToolButton(parent)
        button.setObjectName('ToolPaneClose')
        button.setAutoRaise(True)
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        button.setIconSize(QSize(CLOSE_ICON_SIZE, CLOSE_ICON_SIZE))
        button.setFixedSize(QSize(CLOSE_ICON_SIZE + 8, CLOSE_ICON_SIZE + 8))
        button.setToolTip(self.tr('Hide'))
        icons.set_icon(button, 'close')
        button.clicked.connect(self.close)
        return button

    def _build_placeholder(self) -> QWidget:
        """Build the muted notice shown while the pane has no tool behind it.

        Returns
        -------
        PyQt6.QtWidgets.QLabel
            A centred, muted label.
        """

        placeholder = QLabel(self.tr('Not implemented yet'))
        placeholder.setObjectName('ToolPanePlaceholder')
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder.setWordWrap(True)
        return placeholder

    def _build_card(self, content: QWidget) -> QWidget:
        """Build the card the pane is drawn as, inset from the dock around it.

        The card is a frame the style sheet can round and fill; the transparent
        widget around it is what holds the gap, since a ``QDockWidget`` gives its
        widget the whole of the space it was allotted.

        Parameters
        ----------
        content : PyQt6.QtWidgets.QWidget
            The widget the pane holds.

        Returns
        -------
        PyQt6.QtWidgets.QWidget
            The transparent widget to hand to ``setWidget``.
        """

        card = QFrame(self)
        card.setObjectName('ToolPaneCard')
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)
        card_layout.addWidget(self._header)
        card_layout.addWidget(self._wrap(content), 1)

        outer = QWidget(self)
        outer.setObjectName('ToolPaneOuter')
        outer_layout = QVBoxLayout(outer)
        outer_layout.setContentsMargins(PANE_GAP, PANE_GAP, PANE_GAP, PANE_GAP)
        outer_layout.addWidget(card)
        return outer

    def _wrap(self, content: QWidget) -> QWidget:
        """Put the content in a container the style sheet can reach.

        Parameters
        ----------
        content : PyQt6.QtWidgets.QWidget
            The widget the pane holds.

        Returns
        -------
        PyQt6.QtWidgets.QWidget
            The container.
        """

        container = QWidget(self)
        container.setObjectName('ToolPaneContent')
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(content)
        return container
