"""The adapters: the only place a backend library is named.

One subpackage per MASAFI library, each turning what :mod:`simtwin_core`
describes into what that library holds, and back.  The application imports none
of the libraries itself — ``test/test_layers.py`` holds that — so a library can
change, or another can be added, without the application knowing.

Only what has been built is here: :mod:`simtwin_adapters.sim_petri`, over
MASAFI-sim-petri.
"""
