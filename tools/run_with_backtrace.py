"""Run the application, printing a C backtrace if it dies on a fatal signal.

``PYTHONFAULTHANDLER=1`` prints the *Python* stack a crash happened on, which
says which of our code was running.  When the answer is "the event loop" the
crash is inside Qt's own C++, with no Python frame to name, and the Python stack
says nothing more.  This adds the other half: glibc's ``backtrace`` prints the
frames of the C stack, which names the library — and, where symbols survive, the
function — the process actually died in.

Run it in place of ``make run``::

    PYTHONPATH=src .venv/bin/python tools/run_with_backtrace.py

The Qt libraries in the PyQt6 wheels are stripped, so most frames come out as a
library and an offset rather than a name.  That is still the answer to the
question this tool is for: *whose code was it?*
"""

from __future__ import annotations

import ctypes
import ctypes.util
import faulthandler
import os
import signal
import sys

#: How many frames to print.  A Qt stack is deep and the interesting part is the
#: top of it.
FRAMES = 64

#: The handlers, kept alive: a callback that is garbage collected while the
#: signal it serves is still armed is a second crash on top of the first.
_handlers: list = []

#: What ``signal(2)`` calls the default disposition.
SIG_DFL = 0


def install(signals=(signal.SIGSEGV, signal.SIGABRT, signal.SIGBUS, signal.SIGFPE)) -> None:
    """Print a C backtrace on a fatal signal, then die of it as usual.

    Parameters
    ----------
    signals : tuple of int, optional
        The signals to answer.
    """

    libc = ctypes.CDLL(ctypes.util.find_library('c'), use_errno=True)
    buffer = (ctypes.c_void_p * FRAMES)()
    handler_type = ctypes.CFUNCTYPE(None, ctypes.c_int)

    def on_signal(number: int) -> None:
        """Print the C stack, then let the signal do what it was going to do.

        Parameters
        ----------
        number : int
            The signal that arrived.
        """

        os.write(2, f'\n--- C backtrace on signal {number} ---\n'.encode())
        depth = libc.backtrace(buffer, FRAMES)
        libc.backtrace_symbols_fd(buffer, depth, 2)
        os.write(2, b'--- end of C backtrace ---\n')
        #  Put the *C* handler back, not Python's: this one was armed through
        #  libc, so signal.signal() would leave it in place and the re-raise
        #  below would land here again, for ever.
        libc.signal(number, SIG_DFL)
        os.kill(os.getpid(), number)

    handler = handler_type(on_signal)
    _handlers.append(handler)
    for number in signals:
        libc.signal(number, handler)


if __name__ == '__main__':
    faulthandler.enable()
    install()
    from masafi_simtwin.application import main

    sys.exit(main(sys.argv))
