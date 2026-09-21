"""The Settings dialog.

The layout is :mod:`~masafi_simtwin.dialogs.forms.settings`, compiled from
``forms/settings.ui``: a tree of categories on the left, one page per category
on the right, in the arrangement of the settings dialog of an IDE.

Both halves live in the form, and they are paired **by order**.  Walking the
tree depth first gives ``Appearance, Language, Themes, Page, Default Units,
Time, Space, Saving``, and the pages of the stack are in exactly that order, so the
*n*-th item shows the *n*-th page.  Adding a category therefore means adding both, in
the same place; :mod:`test.masafi_simtwin.dialogs.test_settings` fails when the
two lists stop lining up, so the pairing cannot drift unnoticed.

Two things a page cannot say for itself and this module writes into it:

* its **heading**, taken from the tree so that renaming a category in Designer
  renames its page with it — which is why the heading in the form is a
  non-translatable placeholder that only shows the shape of the page;
* the **links of a category that has children**, one per child, added to the
  ``<stem>_links`` layout the form leaves empty on such a page.  Clicking one
  selects the child in the tree, which is what shows its page.

Each page is a plain ``QWidget`` in the form, so the parameters of a category are
added by opening the form and dropping widgets into the page that already carries
its name.  The leaves hold them — language, theme, page, time, space and saving —
and the two parents hold the links to their children.

What those parameters read and write is :attr:`SettingsDialog.edit`, a
:class:`~masafi_simtwin.preferences.PreferenceEdit` that holds changes aside
until the dialog is accepted.  That is what OK and Cancel mean here: OK writes
the pending changes and Cancel drops them, so a page never has to undo itself,
and a page added later needs nothing more than to call
:meth:`~masafi_simtwin.preferences.PreferenceEdit.set_value`.
"""

from __future__ import annotations

from html import escape
from typing import Any, Iterator

from PyQt6.QtCore import QCoreApplication, Qt
from PyQt6.QtGui import QColor, QFontDatabase, QIcon, QPalette, QPixmap
from PyQt6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QLabel,
    QPushButton,
    QRadioButton,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from masafi_simtwin import fonts, paper
from masafi_simtwin.dialogs.forms.ui_settings import Ui_SettingsDialog
from masafi_simtwin.dialogs.restart import warn_restart_needed
from masafi_simtwin.preferences import (
    AUTOSAVE_INTERVALS,
    AUTOSAVE_KEY,
    DISTANCE_UNITS,
    GRID_STEP_KEY,
    MAX_GRID_STEP,
    MIN_GRID_STEP,
    SURFACE_UNITS,
    SYSTEM_FONT,
    SYSTEM_LANGUAGE,
    SYSTEM_THEME,
    TIME_UNITS,
    TYPEFACES,
    Preferences,
)
from masafi_simtwin.theme import COLORS, ColorScheme
from masafi_simtwin.translations import LANGUAGE_NAMES, LANGUAGES
from simtwin_core.petri_net import (
    ALIGNMENTS,
    AUTOMATIC,
    MAX_FONT_SIZE,
    MAX_LINE_WIDTH,
    MIN_FONT_SIZE,
    MIN_LINE_WIDTH,
)

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

#: What ``petri_net/alignment`` is worth for each entry of the alignment combo
#: box, in the order the entries are in the form.  They are the core's own
#: names, so the dialog and a document cannot come to mean different things by
#: the same word.
ALIGNMENT_VALUES: tuple[str, ...] = tuple(ALIGNMENTS)

#: Each colour a net is drawn in: the preference it is stored under, the box
#: that says it follows the theme, the button a colour is chosen on, and the
#: label warning that the colour chosen will not follow the theme.
COLOUR_CONTROLS: tuple[tuple[str, str, str, str], ...] = (
    (
        'petri_net/text_colour',
        'text_colour_automatic',
        'text_colour_button',
        'text_colour_note',
    ),
    (
        'petri_net/line_colour',
        'line_colour_automatic',
        'line_colour_button',
        'line_colour_note',
    ),
)

#: The inks the two themes write in, which are the colours *Automatic* stands
#: for.  Choosing one of them outright is what the warning is about: it looks
#: right in the scheme it was chosen in and wrong in the other, and it is the
#: one choice a person is most likely to make by accident.
THEME_INKS: frozenset[str] = frozenset(
    colours.text.lower() for colours in COLORS.values()
)

#: How big the square of colour on a colour button is drawn, in pixels.
SWATCH_SIZE = 14


