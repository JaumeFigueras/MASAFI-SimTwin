from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QLibraryInfo
from PyQt6.QtCore import QLocale
from PyQt6.QtCore import  QTranslator
from PyQt6.QtWidgets import QApplication

SUPPORTED_LOCALES = ("en_US", "ca_ES")


def _normalize_locale(loc: QLocale) -> str:
    name = loc.name()  # e.g. "en_US", "ca_ES", "en_GB", "ca_AD"
    if name in SUPPORTED_LOCALES:
        return name

    # Map any English variant to our shipped English
    if name.startswith("en_"):
        return "en_US"

    # Map any Catalan variant to our shipped Catalan
    if name.startswith("ca_"):
        return "ca_ES"

    # Default fallback
    return "en_US"


def install_translators(app: QApplication, locale: QLocale | None = None) -> str:
    """
    Loads:
      1) Qt base translations (optional)
      2) App translations from: src/masafi_simtwin/i18n/<lang>/masafi_simtwin.qm

    Returns the locale actually selected (e.g. "en_US" or "ca_ES").
    """
    selected = _normalize_locale(locale or QLocale.system())

    # 1) Qt base translations (dialogs, standard buttons)
    qt_translator = QTranslator(app)
    qt_translator.load(QLocale(selected), "qtbase", "_", QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath))
    app.installTranslator(qt_translator)

    # 2) App translations
    app_translator = QTranslator(app)
    qm_path = Path(__file__).parent / "i18n" / selected / "masafi_simtwin.qm"
    if qm_path.exists() and app_translator.load(str(qm_path)):
        app.installTranslator(app_translator)

    return selected