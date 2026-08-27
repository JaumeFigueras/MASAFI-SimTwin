"""Qt Designer forms and the modules ``pyuic6`` compiles from them.

Open a form with ``make designer F=<name>``; recompile with ``make ui`` after
saving.  The ``ui_*.py`` modules are generated — never edit one, the next
``make ui`` overwrites it, and ``make test`` fails when one has drifted from its
form.
"""
