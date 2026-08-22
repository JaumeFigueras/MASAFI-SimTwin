"""The tabbed document area at the centre of the window.

Every document type of the application — process flow model, animations, Petri
nets — opens here as a tab over the same underlying model.  The area shows a
placeholder while no document is open, in the way an IDE shows an empty editor
background, and swaps to the tab widget as soon as the first one arrives.
"""

from __future__ import annotations

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtWidgets import QLabel, QStackedWidget, QTabBar, QTabWidget, QToolButton, QWidget

from masafi_simtwin import icons

#: Side, in pixels, of the close button drawn at the right of every tab.
CLOSE_ICON_SIZE = 16


class DocumentArea(QStackedWidget):
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

        self.addWidget(self._placeholder)
        self.addWidget(self._tabs)
        self._update_visible_page()

    @property
    def tabs(self) -> QTabWidget:
        """PyQt6.QtWidgets.QTabWidget: The tab widget holding the documents."""

        return self._tabs

    @property
    def document_count(self) -> int:
        """int: How many documents are open."""

        return self._tabs.count()

    def add_document(self, widget: QWidget, title: str) -> int:
        """Open a document in a new tab and make it current.

        Parameters
        ----------
        widget : PyQt6.QtWidgets.QWidget
            The document view.
        title : str
            Translated tab title.

        Returns
        -------
        int
            Index of the new tab.
        """

        index = self._tabs.addTab(widget, title)
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
        button.clicked.connect(lambda: self.close_document(self._tabs.indexOf(document)))
        return button

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
        widget.deleteLater()
        self._update_visible_page()

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

        self.setCurrentWidget(self._tabs if self._tabs.count() else self._placeholder)
