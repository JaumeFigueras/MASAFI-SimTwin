"""The Properties pane: what is selected on the current sheet, or the model it is.

The layout is :mod:`~masafi_simtwin.panes.forms.ui_properties`, compiled from
``forms/properties.ui``: a stack of pages, one shown at a time.

* **Nothing** — no model is open, or the tab being looked at is not a model.
* **Model** — a model is open and nothing on its sheet is selected: its name, its
  kind and its units, read-only, as decided with Jaume.
* **Place** — one place or several, and nothing else, selected: its name, its
  initial tokens and its description, to be edited.  With several places the
  name cannot be edited, and a field they do not agree on is left blank.
* **Selection** — anything else: how many places, transitions and arcs.

**The pane is told what to show and never looks for it.**  The window asks the
document what is selected, :func:`~masafi_simtwin.documents.selection_of`, and
hands the answer over, so the pane knows descriptions —
:class:`~simtwin_core.petri_net.PlaceData`, :class:`~simtwin_core.petri_net.ArcData`
— and nothing of the items on a scene.

**Nor does it change anything.**  An edit is *asked for* — :attr:`PropertiesPane.name_asked`,
:attr:`PropertiesPane.tokens_asked`, :attr:`PropertiesPane.description_asked` — and
the document makes it as one recorded change, so it is undone like any other and
reaches the journal like any other.  What the pane then shows is what the sheet
became, because the recorded change is what refreshes it.

**A name is checked as it is typed**, with :func:`~simtwin_core.petri_net.name_problem`
— the rule the document holds too — and the reason it is refused is said under
the field.  A name still refused when editing ends is put back rather than asked
for.
"""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QWidget

from masafi_simtwin.panes.forms.ui_properties import Ui_PropertiesPane
from masafi_simtwin.project import ModelKind
from simtwin_core.petri_net import NameProblem, name_problem

#: How a unit whose stored value is not its symbol is written.  The values are
#: kept to ASCII so the settings file needs no encoding; the microsecond's symbol
#: is not.
UNIT_SYMBOLS: dict[str, str] = {'us': 'µs'}

#: What the tokens field holds while the places shown do not agree on theirs: one
#: below the fewest tokens there can be, drawn as a blank.
MIXED = -1


def unit_symbol(unit: str) -> str:
    """Give the symbol a unit is written with.

    Parameters
    ----------
    unit : str
        The unit as it is stored — ``s``, ``us``, ``km``.

    Returns
    -------
    str
        Its symbol, which is the same in every language and is not translated.
    """

    return UNIT_SYMBOLS.get(unit, unit)


