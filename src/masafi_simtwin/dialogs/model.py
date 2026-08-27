"""The dialog behind *New Model* and *Model Properties*.

One form serves both, because they ask the same questions.  What changes is
which of them can still be answered: a model's **kind** is settled when it is
created, so on an existing model the type chooser is shown but disabled — the
answer stays visible, and the fact that it cannot be changed is visible with it.

The distance unit follows the kind rather than the user: a Petri net and a
process flow are graphs, whose blocks have no position that means anything, so
the chooser is disabled and says why.  The units start at the application's own
defaults, which is what makes a new model agree with the settings unless the
user says otherwise.

Kinds that cannot be built yet are refused on *OK* rather than hidden from the
list, so that the shape of what is coming is visible without pretending it
works.
"""

from __future__ import annotations

from PyQt6.QtWidgets import QComboBox, QDialog, QDialogButtonBox, QMessageBox, QWidget

from masafi_simtwin import project
from masafi_simtwin.dialogs.forms.ui_model import Ui_ModelDialog
from masafi_simtwin.preferences import DISTANCE_UNITS, TIME_UNITS, Preferences

#: What the entries of the type chooser stand for, in the order they are in the
#: form.  Adding an entry in Designer means adding its kind here; the dialog
#: refuses to open when the two disagree.
KIND_VALUES: tuple[project.ModelKind, ...] = (
    project.ModelKind.PETRI_NET,
    project.ModelKind.PROCESS_FLOW,
    project.ModelKind.PROCESS_2D,
    project.ModelKind.PROCESS_3D,
)


class ModelDialog(QDialog, Ui_ModelDialog):
    """Ask what a model is called, what kind it is, and what it is measured in.

    Parameters
    ----------
    parent : PyQt6.QtWidgets.QWidget, optional
        Parent widget.
    preferences : masafi_simtwin.preferences.Preferences, optional
        Where the default units come from.  The application's own are used when
        it is omitted.
    model : dict, optional
        The model being changed.  Omitted for a new one, which is what decides
        between the dialog's two titles and whether the kind can be chosen.
    taken : list of str, optional
        The names of the project's other models, which this one may not reuse.

    Attributes
    ----------
    editing : bool
        Whether an existing model is being changed rather than a new one made.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        preferences: Preferences | None = None,
        model: dict | None = None,
        taken: list[str] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setupUi(self)

        self.editing = model is not None
        self._taken = {name.strip().casefold() for name in (taken or [])}
        settings = preferences if preferences is not None else Preferences()

        self._fill(self.kind_combo, [kind.value for kind in KIND_VALUES])
        self._fill(self.time_combo, TIME_UNITS)
        self._fill(self.distance_combo, DISTANCE_UNITS)

        if self.editing:
            self.setWindowTitle(self.tr('Model Properties'))
            self.name_edit.setText(model.get('name', ''))
            self.kind_combo.setCurrentIndex(
                self.kind_combo.findData(model.get('kind'))
            )
            self.kind_combo.setEnabled(False)
            units = model.get('units') or {}
            self._select(self.time_combo, units.get('time'), settings, 'units/time')
            self._select(
                self.distance_combo, units.get('distance'), settings, 'units/distance'
            )
        else:
            self._select(self.time_combo, None, settings, 'units/time')
            self._select(self.distance_combo, None, settings, 'units/distance')

        self.name_edit.textChanged.connect(self._revalidate)
        self.kind_combo.currentIndexChanged.connect(self._on_kind_chosen)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        self._on_kind_chosen(self.kind_combo.currentIndex())
        self.name_edit.setFocus()

    # ------------------------------------------------------------------
    # Construction helpers
    # ------------------------------------------------------------------

    def _fill(self, combo: QComboBox, values) -> None:
        """Pair a combo box's entries with what they stand for.

        Parameters
        ----------
        combo : PyQt6.QtWidgets.QComboBox
            The combo box in the form.
        values : iterable
            One value per entry, in the order the entries are in.

        Raises
        ------
        RuntimeError
            When the form has a different number of entries than there are
            values for them.
        """

        values = list(values)
        if combo.count() != len(values):
            raise RuntimeError(
                f'{combo.objectName()} has {combo.count()} entries and there are '
                f'{len(values)} values to pair them with: {values}'
            )
        for index, value in enumerate(values):
            combo.setItemData(index, value)

    def _select(
        self, combo: QComboBox, value, settings: Preferences, key: str
    ) -> None:
        """Put a combo box on a value, or on the application's default for it.

        Parameters
        ----------
        combo : PyQt6.QtWidgets.QComboBox
            The combo box.
        value : object
            What to select, or ``None`` to fall back to the preference.
        settings : masafi_simtwin.preferences.Preferences
            Where the fallback comes from.
        key : str
            The preference holding it.
        """

        index = combo.findData(value if value is not None else settings.value(key))
        combo.setCurrentIndex(max(index, 0))

    # ------------------------------------------------------------------
    # What the fields add up to
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        """str: The name typed in, without the spaces around it."""

        return self.name_edit.text().strip()

    @property
    def kind(self) -> project.ModelKind:
        """masafi_simtwin.project.ModelKind: The kind chosen."""

        return project.ModelKind(self.kind_combo.currentData())

    def units(self) -> dict:
        """Give the units the model is to be expressed in.

        Returns
        -------
        dict
            ``time`` always; ``distance`` only for the kinds it applies to, so
            that a Petri net does not carry a setting that means nothing.
        """

        units = {'time': self.time_combo.currentData()}
        if self.kind in project.KINDS_WITH_DISTANCE:
            units['distance'] = self.distance_combo.currentData()
        return units

    def problem(self) -> str:
        """Say what stands between the dialog and a model, if anything.

        Returns
        -------
        str
            A translated sentence naming the problem, empty when there is none.
        """

        if not self.name:
            return self.tr('Give the model a name.')
        if self.name.strip().casefold() in self._taken:
            return self.tr('The project already holds a model called {0}.').format(self.name)
        return ''

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_kind_chosen(self, _index: int) -> None:
        """Let the kind decide whether a distance unit applies.

        Parameters
        ----------
        _index : int
            The entry that is now current, which is read back off the combo.
        """

        applies = self.kind in project.KINDS_WITH_DISTANCE
        self.distance_label.setEnabled(applies)
        self.distance_combo.setEnabled(applies)
        self.distance_note.setVisible(not applies)
        self._revalidate()

    def _revalidate(self) -> None:
        """Show the problem, and let OK follow from it."""

        problem = self.problem()
        self.message_label.setText(problem)
        button = self.button_box.button(QDialogButtonBox.StandardButton.Ok)
        if button is not None:
            button.setEnabled(not problem)

    def accept(self) -> None:
        """Close, unless the kind chosen is one that cannot be built yet."""

        if self.problem():
            return
        if not self.editing and self.kind not in project.IMPLEMENTED_KINDS:
            QMessageBox.information(
                self,
                self.tr('Not implemented yet'),
                self.tr('{0} models cannot be built yet.').format(
                    self.kind_combo.currentText()
                ),
                QMessageBox.StandardButton.Ok,
            )
            return
        super().accept()
