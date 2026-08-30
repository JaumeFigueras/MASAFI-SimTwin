"""The Arc dialog: what an arc carries.

The layout is :mod:`~masafi_simtwin.dialogs.forms.arc`, compiled from
``forms/arc.ui``.  It asks one question — the weight — because the weight is the
only property a P/T arc has, and it is the interim: when the right-hand
properties pane exists the same question is asked there, of whatever is
selected, and this dialog is what a double click opens until then.
"""

from __future__ import annotations

from PyQt6.QtWidgets import QDialog, QWidget

from masafi_simtwin.dialogs.forms.ui_arc import Ui_ArcDialog


class ArcDialog(QDialog, Ui_ArcDialog):
    """How many tokens an arc carries.

    Parameters
    ----------
    weight : int, optional
        The weight the arc has now, which is what the dialog opens on.
    parent : PyQt6.QtWidgets.QWidget, optional
        Parent widget.
    """

    def __init__(self, weight: int = 1, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setupUi(self)
        self.weight_spin.setValue(max(int(weight), self.weight_spin.minimum()))
        self.weight_spin.selectAll()
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

    @property
    def weight(self) -> int:
        """int: The weight that was chosen."""

        return self.weight_spin.value()
