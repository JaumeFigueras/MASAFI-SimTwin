"""The contents of the tool panes that are more than a tree.

A pane's layout is a Qt Designer form under ``forms/``, compiled like a dialog's,
so that a human can see and review it.
"""

from masafi_simtwin.panes.properties import PropertiesPane

__all__ = ['PropertiesPane']