def ask_for_colour(parent: QWidget, current: str) -> str | None:
    """Ask the user for a colour, through Qt's own colour dialog.

    It is a function rather than a method so that a test can answer it without a
    modal dialog opening on the screen, which is what
    :func:`~masafi_simtwin.dialogs.restart.warn_restart_needed` is for the
    restart notice.

    Parameters
    ----------
    parent : PyQt6.QtWidgets.QWidget
        What the dialog is modal over.
    current : str
        The colour to open on, or :data:`~simtwin_core.petri_net.AUTOMATIC`,
        which is no colour and opens on the ink of the scheme in force.

    Returns
    -------
    str, optional
        The colour as ``#rrggbb``, or ``None`` when the dialog was given up.
    """

    if current == AUTOMATIC:
        initial = parent.palette().color(QPalette.ColorRole.Text)
    else:
        initial = QColor(current)
    chosen = QColorDialog.getColor(
        initial,
        parent,
        QCoreApplication.translate('SettingsDialog', 'Choose a Colour'),
    )
    return chosen.name() if chosen.isValid() else None


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
        self._bind_paper()
        self._bind_orientation()
        self._bind_fonts()
        for combo, key, values in (
            (self.theme_combo, 'appearance/theme', THEME_VALUES),
            (self.alignment_combo, 'petri_net/alignment', ALIGNMENT_VALUES),
            (self.time_combo, 'units/time', TIME_UNITS),
            (self.distance_combo, 'units/distance', DISTANCE_UNITS),
            (self.surface_combo, 'units/surface', SURFACE_UNITS),
            (self.autosave_combo, AUTOSAVE_KEY, AUTOSAVE_INTERVALS),
        ):
            self._bind_choice(combo, key, values)
        self._bind_size(
            self.font_size_spin,
            self.font_size_points,
            'petri_net/font_size',
            MIN_FONT_SIZE,
            MAX_FONT_SIZE,
        )
        self._bind_size(
            self.line_width_spin,
            self.line_width_points,
            'petri_net/line_width',
            MIN_LINE_WIDTH,
            MAX_LINE_WIDTH,
        )
        self._bind_size(
            self.grid_step_spin,
            None,
            GRID_STEP_KEY,
            MIN_GRID_STEP,
            MAX_GRID_STEP,
        )
        self._bind_typefaces()
        self._bind_colours()

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

    def _bind_paper(self) -> None:
        """Fill the paper combo box from the machine, and follow it from there.

        The entries are built here rather than in the form for the same reason
        the languages are: they are not layout.  What paper there is to choose
        from is what this machine prints on — a different list on a different
        desk — and the names come from Qt, which is where their translations
        are.  The form therefore has to leave the combo empty.

        The entry shown when nothing has been chosen is the size this machine
        prints on by default, which is what ``appearance/page_size`` being unset
        means.  A size stored that this machine does not offer — a settings file
        carried from another desk — is added rather than dropped, so that the
        dialog shows what is actually in force.

        Raises
        ------
        RuntimeError
            When the form already holds entries, which would be duplicated by
            the ones added here.
        """

        combo: QComboBox = self.paper_combo
        if combo.count():
            raise RuntimeError(
                'paper_combo is filled from the sizes this machine offers, so it '
                f'has to be left empty in settings.ui; it holds {combo.count()} '
                f'entries.'
            )
        for size in paper.installed_sizes():
            combo.addItem(size.name(), size.key())

        chosen = self.edit.value('appearance/page_size') or paper.default_key()
        if combo.findData(chosen) < 0:
            combo.addItem(paper.name_of(chosen), chosen)
        combo.setCurrentIndex(combo.findData(chosen))
        combo.currentIndexChanged.connect(
            lambda index: self._on_choice('appearance/page_size', combo, index)
        )

    def _bind_orientation(self) -> None:
        """Set the orientation radio buttons, and follow them from there.

        Two of them are a choice of one thing, so they are read as one: the
        button that is on says what is stored.  Radio buttons in one layout are
        exclusive of their own accord, so turning one on turns the other off and
        only the one turning *on* is worth listening to.
        """

        buttons: tuple[tuple[QRadioButton, str], ...] = (
            (self.portrait_radio, paper.PORTRAIT),
            (self.landscape_radio, paper.LANDSCAPE),
        )
        stored = self.edit.value('appearance/page_orientation')
        for button, orientation in buttons:
            button.setChecked(orientation == stored)
            button.toggled.connect(
                lambda checked, value=orientation: self._on_orientation(checked, value)
            )

    def _on_orientation(self, checked: bool, orientation: str) -> None:
        """Hold the orientation that has just been turned on.

        Parameters
        ----------
        checked : bool
            Whether this is the button that came on rather than the one that
            went off.
        orientation : str
            What that button stands for.
        """

        if not checked:
            return
        self.edit.set_value('appearance/page_orientation', orientation)
        self._warn_once_about_restart()

    def _bind_choice(
        self, combo: QComboBox, key: str, values: tuple[Any, ...]
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
        values : tuple
            What each of its entries is worth, in the order they are in, of the
            preference's own type.

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

    def _bind_fonts(self) -> None:
        """Fill the font combo box from this machine, and follow it from there.

        The entries are built here rather than in the form for the reason the
        paper sizes are: what there is to choose from is what this machine has,
        which is a different list on a different desk.  The first entry is what
        leaving ``petri_net/font`` unset means, and it names the family that
        would be used, so the choice is between *whatever this machine has* and
        one family in particular rather than between a word and a list.

        A family stored that this machine has not got — a settings file carried
        from another desk — is added rather than dropped, so the dialog shows
        what is actually in force, exactly as a paper size does.

        Raises
        ------
        RuntimeError
            When the form already holds entries, which would be duplicated by
            the ones added here.
        """

        combo: QComboBox = self.font_combo
        if combo.count():
            raise RuntimeError(
                'font_combo is filled from the families this machine has, so it '
                f'has to be left empty in settings.ui; it holds {combo.count()} '
                f'entries.'
            )
        combo.addItem(
            self.tr('Default ({0})', 'the font a net is lettered in when none is chosen')
            .format(fonts.default_family()),
            SYSTEM_FONT,
        )
        for family in QFontDatabase.families():
            combo.addItem(family, family)

        stored = self.edit.value('petri_net/font')
        if stored and combo.findData(stored) < 0:
            combo.addItem(stored, stored)
        combo.setCurrentIndex(combo.findData(stored))
        combo.currentIndexChanged.connect(
            lambda index: self._on_choice('petri_net/font', combo, index)
        )

    def _bind_size(
        self,
        spin: QDoubleSpinBox,
        points: QLabel | None,
        key: str,
        low: float,
        high: float,
    ) -> None:
        """Put a length in a spin box, with its size in points beside it.

        The limits are set here rather than in the form because they are the
        rule the value is actually held to — the core's for a size a document
        carries, this module's for the grid — and a number typed into Designer
        could drift away from it.  The points are shown because a font is
        chosen in points everywhere else in the world, while the sheet — and so
        everything drawn on it — is measured in millimetres.  A length that is
        not lettering has no size in points to show, so the label is optional:
        the grid is a distance on the paper and nothing to do with a typeface.

        Parameters
        ----------
        spin : PyQt6.QtWidgets.QDoubleSpinBox
            The spin box in the form.
        points : PyQt6.QtWidgets.QLabel, optional
            The label beside it, which says the same size in points, and
            ``None`` for a length that is not a font's.
        key : str
            The preference it edits.
        low, high : float
            The smallest and the largest it may be, in millimetres.
        """

        spin.setRange(low, high)
        spin.setValue(self.edit.value(key))
        self._show_points(spin, points)
        spin.valueChanged.connect(
            lambda value, spin=spin, points=points, key=key: self._on_size(
                key, value, spin, points
            )
        )

    def _show_points(self, spin: QDoubleSpinBox, points: QLabel | None) -> None:
        """Say in points what a spin box holds in millimetres.

        Parameters
        ----------
        spin : PyQt6.QtWidgets.QDoubleSpinBox
            The spin box, in millimetres.
        points : PyQt6.QtWidgets.QLabel, optional
            The label to write in, and ``None`` for a length with no size in
            points to show, which is asked of this and answered by doing
            nothing so that no caller has to remember which lengths have one.
        """

        if points is None:
            return
        points.setText(self.tr('≈ {0} pt').format(f'{spin.value() / 25.4 * 72.0:.1f}'))

    def _on_size(
        self, key: str, value: float, spin: QDoubleSpinBox, points: QLabel | None
    ) -> None:
        """Hold a length that has just been typed or stepped to.

        Parameters
        ----------
        key : str
            The preference the spin box edits.
        value : float
            What it now holds, in millimetres.
        spin : PyQt6.QtWidgets.QDoubleSpinBox
            The spin box that moved.
        points : PyQt6.QtWidgets.QLabel, optional
            The label beside it, and ``None`` for a length with none.
        """

        self.edit.set_value(key, float(value))
        self._show_points(spin, points)
        self._warn_once_about_restart()

    def _bind_typefaces(self) -> None:
        """Set the Bold and Italic boxes of every kind of text, and follow them.

        The kinds are :data:`~masafi_simtwin.preferences.TYPEFACES`, and the
        boxes of each are named after it, so a kind of text added there and
        forgotten in the form is a failure rather than a pair of controls that
        quietly edits nothing.  An arc is the one kind with no boxes: a weight
        is never bold, italic or aligned.

        Raises
        ------
        RuntimeError
            When a kind of text has no pair of boxes in the form.
        """

        for role, keys in TYPEFACES.items():
            if keys is None:
                continue
            for key, name in zip(keys, (f'{role}_bold_check', f'{role}_italic_check')):
                box: QCheckBox | None = self.findChild(QCheckBox, name)
                if box is None:
                    raise RuntimeError(
                        f'{key} is a typeface preference with no {name} in '
                        f'settings.ui to edit it.'
                    )
                box.setChecked(self.edit.value(key))
                box.toggled.connect(lambda ticked, key=key: self._on_flag(key, ticked))

    def _on_flag(self, key: str, ticked: bool) -> None:
        """Hold a yes-or-no preference that has just been ticked or unticked.

        Parameters
        ----------
        key : str
            The preference the box edits.
        ticked : bool
            Whether it is now ticked.
        """

        self.edit.set_value(key, bool(ticked))
        self._warn_once_about_restart()

    def _bind_colours(self) -> None:
        """Set both colour controls, and follow them from there."""

        for key, automatic, button, note in COLOUR_CONTROLS:
            box: QCheckBox = getattr(self, automatic)
            chooser: QPushButton = getattr(self, button)
            warning: QLabel = getattr(self, note)
            box.setChecked(self.edit.value(key) == AUTOMATIC)
            self._show_colour(key, chooser, warning)
            box.toggled.connect(
                lambda ticked, key=key, box=box, chooser=chooser, warning=warning: (
                    self._on_automatic(key, ticked, box, chooser, warning)
                )
            )
            chooser.clicked.connect(
                lambda _checked=False, key=key, chooser=chooser, warning=warning: (
                    self._choose_colour(key, chooser, warning)
                )
            )

    def _on_automatic(
        self, key: str, ticked: bool, box: QCheckBox, button: QPushButton, note: QLabel
    ) -> None:
        """Follow the theme, or ask for the colour to use instead of it.

        Unticking the box is the gesture that says *not the theme's colour, this
        one*, so it opens the colour dialog rather than leaving the user to find
        the button: a box unticked and no colour chosen would be a state that
        means nothing.  Giving that dialog up therefore puts the tick back.

        Parameters
        ----------
        key : str
            The preference the control edits.
        ticked : bool
            Whether *Automatic* is now ticked.
        box : PyQt6.QtWidgets.QCheckBox
            The box itself, to be put back when the dialog is given up.
        button : PyQt6.QtWidgets.QPushButton
            The button the colour is chosen on.
        note : PyQt6.QtWidgets.QLabel
            The warning under them.
        """

        if ticked:
            self.edit.set_value(key, AUTOMATIC)
            self._show_colour(key, button, note)
            self._warn_once_about_restart()
            return

        colour = ask_for_colour(self, self.edit.value(key))
        if colour is None:
            box.blockSignals(True)
            box.setChecked(True)
            box.blockSignals(False)
            return
        self.edit.set_value(key, colour)
        self._show_colour(key, button, note)
        self._warn_once_about_restart()

    def _choose_colour(self, key: str, button: QPushButton, note: QLabel) -> None:
        """Ask for a colour and hold it, leaving it alone if the dialog is given up.

        Parameters
        ----------
        key : str
            The preference the control edits.
        button : PyQt6.QtWidgets.QPushButton
            The button that was pressed.
        note : PyQt6.QtWidgets.QLabel
            The warning under it.
        """

        colour = ask_for_colour(self, self.edit.value(key))
        if colour is None:
            return
        self.edit.set_value(key, colour)
        self._show_colour(key, button, note)
        self._warn_once_about_restart()

    def _show_colour(self, key: str, button: QPushButton, note: QLabel) -> None:
        """Show what a colour is worth, and warn where the warning is due.

        The swatch is an icon built here rather than a style sheet, which a form
        may not carry and which could not follow the theme anyway.  The warning
        is raised for the inks the themes themselves write in: such a colour
        looks right in the scheme it was chosen in, is wrong in the other, and
        *Automatic* is what the person almost certainly meant.

        Parameters
        ----------
        key : str
            The preference the control edits.
        button : PyQt6.QtWidgets.QPushButton
            The button the colour is chosen on.
        note : PyQt6.QtWidgets.QLabel
            The warning under it.
        """

        colour = self.edit.value(key)
        chosen = colour != AUTOMATIC
        button.setEnabled(chosen)
        if chosen:
            swatch = QPixmap(SWATCH_SIZE, SWATCH_SIZE)
            swatch.fill(QColor(colour))
            button.setIcon(QIcon(swatch))
        else:
            button.setIcon(QIcon())
        note.setVisible(chosen and colour.lower() in THEME_INKS)

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
