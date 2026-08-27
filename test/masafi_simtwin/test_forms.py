"""Tests for the Qt Designer forms and the modules compiled from them.

These guard the arrangement rather than any one dialog: that no ``ui_*.py``
has drifted from the form it was generated from, and that a form carries only
what a form is allowed to carry.
"""

from __future__ import annotations

import sys
from pathlib import Path
from xml.etree import ElementTree

import pytest

ROOT = Path(__file__).resolve().parents[2]

sys.path.insert(0, str(ROOT / 'tools'))

from build_forms import find_tool, forms, generated, is_current  # noqa: E402

#: The forms, named by their stem so a failure says which one broke.
FORM_IDS = [form.stem for form in forms()]


def test_there_is_at_least_one_form():
    """A silent empty list would make every test below pass for nothing."""

    assert forms()


@pytest.mark.parametrize('form', forms(), ids=FORM_IDS)
def test_the_generated_module_is_in_step_with_its_form(form):
    """``make ui`` has been run since the form was last saved.

    A form saved in Qt Designer changes nothing until it is compiled, so a
    stale module is a change that silently did not happen.
    """

    pyuic = find_tool('pyuic6')
    assert generated(form).exists(), f'{form.name} has never been compiled'
    assert is_current(form, pyuic), f'{form.name} changed; run `make ui`'


@pytest.mark.parametrize('form', forms(), ids=FORM_IDS)
def test_a_form_carries_no_stylesheet(form):
    """Colours come from the theme, never from the form.

    A stylesheet set in Designer is baked into the generated module and cannot
    follow the desktop between light and dark, so the theme would stop applying
    to that widget.
    """

    tree = ElementTree.parse(form)
    styled = [
        element.get('name')
        for element in tree.iter('property')
        if element.get('name') == 'styleSheet'
    ]
    assert not styled, f'{form.name} sets a stylesheet; use the theme instead'


@pytest.mark.parametrize('form', forms(), ids=FORM_IDS)
def test_the_form_class_names_the_context_of_its_strings(form):
    """The ``<class>`` of a form is the ``tr()`` context of the strings in it.

    Naming it after the dialog is what puts the strings of a dialog on one page
    in Qt Linguist, together with the ones its class translates in code.
    """

    root = ElementTree.parse(form).getroot()
    name = root.findtext('class')
    assert name, f'{form.name} has no <class>'
    assert name.endswith('Dialog') or name.endswith('Widget'), (
        f'{form.name} is called {name!r}; name a form after the class that uses it'
    )
