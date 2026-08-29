"""The tabbed document area at the centre of the window.

Every document type of the application — process flow model, animations, Petri
nets — opens here as a tab over the same underlying model.  The area shows a
placeholder while no document is open, in the way an IDE shows an empty editor
background, and swaps to the tab widget as soon as the first one arrives.

A document is opened under a **key**, which is what makes a document a document
rather than one more copy of it: the key of a model is its UUID, so asking for
the same model twice raises the tab that is already open instead of adding a
second one, and renaming or deleting a model finds its tab without knowing where
the user has dragged it to.  The area gives no meaning to a key beyond that; it
is the window that decides what one stands for.

Like a tool pane, the documents are drawn as one rounded card — tab bar included,
so the tabs belong to the card rather than floating on the ground beside it —
inset by :data:`~masafi_simtwin.theme.PANE_GAP`.  The area itself is only the
transparent holder of that gap.
"""

from __future__ import annotations

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QLabel,
    QStackedWidget,
    QTabBar,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from masafi_simtwin import icons
from masafi_simtwin.theme import PANE_GAP

#: Side, in pixels, of the close button drawn at the right of every tab.
CLOSE_ICON_SIZE = 16


class DocumentArea(QWidget):
    """The tabbed document interface.

    Parameters
    ----------
    parent : PyQt6.QtWidgets.QWidget, optional
        Parent widget.

    Attributes
    ----------
    current_document_changed : PyQt6.QtCore.pyqtSignal
        Emitted with the title of the document that became current, or with an
        empty string once the last one is closed.
    """

    current_document_changed = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName('DocumentArea')

        self._placeholder = QLabel(self.tr('No document open'), self)
        self._placeholder.setObjectName('DocumentPlaceholder')
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._tabs = QTabWidget(self)
        self._tabs.setObjectName('DocumentTabs')
        self._tabs.setDocumentMode(True)
        self._tabs.setMovable(True)
        self._tabs.setElideMode(Qt.TextElideMode.ElideRight)
        self._tabs.currentChanged.connect(self._on_current_changed)

        #: The document each key stands for.  Widgets rather than indices,
        #: because a tab that is dragged changes its index and not its widget.
        self._documents: dict[str, QWidget] = {}

        self._stack = QStackedWidget(self)
        self._stack.addWidget(self._placeholder)
        self._stack.addWidget(self._tabs)

        card = QFrame(self)
        card.setObjectName('DocumentCard')
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.addWidget(self._stack)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(PANE_GAP, PANE_GAP, PANE_GAP, PANE_GAP)
        layout.addWidget(card)

        self._update_visible_page()

    @property
    def tabs(self) -> QTabWidget:
        """PyQt6.QtWidgets.QTabWidget: The tab widget holding the documents."""

        return self._tabs

    @property
    def document_count(self) -> int:
        """int: How many documents are open."""

        return self._tabs.count()

    @property
    def showing_placeholder(self) -> bool:
        """bool: Whether the card is showing the placeholder instead of the tabs."""

        return self._stack.currentWidget() is self._placeholder

    # ------------------------------------------------------------------
    # Opening
    # ------------------------------------------------------------------

    def add_document(
        self,
        widget: QWidget,
        title: str,
        key: str | None = None,
        tool_tip: str = '',
    ) -> int:
        """Open a document in a new tab and make it current.

        Parameters
        ----------
        widget : PyQt6.QtWidgets.QWidget
            The document view.
        title : str
            Translated tab title.
        key : str, optional
            What the document is, so that it can be found again.  A key already
            open is closed first, because two tabs of one thing is the state
            this key exists to prevent.
        tool_tip : str, optional
            What the tab says when the pointer rests on it, which is where a
            title too long for the tab bar can still be read.

        Returns
        -------
        int
            Index of the new tab.
        """

        if key is not None:
            self.close_document_for(key)

        index = self._tabs.addTab(widget, title)
        self._tabs.setTabToolTip(index, tool_tip or title)
        self._tabs.tabBar().setTabButton(
            index, QTabBar.ButtonPosition.RightSide, self._build_close_button(widget)
        )
        if key is not None:
            self._documents[key] = widget
        self._tabs.setCurrentIndex(index)
        self._update_visible_page()
        return index

    def _build_close_button(self, document: QWidget) -> QToolButton:
        """Build the close button of one tab.

        Qt's own closable tabs draw the close button with the current style,
        which under Fusion is a red cross that belongs to no theme of this
        application.  Supplying the button means it is a Material Symbol like
        every other icon, and that it follows the theme with them.

        Parameters
        ----------
        document : PyQt6.QtWidgets.QWidget
            The document the button closes.  The index is looked up when the
            button is pressed, because tabs move.

        Returns
        -------
        PyQt6.QtWidgets.QToolButton
            The close button.
        """

        button = QToolButton(self._tabs)
        button.setObjectName('TabCloseButton')
        button.setAutoRaise(True)
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        button.setIconSize(QSize(CLOSE_ICON_SIZE, CLOSE_ICON_SIZE))
        button.setFixedSize(QSize(CLOSE_ICON_SIZE + 4, CLOSE_ICON_SIZE + 4))
        button.setToolTip(self.tr('Close'))
        icons.set_icon(button, 'close')
        button.clicked.connect(lambda: self.close_document(self._tabs.indexOf(document)))
        return button

    # ------------------------------------------------------------------
    # Finding what is open
    # ------------------------------------------------------------------

    def document(self, key: str) -> QWidget | None:
        """Give the document opened under a key.

        Parameters
        ----------
        key : str
            What was passed to :meth:`add_document`.

        Returns
        -------
        PyQt6.QtWidgets.QWidget, optional
            The document, or ``None`` when it is not open.
        """

        return self._documents.get(key)

    def show_document(self, key: str) -> bool:
        """Raise the document opened under a key, if it is open.

        Parameters
        ----------
        key : str
            What was passed to :meth:`add_document`.

        Returns
        -------
        bool
            Whether there was one to raise.  A caller opens the document when
            there was not, which is what makes this the whole of *open or
            raise*.
        """

        widget = self._documents.get(key)
        if widget is None:
            return False
        self._tabs.setCurrentIndex(self._tabs.indexOf(widget))
        return True

    def set_document_title(self, key: str, title: str, tool_tip: str = '') -> None:
        """Retitle a document that is open, and do nothing when it is not.

        Parameters
        ----------
        key : str
            What was passed to :meth:`add_document`.
        title : str
            The new tab title.
        tool_tip : str, optional
            The new tool tip, the title itself when omitted.
        """

        widget = self._documents.get(key)
        if widget is None:
            return
        index = self._tabs.indexOf(widget)
        self._tabs.setTabText(index, title)
        self._tabs.setTabToolTip(index, tool_tip or title)
        if index == self._tabs.currentIndex():
            self.current_document_changed.emit(title)

    # ------------------------------------------------------------------
    # Closing
    # ------------------------------------------------------------------

    def close_document(self, index: int) -> None:
        """Close one document.

        Parameters
        ----------
        index : int
            Index of the tab to close.
        """

        widget = self._tabs.widget(index)
        if widget is None:
            return
        self._tabs.removeTab(index)
        self._forget(widget)
        widget.deleteLater()
        self._update_visible_page()

    def close_document_for(self, key: str) -> None:
        """Close the document opened under a key, if it is open.

        Parameters
        ----------
        key : str
            What was passed to :meth:`add_document`.
        """

        widget = self._documents.get(key)
        if widget is not None:
            self.close_document(self._tabs.indexOf(widget))

    def close_all_documents(self) -> None:
        """Close every document, which is what closing a project comes to."""

        while self._tabs.count():
            self.close_document(0)

    def _forget(self, widget: QWidget) -> None:
        """Drop the key a closed document was opened under.

        Parameters
        ----------
        widget : PyQt6.QtWidgets.QWidget
            The document that has just been removed from the tabs.
        """

        for key, document in list(self._documents.items()):
            if document is widget:
                del self._documents[key]

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------

    def _on_current_changed(self, index: int) -> None:
        """Report the document that became current.

        Parameters
        ----------
        index : int
            Index of the current tab, or ``-1`` when none is left.
        """

        self.current_document_changed.emit('' if index < 0 else self._tabs.tabText(index))

    def _update_visible_page(self) -> None:
        """Show the placeholder or the tabs, whichever the document count calls for."""

        self._stack.setCurrentWidget(self._tabs if self._tabs.count() else self._placeholder)
