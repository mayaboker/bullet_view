import os
import gc

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PySide6 import QtCore, QtWidgets

_APPLICATION = None


@pytest.fixture(scope='session', autouse=True)
def qt_application():
    """Retain the app through interpreter shutdown, as Qt's bindings expect."""
    global _APPLICATION
    _APPLICATION = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    yield _APPLICATION
    # Collect presenter/signal cycles while Qt is still alive, before binding shutdown.
    gc.collect()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)
    _APPLICATION.processEvents()
    gc.collect()
