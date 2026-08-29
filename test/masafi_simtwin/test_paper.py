"""Tests for the paper a sheet is ruled into."""

from __future__ import annotations

import pytest
from PyQt6.QtCore import QSizeF
from PyQt6.QtGui import QPageSize

from masafi_simtwin import paper


@pytest.fixture(autouse=True)
def ask_the_machine_again():
    """Let every test start from what this machine actually says.

    The answers are kept once they are worked out, because asking the print
    subsystem is a round trip; a test that puts a different machine in front of
    the same functions has to be able to clear that.
    """

    paper.forget()
    yield
    paper.forget()


def test_the_sizes_offered_have_keys_and_no_repeats():
    """A size with no key cannot be stored, and a list with repeats is a bug."""

    keys = [size.key() for size in paper.installed_sizes()]

    assert keys
    assert all(keys)
    assert len(set(keys)) == len(keys)


def test_a_machine_with_no_printer_is_offered_the_usual_sizes(monkeypatch):
    """Which is an ordinary machine, not a broken one."""

    monkeypatch.setattr(paper, '_printer', lambda: None)
    paper.forget()
    keys = [size.key() for size in paper.installed_sizes()]

    assert keys == [QPageSize(identifier).key() for identifier in paper.FALLBACK_SIZES]
    assert 'A4' in keys


def test_the_printer_is_asked_first(monkeypatch):
    """What this machine prints on beats what is usual anywhere."""

    class OnePaperPrinter:
        def supportedPageSizes(self):  # noqa: N802  (Qt naming)
            return [QPageSize(QPageSize.PageSizeId.Legal)]

        def defaultPageSize(self):  # noqa: N802  (Qt naming)
            return QPageSize(QPageSize.PageSizeId.Legal)

    monkeypatch.setattr(paper, '_printer', OnePaperPrinter)
    paper.forget()

    assert [size.key() for size in paper.installed_sizes()] == ['Legal']
    assert paper.default_key() == 'Legal'


def test_the_machine_is_asked_only_once(monkeypatch):
    """Asking is a round trip to the print subsystem, and it can be a slow one."""

    asked = []
    monkeypatch.setattr(paper, '_printer', lambda: asked.append(True))
    paper.forget()
    paper.installed_sizes()
    paper.installed_sizes()
    paper.default_key()
    paper.default_key()

    assert len(asked) == 2  # once for the sizes, once for the default


def test_with_no_printer_the_locale_decides(monkeypatch):
    """The United States prints on Letter and the rest of the world on A4."""

    from PyQt6.QtCore import QLocale

    monkeypatch.setattr(paper, '_printer', lambda: None)

    class Imperial:
        @staticmethod
        def measurementSystem():  # noqa: N802  (Qt naming)
            return QLocale.MeasurementSystem.ImperialUSSystem

    class Metric:
        @staticmethod
        def measurementSystem():  # noqa: N802  (Qt naming)
            return QLocale.MeasurementSystem.MetricSystem

    monkeypatch.setattr(QLocale, 'system', lambda: Imperial)
    paper.forget()
    assert paper.default_key() == 'Letter'

    monkeypatch.setattr(QLocale, 'system', lambda: Metric)
    paper.forget()
    assert paper.default_key() == 'A4'


def test_a_size_is_found_by_the_key_it_is_stored_under():
    """The key is ASCII and stable, which is what makes it storable."""

    assert paper.size_of('A4').id() == QPageSize.PageSizeId.A4
    assert paper.size_of('Letter').id() == QPageSize.PageSizeId.Letter
    assert paper.size_of('Papyrus') is None
    assert paper.size_of('') is None


def test_a_page_is_given_in_millimetres_the_way_round_it_is_used():
    """The sheet is in millimetres, so this is where a page becomes one."""

    assert paper.dimensions('A4', paper.PORTRAIT) == QSizeF(210.0, 297.0)
    assert paper.dimensions('A4', paper.LANDSCAPE) == QSizeF(297.0, 210.0)
    assert paper.dimensions('A3', paper.PORTRAIT) == QSizeF(297.0, 420.0)


def test_a_page_nobody_can_make_sense_of_falls_back():
    """A settings file can be edited by hand; it cannot leave us without a page."""

    assert paper.dimensions('Papyrus') == paper.dimensions(paper.default_key())
    assert paper.dimensions('A4', 'sideways') == paper.dimensions('A4', paper.PORTRAIT)


def test_a_size_is_named_for_showing():
    """By Qt, which is where the translations of those names are."""

    assert paper.name_of('A4') == QPageSize(QPageSize.PageSizeId.A4).name()
    assert paper.name_of('Papyrus') == 'Papyrus'