class PropertiesPane(QWidget, Ui_PropertiesPane):
    """What the Properties pane holds.

    Parameters
    ----------
    parent : PyQt6.QtWidgets.QWidget, optional
        Parent widget.

    Attributes
    ----------
    name_asked : PyQt6.QtCore.pyqtSignal
        Emitted with a place's UUID and the name it is to be given, once editing
        of a name the rule allows has ended.
    tokens_asked : PyQt6.QtCore.pyqtSignal
        Emitted with the UUIDs of the places shown and the tokens they are all
        to hold.
    description_asked : PyQt6.QtCore.pyqtSignal
        Emitted with the UUIDs of the places shown and the description they are
        all to have.
    """

    name_asked = pyqtSignal(str, str)
    tokens_asked = pyqtSignal(object, int)
    description_asked = pyqtSignal(object, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setupUi(self)

        #: The places on the place page, and the names the one shown may not take.
        self._places: tuple = ()
        self._taken: tuple[str, ...] = ()
        #: Set while fields are filled in, so that filling one is not an edit.
        self._showing = False

        self.place_name_edit.textEdited.connect(self._on_name_edited)
        self.place_name_edit.editingFinished.connect(self._on_name_finished)
        self.place_tokens_spin.setKeyboardTracking(False)
        self.place_tokens_spin.valueChanged.connect(self._on_tokens_changed)
        self.place_description_edit.editingFinished.connect(self._on_description_finished)

        self.show_nothing()

    @property
    def page(self) -> QWidget:
        """PyQt6.QtWidgets.QWidget: The page being shown."""

        return self.page_stack.currentWidget()

    # ------------------------------------------------------------------
    # What is shown
    # ------------------------------------------------------------------

    def show_nothing(self) -> None:
        """Show that there is no model to say anything about."""

        self._places = ()
        self.page_stack.setCurrentWidget(self.nothing_page)

    def show_model(self, model: dict) -> None:
        """Show a model that has nothing selected on its sheet.

        Parameters
        ----------
        model : dict
            The model's entry in the manifest: its ``name``, ``kind`` and
            ``units``.  A model with no distance unit — a Petri net, a process
            flow — shows no distance row at all rather than an empty one.
        """

        units = model.get('units') or {}
        distance = units.get('distance')
        self._places = ()
        self.model_name_value.setText(model.get('name', ''))
        self.model_kind_value.setText(self.kind_name(model.get('kind', '')))
        self.model_time_value.setText(unit_symbol(units.get('time', '')))
        self.model_distance_value.setText(unit_symbol(distance or ''))
        self.model_form.setRowVisible(self.model_distance_label, distance is not None)
        self.page_stack.setCurrentWidget(self.model_page)

    def show_selection(self, selection) -> None:
        """Show how much of each kind is selected.

        Parameters
        ----------
        selection : masafi_simtwin.documents.petri_net.Selection
            The places, transitions and arcs selected, as descriptions.
        """

        self._places = ()
        self.places_value.setText(str(len(selection.places)))
        self.transitions_value.setText(str(len(selection.transitions)))
        self.arcs_value.setText(str(len(selection.arcs)))
        self.page_stack.setCurrentWidget(self.selection_page)

    def show_places(self, places, names=()) -> None:
        """Show one place or several, to be edited.

        Parameters
        ----------
        places : collections.abc.Iterable of simtwin_core.petri_net.PlaceData
            The places, one at least.
        names : collections.abc.Iterable of str, optional
            The names of every place and transition of the net, which is what a
            place's new name is checked against — its own left out.
        """

        self._showing = True
        try:
            self._places = tuple(places)
            if len(self._places) == 1:
                place = self._places[0]
                self._taken = tuple(name for name in names if name != place.name)
                self.place_heading.setText(self.tr('Place'))
                self.place_name_edit.setEnabled(True)
                self.place_name_edit.setPlaceholderText('')
                self.place_name_edit.setText(place.name)
            else:
                self._taken = ()
                self.place_heading.setText(self.tr('Places: {0}').format(len(self._places)))
                self.place_name_edit.setEnabled(False)
                self.place_name_edit.clear()
                self.place_name_edit.setPlaceholderText(self.tr('Several places'))
            self._show_name_problem(None)

            tokens = {place.tokens for place in self._places}
            if len(tokens) == 1:
                self.place_tokens_spin.setSpecialValueText('')
                self.place_tokens_spin.setMinimum(0)
                self.place_tokens_spin.setValue(tokens.pop())
            else:
                self.place_tokens_spin.setMinimum(MIXED)
                self.place_tokens_spin.setSpecialValueText(' ')
                self.place_tokens_spin.setValue(MIXED)

            descriptions = {place.description for place in self._places}
            if len(descriptions) == 1:
                self.place_description_edit.setPlaceholderText('')
                self.place_description_edit.setText(descriptions.pop())
            else:
                self.place_description_edit.clear()
                self.place_description_edit.setPlaceholderText(self.tr('Several descriptions'))

            self.page_stack.setCurrentWidget(self.place_page)
        finally:
            self._showing = False

    def kind_name(self, kind: str) -> str:
        """Give what a kind of model is called.

        Parameters
        ----------
        kind : str
            The kind as the manifest stores it, a :class:`ModelKind` value.

        Returns
        -------
        str
            Its translated name, and the stored value for a kind nobody has
            named, so that nothing is hidden.
        """

        names = {
            ModelKind.PETRI_NET.value: self.tr('Petri Net'),
            ModelKind.PROCESS_FLOW.value: self.tr('Process Flow'),
            ModelKind.PROCESS_2D.value: self.tr('2D Process'),
            ModelKind.PROCESS_3D.value: self.tr('3D Process'),
        }
        return names.get(kind, kind)

    def name_problem_text(self, problem: NameProblem) -> str:
        """Say, in a person's words, why a name is refused.

        Parameters
        ----------
        problem : simtwin_core.petri_net.NameProblem
            The rule it breaks.

        Returns
        -------
        str
            The translated sentence.
        """

        texts = {
            NameProblem.EMPTY: self.tr('A name cannot be empty.'),
            NameProblem.NOT_ASCII: self.tr(
                'A name can only use letters without accents, digits and underscores.'
            ),
            NameProblem.DIGIT_FIRST: self.tr('A name cannot start with a digit.'),
            NameProblem.NOT_IDENTIFIER: self.tr(
                'A name can only use letters, digits and underscores, with no spaces.'
            ),
            NameProblem.KEYWORD: self.tr('A Python keyword cannot be a name.'),
            NameProblem.TAKEN: self.tr(
                'Another place or transition already has this name, ignoring case.'
            ),
        }
        return texts[problem]

    # ------------------------------------------------------------------
    # Editing
    # ------------------------------------------------------------------

    def _show_name_problem(self, problem: NameProblem | None) -> None:
        """Say why the name being typed is refused, or say nothing.

        Parameters
        ----------
        problem : simtwin_core.petri_net.NameProblem, optional
            The rule it breaks, or ``None`` when it breaks none.
        """

        self.place_name_problem.setText('' if problem is None else self.name_problem_text(problem))
        self.place_name_problem.setHidden(problem is None)

    def _on_name_edited(self, text: str) -> None:
        """Check a name as it is typed.

        Parameters
        ----------
        text : str
            What the field holds now.
        """

        self._show_name_problem(name_problem(text, self._taken))

    def _on_name_finished(self) -> None:
        """Ask for the name typed, or put back the one the place has."""

        if self._showing or len(self._places) != 1:
            return
        place = self._places[0]
        text = self.place_name_edit.text()
        if text != place.name and name_problem(text, self._taken) is None:
            self.name_asked.emit(place.uuid, text)
            return
        self.place_name_edit.setText(place.name)
        self._show_name_problem(None)

    def _on_tokens_changed(self, value: int) -> None:
        """Ask for the tokens chosen, for every place shown.

        Parameters
        ----------
        value : int
            The tokens, or :data:`MIXED` while nothing has been chosen.
        """

        if self._showing or not self._places or value < 0:
            return
        if all(place.tokens == value for place in self._places):
            return
        self.tokens_asked.emit(tuple(place.uuid for place in self._places), value)

    def _on_description_finished(self) -> None:
        """Ask for the description typed, for every place shown."""

        if self._showing or not self._places:
            return
        text = self.place_description_edit.text()
        several = len({place.description for place in self._places}) > 1
        if several and not text:
            return
        if all(place.description == text for place in self._places):
            return
        self.description_asked.emit(tuple(place.uuid for place in self._places), text)
