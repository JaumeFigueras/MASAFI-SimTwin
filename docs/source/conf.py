"""Configuration file for the Sphinx documentation builder.

For the full list of built-in configuration values, see the documentation:
https://www.sphinx-doc.org/en/master/usage/configuration.html

The documentation is written once, in English, and translated through Sphinx's
own gettext: the Catalan catalogues are ``locale/ca/LC_MESSAGES/*.po``, kept up
to date by ``make docs-po``.  Each language is built on its own, with
``-D language=…``, into ``docs/build/html/<language>`` — ``make docs`` builds
them all.  A sentence nobody has translated yet is shown in English.
"""

from importlib.metadata import version as _version

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'MASAFI-SimTwin'
copyright = '2026, Jaume Figueras'
author = 'Jaume Figueras'

# Single source of truth: the installed distribution metadata, which setuptools
# fills in from ``pyproject.toml``.  Building the docs therefore requires the
# package to be installed (``make install``).
release = _version('masafi-simtwin')
version = '.'.join(release.split('.')[:2])

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',
    'sphinx.ext.apidoc',
    'sphinx.ext.intersphinx',
    'sphinx.ext.viewcode',
    'sphinx.ext.todo',
]

templates_path = ['_templates']
exclude_patterns = []

# -- Languages ---------------------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/advanced/intl.html
#
# ``language`` is the one the pages are written in; a build of another passes
# ``-D language=ca``.  ``LANGUAGES`` is what the sidebar offers, each under its
# own name, in the order shown — the application's own idiom.

language = 'en'
locale_dirs = ['locale/']
gettext_compact = False

LANGUAGES = [
    ('en', 'English'),
    ('ca', 'Català'),
]

html_context = {
    'languages': LANGUAGES,
}

# -- To do -------------------------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/extensions/todo.html
#
# Shown while the documentation is being written: every page but the landing
# page says, in a box, what it is going to hold.

todo_include_todos = True

# -- API generation ----------------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/extensions/apidoc.html
#
# The ``developing/api/`` stubs are regenerated on every build and are not
# tracked in git.  The reference is not translated: ``make docs-po`` leaves it
# out of the catalogues, so it reads in English in every language.

apidoc_modules = [
    {
        'path': f'../../src/{package}',
        'destination': f'developing/api/{package}',
        'separate_modules': True,
        'automodule_options': {'members', 'undoc-members', 'show-inheritance'},
        'exclude_patterns': ['**/forms/ui_*'],
    }
    for package in ('masafi_simtwin', 'simtwin_core', 'simtwin_adapters')
]

# -- intersphinx -------------------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/extensions/intersphinx.html
#
# Lets roles such as :exc:`ValueError` resolve to the standard library
# documentation.  The inventory is fetched over the network and cached in the
# doctree directory; an offline build degrades to plain text with a warning
# rather than failing.

intersphinx_mapping = {
    'python': ('https://docs.python.org/3', None),
}

# -- autodoc -----------------------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/extensions/autodoc.html

autodoc_member_order = 'bysource'
autodoc_default_options = {
    'ignore-module-all': True,
}
# Types stay in the rendered signature.  NumPy-style docstrings already spell
# the types out in their ``Parameters`` section, so moving annotations into the
# description would render every parameter type twice.
autodoc_typehints = 'signature'

# -- napoleon ----------------------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/extensions/napoleon.html
#
# NumPy syntax only: Google-style parsing is off so that a malformed NumPy
# docstring fails loudly instead of being silently reinterpreted.

napoleon_numpy_docstring = True
napoleon_google_docstring = False
napoleon_include_init_with_doc = True
napoleon_use_rtype = True
# A frozen dataclass names its fields in an ``Attributes`` section and autodoc
# finds them again as members; as ``:ivar:`` fields the section describes
# them without declaring them a second time.
napoleon_use_ivar = True


def _signal_docstrings(app, what, name, obj, options, lines):
    """Drop the docstring PyQt gives every signal.

    A ``pyqtSignal`` carries PyQt's own explanation of how to declare one,
    the same on every signal of every class and none of it about the signal;
    what a signal says is in the class's ``Signals`` section.
    """

    from PyQt6.QtCore import pyqtSignal

    if isinstance(obj, pyqtSignal):
        lines.clear()


def setup(app):
    app.connect('autodoc-process-docstring', _signal_docstrings)


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'sphinx_rtd_theme'
