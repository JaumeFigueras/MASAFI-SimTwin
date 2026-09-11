"""The backend-agnostic protocol between the application and the simulation libraries.

:mod:`masafi_simtwin` draws models and :mod:`simtwin_adapters` hands them to a
library; this package is what passes between the two.  So nothing in it imports
Qt, SimPy or a MASAFI library — ``test/test_layers.py`` holds that — and the same
description of a model can be drawn by the one and read by any of the others.

Only what has been built is here: :mod:`simtwin_core.petri_net`, a Petri net as it
is drawn.
"""
