"""Tests for the fonts this machine letters a net in."""

from __future__ import annotations

import pytest
from PyQt6.QtGui import QFont, QFontInfo

from masafi_simtwin import fonts


@pytest.fixture(autouse=True)
def ask_the_machine_again():
    """Let every test start from what this machine actually says.

    The answers are kept once they are worked out, as the paper ones are, so a
    test that puts a different machine in front of the same functions has to be
    able to clear that.
    """

    fonts.forget()
    yield
    fonts.forget()


def test_a_font_nobody_has_is_not_installed():
    """Which is the whole question a document's own font has to be put to."""

    assert not fonts.installed('No Such Font At All')


def test_nothing_is_not_a_font():
    """An empty name resolves to whatever Qt feels like, so it is asked first."""

    assert not fonts.installed('')
    assert not fonts.installed('   ')


def test_the_font_the_application_letters_in_is_installed():
    """Whatever this machine's own is, it is one it has."""

    assert fonts.installed(QFontInfo(QFont()).family())


def test_the_foundry_qt_adds_is_no_part_of_the_name(monkeypatch):
    """``Nimbus Sans`` comes back as ``Nimbus Sans [UKWN]`` and is still it.

    This is the reason the question is asked this way at all: the obvious check,
    whether the family is one of ``QFontDatabase.families()``, answers *no* for
    a font that is installed and draws perfectly well.
    """

    monkeypatch.setattr(fonts, '_resolved', lambda family: 'Nimbus Sans [UKWN]')

    assert fonts.installed('Nimbus Sans')
    assert fonts.installed('nimbus sans')
    assert not fonts.installed('Helvetica')


def test_a_font_that_is_not_there_is_told_apart_by_what_qt_letters_instead(monkeypatch):
    """Qt answers a missing family with the one it would use in its place."""

    monkeypatch.setattr(fonts, '_resolved', lambda family: 'DejaVu Sans')

    assert not fonts.installed('No Such Font At All')
    assert fonts.installed('DejaVu Sans')


def test_the_preferred_font_is_the_default_where_the_machine_has_it(monkeypatch):
    """Nimbus Sans, as agreed, wherever it is installed."""

    monkeypatch.setattr(fonts, 'installed', lambda family: family == fonts.PREFERRED_FONT)
    fonts.forget()

    assert fonts.default_family() == fonts.PREFERRED_FONT


def test_without_it_the_machine_s_own_font_is_the_default(monkeypatch):
    """A machine that lacks it letters in whatever it letters everything in."""

    monkeypatch.setattr(fonts, 'installed', lambda family: False)
    fonts.forget()

    assert fonts.default_family() == QFontInfo(QFont()).family()


def test_there_is_always_a_default_family():
    """Whatever this machine is, something has to be lettered in."""

    assert fonts.default_family()


def test_a_family_is_asked_about_once(monkeypatch):
    """Resolving a font is work, and a net is lettered again at every repaint."""

    asked: list[str] = []

    def resolve(family):
        asked.append(family)
        return 'DejaVu Sans'

    monkeypatch.setattr(fonts, '_resolved', resolve)
    fonts.forget()
    fonts.installed('DejaVu Sans')
    fonts.installed('DejaVu Sans')
    fonts.installed('Another Font')

    assert asked == ['DejaVu Sans', 'Another Font']


def test_the_default_family_is_worked_out_once(monkeypatch):
    """The same, for the question every unstyled item asks."""

    asked: list[str] = []

    monkeypatch.setattr(
        fonts, 'installed', lambda family: bool(asked.append(family))
    )
    fonts.forget()
    fonts.default_family()
    fonts.default_family()

    assert asked == [fonts.PREFERRED_FONT]
