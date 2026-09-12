"""The Properties pane: what is selected on the current sheet, or the model it is.

The layout is :mod:`~masafi_simtwin.panes.forms.ui_properties`, compiled from
``forms/properties.ui``: a stack of pages, one shown at a time.

* **Nothing** — no model is open, or the tab being looked at is not a model.
* **Model** — a model is open and nothing on its sheet is selected: its name, its
  kind and its units, read-only, as decided with Jaume.
* **Node** — places alone, or transitions alone, selected: the name and the
  description, and a place's initial tokens, to be edited.  One page for both
  kinds, a transition being a place without tokens: the tokens row is shown only
  when every node shown is a place.  With several nodes the name cannot be
  edited, and a field they do not agree on is left blank.
* **Arc** — arcs alone selected: the weight, to be edited, and for one arc the
  names of the nodes it runs between.  Its shape and its kind are chosen on the
  arc tool bar and are not repeated here.
* **Selection** — anything else, a mix of kinds among it: how many places,
  transitions and arcs.

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
from simtwin_core.petri_net import NameProblem, PlaceData, name_problem

#: How a unit whose stored value is not its symbol is written.  The values are
#: kept to ASCII so the settings file needs no encoding; the microsecond's symbol
#: is not.
UNIT_SYMBOLS: dict[str, str] = {'us': 'µs'}

#: What the tokens field holds while the places shown do not agree on theirs: one
#: below the fewest tokens there can be, drawn as a blank.
MIXED = -1

#: What the weight field holds while the arcs shown do not agree on theirs: one
#: below the lightest an arc can be, drawn as a blank.
MIXED_WEIGHT = 0


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
        Emitted with a node's UUID and the name it is to be given, once editing
        of a name the rule allows has ended.
    tokens_asked : PyQt6.QtCore.pyqtSignal
        Emitted with the UUIDs of the places shown and the tokens they are all
        to hold.
    description_asked : PyQt6.QtCore.pyqtSignal
        Emitted with the UUIDs of the nodes shown and the description they are
        all to have.
    weight_asked : PyQt6.QtCore.pyqtSignal
        Emitted with the UUIDs of the arcs shown and the weight they are all to
        carry.
    """

    name_asked = pyqtSignal(str, str)
    tokens_asked = pyqtSignal(object, int)
    description_asked = pyqtSignal(object, str)
    weight_asked = pyqtSignal(object, int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setupUi(self)

        #: The nodes on the node page, and the names the one shown may not take.
        self._nodes: tuple = ()
        self._taken: tuple[str, ...] = ()
        #: The arcs on the arc page.
        self._arcs: tuple = ()
        #: Set while fields are filled in, so that filling one is not an edit.
        self._showing = False

        self.node_name_edit.textEdited.connect(self._on_name_edited)
        self.node_name_edit.editingFinished.connect(self._on_name_finished)
        self.node_tokens_spin.setKeyboardTracking(False)
        self.node_tokens_spin.valueChanged.connect(self._on_tokens_changed)
        self.node_description_edit.editingFinished.connect(self._on_description_finished)
        self.arc_weight_spin.setKeyboardTracking(False)
        self.arc_weight_spin.valueChanged.connect(self._on_weight_changed)

        self.show_nothing()

    @property
    def page(self) -> QWidget:
        """PyQt6.QtWidgets.QWidget: The page being shown."""

        return self.page_stack.currentWidget()

    @property
    def _places_shown(self) -> bool:
        """bool: Whether every node on the node page is a place, which holds tokens."""

        return bool(self._nodes) and all(isinstance(node, PlaceData) for node in self._nodes)

    # ------------------------------------------------------------------
    # What is shown
    # ------------------------------------------------------------------

    def show_nothing(self) -> None:
        """Show that there is no model to say anything about."""

        self._nodes = self._arcs = ()
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
        self._nodes = self._arcs = ()
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

        self._nodes = self._arcs = ()
        self.places_value.setText(str(len(selection.places)))
        self.transitions_value.setText(str(len(selection.transitions)))
        self.arcs_value.setText(str(len(selection.arcs)))
        self.page_stack.setCurrentWidget(self.selection_page)

    def show_nodes(self, nodes, names=()) -> None:
        """Show one place or transition, or several of one kind, to be edited.

        Parameters
        ----------
        nodes : collections.abc.Iterable
            The nodes, one at least, all places or all transitions —
            :class:`~simtwin_core.petri_net.PlaceData` or
            :class:`~simtwin_core.petri_net.TransitionData`.
        names : collections.abc.Iterable of str, optional
            The names of every place and transition of the net, which is what a
            node's new name is checked against — its own left out.
        """

        self._showing = True
        try:
            self._arcs = ()
            self._nodes = tuple(nodes)
            places = self._places_shown
            if len(self._nodes) == 1:
                node = self._nodes[0]
                self._taken = tuple(name for name in names if name != node.name)
                self.node_heading.setText(self.tr('Place') if places else self.tr('Transition'))
                self.node_name_edit.setEnabled(True)
                self.node_name_edit.setPlaceholderText('')
                self.node_name_edit.setText(node.name)
            else:
                self._taken = ()
                count = len(self._nodes)
                self.node_heading.setText(
                    self.tr('Places: {0}').format(count)
                    if places
                    else self.tr('Transitions: {0}').format(count)
                )
                self.node_name_edit.setEnabled(False)
                self.node_name_edit.clear()
                self.node_name_edit.setPlaceholderText(
                    self.tr('Several places') if places else self.tr('Several transitions')
                )
            self._show_name_problem(None)

            self.node_form.setRowVisible(self.node_tokens_label, places)
            tokens = {node.tokens for node in self._nodes} if places else {0}
            if len(tokens) == 1:
                self.node_tokens_spin.setSpecialValueText('')
                self.node_tokens_spin.setMinimum(0)
                self.node_tokens_spin.setValue(tokens.pop())
            else:
                self.node_tokens_spin.setMinimum(MIXED)
                self.node_tokens_spin.setSpecialValueText(' ')
                self.node_tokens_spin.setValue(MIXED)

            descriptions = {node.description for node in self._nodes}
            if len(descriptions) == 1:
                self.node_description_edit.setPlaceholderText('')
                self.node_description_edit.setText(descriptions.pop())
            else:
                self.node_description_edit.clear()
                self.node_description_edit.setPlaceholderText(self.tr('Several descriptions'))

            self.page_stack.setCurrentWidget(self.node_page)
        finally:
            self._showing = False

    def show_arcs(self, arcs, node_names=()) -> None:
        """Show one arc or several, to be edited.

        Parameters
        ----------
        arcs : collections.abc.Iterable of simtwin_core.petri_net.ArcData
            The arcs, one at least.
        node_names : collections.abc.Iterable, optional
            Every node of the net as a ``(uuid, name)`` pair, which is how the
            ends of one arc are named.  With several arcs no ends are shown.
        """

        names = dict(node_names)
        self._showing = True
        try:
            self._nodes = ()
            self._arcs = tuple(arcs)
            one = len(self._arcs) == 1
            if one:
                arc = self._arcs[0]
                self.arc_heading.setText(self.tr('Arc'))
                self.arc_source_value.setText(names.get(arc.source, ''))
                self.arc_target_value.setText(names.get(arc.target, ''))
            else:
                self.arc_heading.setText(self.tr('Arcs: {0}').format(len(self._arcs)))
            self.arc_form.setRowVisible(self.arc_source_label, one)
            self.arc_form.setRowVisible(self.arc_target_label, one)

            weights = {arc.weight for arc in self._arcs}
            if len(weights) == 1:
                self.arc_weight_spin.setSpecialValueText('')
                self.arc_weight_spin.setMinimum(1)
                self.arc_weight_spin.setValue(weights.pop())
            else:
                self.arc_weight_spin.setMinimum(MIXED_WEIGHT)
                self.arc_weight_spin.setSpecialValueText(' ')
                self.arc_weight_spin.setValue(MIXED_WEIGHT)

            self.page_stack.setCurrentWidget(self.arc_page)
        finally:
            self._showing = False

    def focus_weight(self) -> None:
        """Put the cursor in the weight, ready to be typed over."""

        self.arc_weight_spin.setFocus()
        self.arc_weight_spin.selectAll()

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

        self.node_name_problem.setText('' if problem is None else self.name_problem_text(problem))
        self.node_name_problem.setHidden(problem is None)

    def _on_name_edited(self, text: str) -> None:
        """Check a name as it is typed.

        Parameters
        ----------
        text : str
            What the field holds now.
        """

        self._show_name_problem(name_problem(text, self._taken))

    def _on_name_finished(self) -> None:
        """Ask for the name typed, or put back the one the node has."""

        if self._showing or len(self._nodes) != 1:
            return
        node = self._nodes[0]
        text = self.node_name_edit.text()
        if text != node.name and name_problem(text, self._taken) is None:
            self.name_asked.emit(node.uuid, text)
            return
        self.node_name_edit.setText(node.name)
        self._show_name_problem(None)

    def _on_tokens_changed(self, value: int) -> None:
        """Ask for the tokens chosen, for every place shown.

        Parameters
        ----------
        value : int
            The tokens, or :data:`MIXED` while nothing has been chosen.
        """

        if self._showing or not self._places_shown or value < 0:
            return
        if all(node.tokens == value for node in self._nodes):
            return
        self.tokens_asked.emit(tuple(node.uuid for node in self._nodes), value)

    def _on_weight_changed(self, value: int) -> None:
        """Ask for the weight chosen, for every arc shown.

        Parameters
        ----------
        value : int
            The weight, or :data:`MIXED_WEIGHT` while nothing has been chosen.
        """

        if self._showing or not self._arcs or value < 1:
            return
        if all(arc.weight == value for arc in self._arcs):
            return
        self.weight_asked.emit(tuple(arc.uuid for arc in self._arcs), value)

    def _on_description_finished(self) -> None:
        """Ask for the description typed, for every node shown."""

        if self._showing or not self._nodes:
            return
        text = self.node_description_edit.text()
        several = len({node.description for node in self._nodes}) > 1
        if several and not text:
            return
        if all(node.description == text for node in self._nodes):
            return
        self.description_asked.emit(tuple(node.uuid for node in self._nodes), text)
