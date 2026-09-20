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

Closing a tab **by hand asks first**: the close button calls
:attr:`DocumentArea.may_close` with the document's key, and the tab stays when the
answer is no.  That is where the window saves a model before its tab goes, and
where it can refuse when the model cannot be saved and the user would rather keep
it.  Closing in code — :meth:`DocumentArea.close_document_for`,
:meth:`DocumentArea.close_all_documents` — does not ask: the window closes a
model's tab that way when the model is deleted, which is not a moment to save it,
and when a project closes, having saved everything already.

A document with **unsaved changes** carries :data:`MODIFIED_MARK` after its title.
The area keeps each title apart from the mark, so a model renamed while it has
changes keeps both, and what is reported as the current document's title is the
title alone.  Whether a document has changes is the window's to say, through
:meth:`DocumentArea.set_document_modified`.

Like a tool pane, the documents are drawn as one rounded card — tab bar included,
so the tabs belong to the card rather than floating on the ground beside it —
inset by :data:`~masafi_simtwin.theme.PANE_GAP`.  The area itself is only the
transparent holder of that gap.
"""

from __future__ import annotations

from collections.abc import Callable

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

#: What follows the title of a document that has changes not yet saved.  Not
#: translated: an asterisk is the same mark in every language.
MODIFIED_MARK = ' *'


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
        empty string once the last one is closed.  The title alone, never the
        mark of unsaved changes.
    document_closed : PyQt6.QtCore.pyqtSignal
        Emitted with the key of a document once its tab has gone, however it
        was closed — an empty string for a document opened without one.
    may_close : collections.abc.Callable, optional
        Asked, with its key, whether a document may close when its close button
        is pressed; the tab stays when it answers false.  ``None`` lets every
        document close, and a document opened without a key is never asked
        about.  A plain callable rather than a signal, because it answers a
        question rather than reporting a fact.
    """

    current_document_changed = pyqtSignal(str)
    document_closed = pyqtSignal(str)

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
        #: Every document's title without the mark, by widget for the same
        #: reason, and the documents that carry the mark.
        self._titles: dict[QWidget, str] = {}
        self._modified: set[QWidget] = set()
        self.may_close: Callable[[str], bool] | None = None

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

        self._titles[widget] = title
        # Known by its key before it is a tab: the first tab added to an empty
        # area is made current by addTab itself, and whoever hears that asks
        # which document it is.
        if key is not None:
            self._documents[key] = widget
        index = self._tabs.addTab(widget, title)
        self._tabs.setTabToolTip(index, tool_tip or title)
        self._tabs.tabBar().setTabButton(
            index, QTabBar.ButtonPosition.RightSide, self._build_close_button(widget)
        )
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
        button.clicked.connect(lambda: self.request_close(self._tabs.indexOf(document)))
        return button

    # ------------------------------------------------------------------
    # Finding what is open
    # ------------------------------------------------------------------

    @property
    def documents(self) -> list[QWidget]:
        """list: Every open document, in the order the tabs are in."""

        return [self._tabs.widget(index) for index in range(self._tabs.count())]

    @property
    def keyed_documents(self) -> dict[str, QWidget]:
        """dict: Every document opened under a key, by its key, in no particular
        order."""

        return dict(self._documents)

    @property
    def current_document(self) -> QWidget | None:
        """PyQt6.QtWidgets.QWidget, optional: The document being looked at, or
        ``None`` when none is open."""

        return self._tabs.currentWidget()

    def key_of(self, widget: QWidget) -> str | None:
        """Give the key a document was opened under.

        Parameters
        ----------
        widget : PyQt6.QtWidgets.QWidget
            The document.

        Returns
        -------
        str, optional
            Its key, or ``None`` when it was opened without one or is not open.
        """

        for key, document in self._documents.items():
            if document is widget:
                return key
        return None

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
        self._titles[widget] = title
        index = self._tabs.indexOf(widget)
        self._show_title(widget)
        self._tabs.setTabToolTip(index, tool_tip or title)
        if index == self._tabs.currentIndex():
            self.current_document_changed.emit(title)

    def set_document_modified(self, key: str, modified: bool) -> None:
        """Mark a document as having unsaved changes, or take the mark away.

        Parameters
        ----------
        key : str
            What was passed to :meth:`add_document`.  A key that is not open is
            passed over.
        modified : bool
            Whether the document differs from what was last written.
        """

        widget = self._documents.get(key)
        if widget is None:
            return
        if modified:
            self._modified.add(widget)
        else:
            self._modified.discard(widget)
        self._show_title(widget)

    def is_document_modified(self, key: str) -> bool:
        """Say whether a document carries the mark of unsaved changes.

        Parameters
        ----------
        key : str
            What was passed to :meth:`add_document`.

        Returns
        -------
        bool
            Whether it does; false for a key that is not open.
        """

        widget = self._documents.get(key)
        return widget is not None and widget in self._modified

    def document_title(self, key: str) -> str:
        """Give a document's title, apart from the mark of unsaved changes.

        The title is kept apart from the mark — see
        :meth:`set_document_modified` — so this is what a document is *called*
        rather than what its tab happens to read, which is what anything naming
        a file after it wants.

        Parameters
        ----------
        key : str
            What was passed to :meth:`add_document`.

        Returns
        -------
        str
            The title, and an empty string for a key that is not open.
        """

        widget = self._documents.get(key)
        return self._titles.get(widget, '') if widget is not None else ''

    def _show_title(self, widget: QWidget) -> None:
        """Write a document's tab text: its title, and the mark when it has one.

        Parameters
        ----------
        widget : PyQt6.QtWidgets.QWidget
            The document.
        """

        title = self._titles.get(widget, '')
        mark = MODIFIED_MARK if widget in self._modified else ''
        self._tabs.setTabText(self._tabs.indexOf(widget), title + mark)

    # ------------------------------------------------------------------
    # Closing
    # ------------------------------------------------------------------

    def request_close(self, index: int) -> bool:
        """Close one document the way its close button does: asking first.

        Parameters
        ----------
        index : int
            Index of the tab to close.

        Returns
        -------
        bool
            Whether it closed.  It did not when :attr:`may_close` said no.
        """

        widget = self._tabs.widget(index)
        if widget is None:
            return False
        key = self.key_of(widget)
        if key is not None and self.may_close is not None and not self.may_close(key):
            return False
        self.close_document(index)
        return True

    def close_document(self, index: int) -> None:
        """Close one document, without asking.

        Parameters
        ----------
        index : int
            Index of the tab to close.
        """

        widget = self._tabs.widget(index)
        if widget is None:
            return
        key = self.key_of(widget)
        self._tabs.removeTab(index)
        self._forget(widget)
        widget.deleteLater()
        self._update_visible_page()
        self.document_closed.emit(key or '')

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
        self._titles.pop(widget, None)
        self._modified.discard(widget)

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

        widget = self._tabs.widget(index) if index >= 0 else None
        self.current_document_changed.emit(self._titles.get(widget, '') if widget else '')

    def _update_visible_page(self) -> None:
        """Show the placeholder or the tabs, whichever the document count calls for."""

        self._stack.setCurrentWidget(self._tabs if self._tabs.count() else self._placeholder)
