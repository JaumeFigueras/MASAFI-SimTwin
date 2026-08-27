"""The application's dialogs, one class per module.

Every dialog is laid out in Qt Designer rather than in code, so that the layout
can be seen and changed by a human.  The ``.ui`` files live in
:mod:`masafi_simtwin.dialogs.forms` beside the ``ui_*.py`` that ``make ui``
compiles from them, and a dialog class inherits the generated ``Ui_`` class:

.. code-block:: python

    class AboutDialog(QDialog, Ui_AboutDialog):
        def __init__(self, parent=None):
            super().__init__(parent)
            self.setupUi(self)

The form carries the structure and the user-facing strings; behaviour, anything
that has to be formatted, and every signal connection stay in the class.  The
theme is not applied here — :class:`~masafi_simtwin.theme.ThemeManager` sets the
palette and stylesheet on the application, so a dialog is themed by inheritance.
Never put a stylesheet in a form: it cannot follow the desktop between light and
dark.
"""

from __future__ import annotations

from masafi_simtwin.dialogs.about import AboutDialog
from masafi_simtwin.dialogs.model import ModelDialog
from masafi_simtwin.dialogs.new_project import NewProjectDialog
from masafi_simtwin.dialogs.restart import ask_to_restart, warn_restart_needed
from masafi_simtwin.dialogs.settings import SettingsDialog

__all__ = [
    'AboutDialog',
    'ModelDialog',
    'NewProjectDialog',
    'SettingsDialog',
    'ask_to_restart',
    'warn_restart_needed',
]
