"""The Settings dialog.

The layout is :mod:`~masafi_simtwin.dialogs.forms.settings`, compiled from
``forms/settings.ui``: a tree of categories on the left, one page per category
on the right, in the arrangement of the settings dialog of an IDE.

Both halves live in the form, and they are paired **by order**.  Walking the
tree depth first gives ``Appearance, Language, Themes, Default Units, Time,
Space``, and the pages of the stack are in exactly that order, so the *n*-th
item shows the *n*-th page.  Adding a category therefore means adding both, in
the same place; :mod:`test.masafi_simtwin.dialogs.test_settings` fails when the
two lists stop lining up, so the pairing cannot drift unnoticed.

Two things a page cannot say for itself and this module writes into it:

* its **heading**, taken from the tree so that renaming a category in Designer
  renames its page with it — which is why the heading in the form is a
  non-translatable placeholder that only shows the shape of the page;
* the **links of a category that has children**, one per child, added to the
  ``<stem>_links`` layout the form leaves empty on such a page.  Clicking one
  selects the child in the tree, which is what shows its page.

The pages hold nothing but a placeholder yet.  Each is a plain ``QWidget`` in
the form, so the parameters of a category are added by opening the form and
dropping widgets into the page that already carries its name.

What those parameters will read and write is :attr:`SettingsDialog.edit`, a
:class:`~masafi_simtwin.preferences.PreferenceEdit` that holds changes aside
until the dialog is accepted.  That is what OK and Cancel mean here: OK writes
the pending changes and Cancel drops them, so a page never has to undo itself.
No page changes anything yet, so both buttons only close the dialog — but the
edit is opened, committed and discarded already, and a page added later needs
nothing more than to call :meth:`~masafi_simtwin.preferences.PreferenceEdit.set_value`.
"""

from __future__ import annotations

from html import escape
from typing import Iterator

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QLabel,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from masafi_simtwin.dialogs.forms.ui_settings import Ui_SettingsDialog
from masafi_simtwin.dialogs.restart import warn_restart_needed
from masafi_simtwin.preferences import (
    DISTANCE_UNITS,
    SURFACE_UNITS,
    SYSTEM_LANGUAGE,
    SYSTEM_THEME,
    TIME_UNITS,
    Preferences,
)
from masafi_simtwin.theme import ColorScheme
from masafi_simtwin.translations import LANGUAGE_NAMES, LANGUAGES

#: Where the index of the page of a category is kept, on the item itself.
PAGE_ROLE = Qt.ItemDataRole.UserRole

#: Suffix of the page widgets, dropped to reach the other widgets of a page.
PAGE_SUFFIX = '_page'

#: What ``appearance/theme`` is worth for each entry of the theme combo box, in
#: the order the entries are in the form.  The unit combo boxes are paired the
#: same way, with the tuples declared in :mod:`masafi_simtwin.preferences`.
#: Adding an entry in Designer means adding its value to the matching tuple;
#: the dialog refuses to open when the two disagree.
THEME_VALUES: tuple[str, ...] = (
    SYSTEM_THEME,
    *(scheme.value for scheme in ColorScheme),
)


