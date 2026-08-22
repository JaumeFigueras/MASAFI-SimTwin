"""MASAFI-SimTwin — the graphical frontend of the MASAFI simulation libraries.

This package holds the Qt shell and every piece of GUI code.  Nothing here may
import SimPy or a ``MASAFI-*`` simulation library: the frontend talks only to
the backend agnostic protocol in :mod:`simtwin_core`, which the packages under
:mod:`simtwin_adapters` implement on top of a concrete library.
"""

from __future__ import annotations

__version__ = '0.1.0'

APPLICATION_NAME = 'MASAFI-SimTwin'
ORGANISATION_NAME = 'MASAFI'
ORGANISATION_DOMAIN = 'masafi.local'

__all__ = [
    'APPLICATION_NAME',
    'ORGANISATION_DOMAIN',
    'ORGANISATION_NAME',
    '__version__',
]
