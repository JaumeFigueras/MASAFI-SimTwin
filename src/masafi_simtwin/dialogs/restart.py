"""The two messages that surround a preference which only takes effect at start-up.

These are ``QMessageBox`` rather than Qt Designer forms.  A form is for a dialog
that has been *laid out* — a tree beside a stack of pages, a logo beside a
version — and there is nothing to lay out in a sentence and two buttons.  Using
the standard box also gets the icon, the platform's button order and Qt's own
translations for anything but the two buttons named here.

The order of the two is what the user is told to expect: the notice goes up as
soon as such a preference is changed, saying that the question will follow, and
the question goes up once the settings dialog has closed.
"""

from __future__ import annotations

from PyQt6.QtCore import QCoreApplication
from PyQt6.QtWidgets import QMessageBox, QWidget

from masafi_simtwin import APPLICATION_NAME


def warn_restart_needed(parent: QWidget | None = None) -> None:
    """Say that what was just changed will not take effect until a restart.

    Shown while the settings dialog is still open, so that the question that
    comes after it is not a surprise.

    Parameters
    ----------
    parent : PyQt6.QtWidgets.QWidget, optional
        The widget to centre the message on, the settings dialog itself.
    """

    translate = QCoreApplication.translate
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Information)
    box.setWindowTitle(translate('RestartMessages', 'Restart needed'))
    box.setText(
        translate(
            'RestartMessages',
            'This change needs the application to be restarted before it takes '
            'effect.',
        )
    )
    box.setInformativeText(
        translate('RestartMessages', 'You will be asked to restart when the settings are closed.')
    )
    box.setStandardButtons(QMessageBox.StandardButton.Ok)
    box.exec()


def ask_to_restart(parent: QWidget | None = None) -> bool:
    """Ask whether to start the application again now.

    Parameters
    ----------
    parent : PyQt6.QtWidgets.QWidget, optional
        The widget to centre the question on, the main window.

    Returns
    -------
    bool
        True when the user asked to restart now, False when they chose to wait.
    """

    translate = QCoreApplication.translate
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Question)
    box.setWindowTitle(translate('RestartMessages', 'Restart {0}').format(APPLICATION_NAME))
    box.setText(
        translate('RestartMessages', 'The settings you changed take effect when the application starts.')
    )
    box.setInformativeText(translate('RestartMessages', 'Restart now?'))

    now = box.addButton(
        translate('RestartMessages', 'Restart Now'), QMessageBox.ButtonRole.AcceptRole
    )
    later = box.addButton(
        translate('RestartMessages', 'Later', 'postpone the restart'),
        QMessageBox.ButtonRole.RejectRole,
    )
    box.setDefaultButton(now)
    box.setEscapeButton(later)
    box.exec()
    return box.clickedButton() is now