class SettingsDialog(QDialog, Ui_SettingsDialog):
    """The settings of the application, by category.

    Parameters
    ----------
    parent : PyQt6.QtWidgets.QWidget, optional
        Parent widget.
    preferences : masafi_simtwin.preferences.Preferences, optional
        The preferences the pages edit.  The application's own are used when it
        is omitted; passing them is for the tests.

    Attributes
    ----------
    edit : masafi_simtwin.preferences.PreferenceEdit
        The changes the pages make, written when the dialog is accepted.

    Raises
    ------
    RuntimeError
        When the form's tree and its stack of pages do not line up, or when a
        category with children has no layout to put its links in.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        preferences: Preferences | None = None,
    ) -> None:
        super().__init__(parent)
        self.setupUi(self)

        self.edit = (preferences if preferences is not None else Preferences()).edit()

        self._pair_tree_with_pages()
        self._fill_pages()
        self._bind_language()
        for combo, key, values in (
            (self.theme_combo, 'appearance/theme', THEME_VALUES),
            (self.time_combo, 'units/time', TIME_UNITS),
            (self.distance_combo, 'units/distance', DISTANCE_UNITS),
            (self.surface_combo, 'units/surface', SURFACE_UNITS),
        ):
            self._bind_choice(combo, key, values)

        self._warned_about_restart = False

        self.category_tree.currentItemChanged.connect(self._on_category_changed)
        self.category_tree.itemClicked.connect(self._show_page_of)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.rejected.connect(self.edit.discard)

        #: The keys written the last time the dialog was accepted.
        self.written: tuple[str, ...] = ()

        self.category_tree.expandAll()
        self.category_tree.setCurrentItem(self.category_tree.topLevelItem(0))

    # ------------------------------------------------------------------
    # The categories
    # ------------------------------------------------------------------

    def categories(self) -> Iterator[QTreeWidgetItem]:
        """Walk the tree of categories depth first.

        Yields
        ------
        PyQt6.QtWidgets.QTreeWidgetItem
            Every category, a parent before its children, in the order the
            pages of the stack are in.
        """

        def walk(item: QTreeWidgetItem) -> Iterator[QTreeWidgetItem]:
            yield item
            for position in range(item.childCount()):
                yield from walk(item.child(position))

        for position in range(self.category_tree.topLevelItemCount()):
            yield from walk(self.category_tree.topLevelItem(position))

    def page_of(self, category: QTreeWidgetItem) -> QWidget:
        """Give the page a category shows.

        Parameters
        ----------
        category : PyQt6.QtWidgets.QTreeWidgetItem
            One of the items of the tree.

        Returns
        -------
        PyQt6.QtWidgets.QWidget
            The page of the stack that was paired with it.
        """

        return self.page_stack.widget(category.data(0, PAGE_ROLE))

    def _pair_tree_with_pages(self) -> None:
        """Give every category the index of the page it shows.

        Raises
        ------
        RuntimeError
            When the form holds a different number of pages than categories.
        """

        categories = list(self.categories())
        if len(categories) != self.page_stack.count():
            raise RuntimeError(
                f'settings.ui has {len(categories)} categories and '
                f'{self.page_stack.count()} pages; a category needs a page of '
                f'its own, in the same order.'
            )
        for index, category in enumerate(categories):
            category.setData(0, PAGE_ROLE, index)

    # ------------------------------------------------------------------
    # The pages
    # ------------------------------------------------------------------

    def _fill_pages(self) -> None:
        """Write the heading of every page, and the links of the ones with children."""

        for category in self.categories():
            page = self.page_of(category)
            stem = page.objectName().removesuffix(PAGE_SUFFIX)
            heading = page.findChild(QLabel, f'{stem}_heading')
            if heading is not None:
                heading.setText(category.text(0))
            if category.childCount():
                self._add_links(category, page, stem)

    def _add_links(self, category: QTreeWidgetItem, page: QWidget, stem: str) -> None:
        """Put one link per child on the page of a category.

        Parameters
        ----------
        category : PyQt6.QtWidgets.QTreeWidgetItem
            The category, which has children.
        page : PyQt6.QtWidgets.QWidget
            Its page.
        stem : str
            The name of the page without its suffix, which names its widgets.

        Raises
        ------
        RuntimeError
            When the form left no layout to put the links in.
        """

        links = page.findChild(QVBoxLayout, f'{stem}_links')
        if links is None:
            raise RuntimeError(
                f'{page.objectName()} has children but no {stem}_links layout to '
                f'list them in; add one to settings.ui.'
            )
        for position in range(category.childCount()):
            child = category.child(position)
            link = QLabel(f'<a href="#">{escape(child.text(0))}</a>', page)
            link.setObjectName(f'{stem}_link_{position}')
            link.setCursor(Qt.CursorShape.PointingHandCursor)
            link.linkActivated.connect(lambda _href, item=child: self._select(item))
            links.addWidget(link)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_category_changed(
        self, current: QTreeWidgetItem | None, _previous: QTreeWidgetItem | None
    ) -> None:
        """Show the page of the category the selection moved to.

        Parameters
        ----------
        current : PyQt6.QtWidgets.QTreeWidgetItem, optional
            The category now selected, if any.
        _previous : PyQt6.QtWidgets.QTreeWidgetItem, optional
            The one it was on before.
        """

        if current is not None:
            self._show_page_of(current)

    def _show_page_of(self, category: QTreeWidgetItem, _column: int = 0) -> None:
        """Bring the page of a category to the front.

        Clicking the category that is already selected moves no selection, so
        this is connected to the click as well; it is what makes a click on a
        parent take the user back to its list of children.

        Parameters
        ----------
        category : PyQt6.QtWidgets.QTreeWidgetItem
            The category that was selected or clicked.
        _column : int, optional
            The column that was clicked, which the tree has only one of.
        """

        self.page_stack.setCurrentWidget(self.page_of(category))

    def _select(self, category: QTreeWidgetItem) -> None:
        """Move the selection to a category, which shows its page.

        Parameters
        ----------
        category : PyQt6.QtWidgets.QTreeWidgetItem
            The category a link on a parent's page points at.
        """

        self.category_tree.setCurrentItem(category)
        self._show_page_of(category)

    # ------------------------------------------------------------------
    # The parameters
    # ------------------------------------------------------------------

    def _bind_language(self) -> None:
        """Fill the language combo box and follow it from there.

        The entries are built here rather than in the form because they are not
        layout: the languages the application offers are declared once, in
        :data:`~masafi_simtwin.translations.LANGUAGES`, and a language is shown
        under its own name — ``Català`` stays ``Català`` in every language, so
        there is nothing for a translator to do with it and nothing for the form
        to hold.  Only the first entry is a word, and that one goes through
        ``tr()`` here — disambiguated, because the theme page offers a *System
        default* of its own and a language may not agree with a theme
        grammatically.

        Raises
        ------
        RuntimeError
            When the form already holds entries, which would be duplicated by
            the ones added here.
        """

        combo: QComboBox = self.language_combo
        if combo.count():
            raise RuntimeError(
                'language_combo is filled from LANGUAGES, so it has to be left '
                f'empty in settings.ui; it holds {combo.count()} entries.'
            )
        combo.addItem(
            self.tr('System default', 'language, not theme'), SYSTEM_LANGUAGE
        )
        for language in LANGUAGES:
            combo.addItem(LANGUAGE_NAMES.get(language, language), language)
        combo.setCurrentIndex(combo.findData(self.edit.value('appearance/language')))
        combo.currentIndexChanged.connect(
            lambda index: self._on_choice('appearance/language', combo, index)
        )

    def _bind_choice(
        self, combo: QComboBox, key: str, values: tuple[str, ...]
    ) -> None:
        """Put a stored preference in a combo box and follow it from there.

        The entries of these combo boxes are in the form, because every one of
        them is a word the interface says — ``Dark``, ``Square metres`` — and
        those belong where a translator will find them.  What each entry stands
        for is not a word, so it is paired to the entries here, by order: the
        *n*-th entry of the form carries the *n*-th value.  That is the same
        arrangement as the tree and its pages, and it is guarded the same way.

        Parameters
        ----------
        combo : PyQt6.QtWidgets.QComboBox
            The combo box in the form.
        key : str
            The preference it edits.
        values : tuple of str
            What each of its entries is worth, in the order they are in.

        Raises
        ------
        RuntimeError
            When the form has a different number of entries than there are
            values for them.
        """

        if combo.count() != len(values):
            raise RuntimeError(
                f'{combo.objectName()} has {combo.count()} entries and {key} has '
                f'{len(values)} values to pair them with, in this order: {values}'
            )
        for index, value in enumerate(values):
            combo.setItemData(index, value)
        combo.setCurrentIndex(combo.findData(self.edit.value(key)))
        combo.currentIndexChanged.connect(
            lambda index, combo=combo, key=key: self._on_choice(key, combo, index)
        )

    def _on_choice(self, key: str, combo: QComboBox, index: int) -> None:
        """Hold a chosen value in the edit, and say a restart is coming if it is.

        Parameters
        ----------
        key : str
            The preference the combo box edits.
        combo : PyQt6.QtWidgets.QComboBox
            The combo box that moved.
        index : int
            The entry that is now current.
        """

        self.edit.set_value(key, combo.itemData(index))
        self._warn_once_about_restart()

    def _warn_once_about_restart(self) -> None:
        """Say that a restart is needed, the first time one is asked for.

        The notice belongs to the change, not to the control: moving the same
        combo box again says nothing more, and a page added later gets the same
        behaviour by calling this after it writes to the edit.
        """

        if self.edit.needs_restart and not self._warned_about_restart:
            self._warned_about_restart = True
            warn_restart_needed(self)

    # ------------------------------------------------------------------
    # Accepting
    # ------------------------------------------------------------------

    def accept(self) -> None:
        """Write the pending changes, then close.

        Overriding ``accept`` rather than connecting to it is what guarantees
        the changes are written before anything reacts to the dialog closing.
        """

        self.written = self.edit.commit()
        super().accept()
