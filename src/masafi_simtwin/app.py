"""
Custom QApplication subclass.

Responsibilities
----------------
* Load and install the correct ``QTranslator`` for the system locale.
* Detect the OS colour scheme (light / dark) on startup and on change.
* Apply a matching ``QPalette`` to the Fusion style engine.
"""

from pathlib import Path

from PyQt6.QtCore import QLocale, QTranslator, Qt
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QApplication

_I18N_DIR = Path(__file__).parent / "i18n"


class MasafiSimTwinApplication(QApplication):
    """
    Masafi-SimTwin application object.

    Parameters
    ----------
    argv : list[str]
        Command-line arguments (pass ``sys.argv``).
    """

    def __init__(self, argv: list[str]) -> None:
        super().__init__(argv)
        self.setApplicationName("Masafi-SimTwin")
        self.setApplicationVersion("0.1.0")
        self.setOrganizationName("YourOrganisation")
        self.setOrganizationDomain("yourorg.example.com")

        # Fusion is required for full custom QPalette support on all platforms.
        self.setStyle("Fusion")

        self._translator = QTranslator(self)
        self._install_translator()

        hints = self.styleHints()
        if hasattr(hints, "colorSchemeChanged"):
            hints.colorSchemeChanged.connect(self._on_color_scheme_changed)
        self._refresh_palette()

    # ------------------------------------------------------------------
    # Internationalisation
    # ------------------------------------------------------------------

    def _install_translator(self) -> None:
        """
        Load the QM file that best matches the current system locale.

        Falls back silently to the source strings (English) when no
        matching compiled translation file is found.
        """
        locale   = QLocale.system().name()          # e.g. "es_ES", "de_DE"
        qm_path  = _I18N_DIR / f"masafi_simtwin_{locale}.qm"
        if self._translator.load(str(qm_path)):
            self.installTranslator(self._translator)

    # ------------------------------------------------------------------
    # Theming
    # ------------------------------------------------------------------

    def _on_color_scheme_changed(self, scheme: Qt.ColorScheme) -> None:
        """
        Respond to an OS colour-scheme change.

        Parameters
        ----------
        scheme : Qt.ColorScheme
            The new colour scheme reported by the OS.
        """
        self._refresh_palette()

    def _refresh_palette(self) -> None:
        """
        Detect the current OS colour scheme and apply a matching palette.

        Uses ``QStyleHints.colorScheme`` (Qt 6.5+).  Falls back to
        palette-luminance detection on older Qt releases.
        """
        hints = self.styleHints()
        if hasattr(hints, "colorScheme") and hasattr(Qt, "ColorScheme"):
            is_dark = hints.colorScheme() == Qt.ColorScheme.Dark
        else:
            bg = self.palette().color(QPalette.ColorRole.Window)
            is_dark = bg.lightness() < 128

        self.setPalette(_dark_palette() if is_dark else self.style().standardPalette())


# ---------------------------------------------------------------------------
# Dark palette factory
# ---------------------------------------------------------------------------

def _dark_palette() -> QPalette:
    """
    Build a dark ``QPalette`` suited to the Fusion style engine.

    Returns
    -------
    QPalette
        A fully specified dark-mode palette.
    """
    p = QPalette()
    r = QPalette.ColorRole
    g = QPalette.ColorGroup

    p.setColor(r.Window,          QColor( 53,  53,  53))
    p.setColor(r.WindowText,      QColor(255, 255, 255))
    p.setColor(r.Base,            QColor( 35,  35,  35))
    p.setColor(r.AlternateBase,   QColor( 53,  53,  53))
    p.setColor(r.ToolTipBase,     QColor( 25,  25,  25))
    p.setColor(r.ToolTipText,     QColor(255, 255, 255))
    p.setColor(r.Text,            QColor(255, 255, 255))
    p.setColor(r.Button,          QColor( 53,  53,  53))
    p.setColor(r.ButtonText,      QColor(255, 255, 255))
    p.setColor(r.BrightText,      QColor(255,   0,   0))
    p.setColor(r.Link,            QColor( 42, 130, 218))
    p.setColor(r.Highlight,       QColor( 42, 130, 218))
    p.setColor(r.HighlightedText, QColor( 35,  35,  35))
    p.setColor(r.Mid,             QColor(100, 100, 100))
    p.setColor(r.Midlight,        QColor( 75,  75,  75))
    p.setColor(r.Dark,            QColor( 35,  35,  35))
    p.setColor(r.Shadow,          QColor( 20,  20,  20))

    for role in (r.WindowText, r.Text, r.ButtonText):
        p.setColor(g.Disabled, role, QColor(127, 127, 127))

    return p