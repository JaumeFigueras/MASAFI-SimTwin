"""The New Project dialog.

The layout is :mod:`~masafi_simtwin.dialogs.forms.new_project`, compiled from
``forms/new_project.ui``: a name, a directory to put it in, and the path those
two add up to, shown as it is typed so that nothing about where the file lands
is a surprise.

The dialog decides nothing but the path.  It validates as the user types and
keeps OK disabled until the answer is a file that can be written, and
:attr:`project_path` is what it leaves behind; the window that opened it is what
writes the project, because that is where a failure has somewhere to be
reported.
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QStandardPaths
from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QFileDialog, QWidget

from masafi_simtwin import project
from masafi_simtwin.dialogs.forms.ui_new_project import Ui_NewProjectDialog


def default_location() -> str:
    """Give the directory a new project is offered in first.

    Returns
    -------
    str
        The user's documents directory, their home directory when there is no
        documents one, and the working directory when there is neither.
    """

    for location in (
        QStandardPaths.StandardLocation.DocumentsLocation,
        QStandardPaths.StandardLocation.HomeLocation,
    ):
        directory = QStandardPaths.writableLocation(location)
        if directory:
            return directory
    return str(Path.cwd())


class NewProjectDialog(QDialog, Ui_NewProjectDialog):
    """Ask where to put a new project and what to call it.

    Parameters
    ----------
    parent : PyQt6.QtWidgets.QWidget, optional
        Parent widget.
    location : str, optional
        The directory to offer first, :func:`default_location` by default.

    Attributes
    ----------
    project_path : pathlib.Path or None
        The file the project is to be written to, once the dialog has been
        accepted.
    """

    def __init__(
        self, parent: QWidget | None = None, location: str | None = None
    ) -> None:
        super().__init__(parent)
        self.setupUi(self)

        self.project_path: Path | None = None

        self.location_edit.setText(location if location else default_location())
        self.name_edit.textChanged.connect(self._revalidate)
        self.location_edit.textChanged.connect(self._revalidate)
        self.browse_button.clicked.connect(self.browse)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        self._revalidate()
        self.name_edit.setFocus()

    # ------------------------------------------------------------------
    # What the two fields add up to
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        """str: The name typed in, without the spaces around it."""

        return self.name_edit.text().strip()

    @property
    def location(self) -> str:
        """str: The directory typed in, without the spaces around it."""

        return self.location_edit.text().strip()

    def target(self) -> Path | None:
        """Give the file the two fields point at.

        Returns
        -------
        pathlib.Path, optional
            The path, or ``None`` while either field is empty.
        """

        if not self.name or not self.location:
            return None
        return project.path_for(self.location, self.name)

    def problem(self) -> str:
        """Say what stands between the dialog and a project, if anything.

        Returns
        -------
        str
            A translated sentence naming the problem, empty when there is none.
        """

        if not self.name:
            return self.tr('Give the project a name.')
        if not self.location:
            return self.tr('Choose where to keep the project.')

        directory = Path(self.location)
        if not directory.is_dir():
            return self.tr('{0} is not a directory.').format(directory)

        target = self.target()
        if target is None:
            return ''
        if target.exists():
            return self.tr('{0} is already there.').format(target.name)
        return ''

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def browse(self) -> None:
        """Choose the directory with a file dialog rather than by typing."""

        directory = QFileDialog.getExistingDirectory(
            self, self.tr('Where to keep the project'), self.location
        )
        if directory:
            self.location_edit.setText(directory)

    def _revalidate(self) -> None:
        """Show the path, show the problem, and let OK follow from both."""

        target = self.target()
        self.path_label.setText(str(target) if target is not None else '')

        problem = self.problem()
        self.message_label.setText(problem)
        button = self.button_box.button(QDialogButtonBox.StandardButton.Ok)
        if button is not None:
            button.setEnabled(not problem)

    def accept(self) -> None:
        """Settle on the path, then close.

        Nothing is written here: the path is what the dialog answers with, and
        the window that opened it does the writing.
        """

        if self.problem():
            return
        self.project_path = self.target()
        super().accept()
