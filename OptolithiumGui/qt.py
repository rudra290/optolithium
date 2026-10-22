#!/usr/bin/env python
# -*- coding: utf-8 -*-

# This file is part of Optolithium lithography modelling software.
#
# Copyright (C) 2015 Alexei Gladkikh
#
# This software is dual-licensed: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version only for NON-COMMERCIAL usage.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301  USA
#
# If you are interested in other licensing models, including a commercial-
# license, please contact the author at gladkikhalexei@gmail.com

import types
import sys

try:
    from PyQt5 import QtCore as _QtCore
    from PyQt5 import QtGui as _PyQtQtGui
    from PyQt5 import QtWidgets as _QtWidgets
    backend_name = 'PyQt5'
    core_version = _QtCore.PYQT_VERSION_STR
    version = _QtCore.PYQT_VERSION_STR
    Signal = _QtCore.pyqtSignal
    Slot = _QtCore.pyqtSlot
    QSlot = _QtCore.pyqtSlot
except ImportError:
    try:
        import PySide
        import PySide.QtCore as _QtCore
        import PySide.QtGui as _PyQtQtGui
        _QtWidgets = _PyQtQtGui
        backend_name = 'PySide'
        core_version = _QtCore.__version__
        version = PySide.__version__
        Signal = _QtCore.Signal
        Slot = _QtCore.Slot
        QSlot = _QtCore.Slot
    except ImportError:
        from PySide2 import QtCore as _QtCore
        from PySide2 import QtGui as _PyQtQtGui
        from PySide2 import QtWidgets as _QtWidgets
        import PySide2
        backend_name = 'PySide2'
        core_version = _QtCore.__version__
        version = PySide2.__version__
        Signal = _QtCore.Signal
        Slot = _QtCore.Slot
        QSlot = _QtCore.Slot

# Composite QtGui module to provide both QtGui and QtWidgets classes (for Qt4/PySide compatibility)
class _QtGuiShim(types.ModuleType):
    def __init__(self, original_gui, original_widgets, original_core):
        super(_QtGuiShim, self).__init__('QtGui')
        self._gui = original_gui
        self._widgets = original_widgets
        self._core = original_core

    def __getattr__(self, name):
        if hasattr(self._widgets, name):
            return getattr(self._widgets, name)
        if hasattr(self._gui, name):
            return getattr(self._gui, name)
        if hasattr(self._core, name):
            return getattr(self._core, name)
        raise AttributeError("module 'QtGui' has no attribute '%s'" % name)

    def __dir__(self):
        return list(set(dir(self._gui) + dir(self._widgets) + dir(self._core)))

QtGui = _QtGuiShim(_PyQtQtGui, _QtWidgets, _QtCore)
QtCore = _QtCore
QtWidgets = _QtWidgets

if hasattr(_QtWidgets, "QHeaderView"):
    if not hasattr(_QtWidgets.QHeaderView, "setClickable"):
        _QtWidgets.QHeaderView.setClickable = lambda self, clickable: self.setSectionsClickable(clickable)
    if not hasattr(_QtWidgets.QHeaderView, "setMovable"):
        _QtWidgets.QHeaderView.setMovable = lambda self, movable: self.setSectionsMovable(movable)
    if not hasattr(_QtWidgets.QHeaderView, "setResizeMode"):
        _QtWidgets.QHeaderView.setResizeMode = lambda self, *args: self.setSectionResizeMode(*args)

# WebKit compatibility shim using QTextBrowser (or QtWebEngineWidgets if available)
class _QWebViewWrapper(_QtWidgets.QTextBrowser):
    def __init__(self, parent=None):
        super(_QWebViewWrapper, self).__init__(parent)
        self.setOpenExternalLinks(True)

    def setHtml(self, html):
        super(_QWebViewWrapper, self).setHtml(html)

    def print_(self, printer):
        super(_QWebViewWrapper, self).print(printer)

class _QtWebKitShim:
    QWebView = _QWebViewWrapper

QtWebKit = _QtWebKitShim()

import helpers
import logging as module_logging

__author__ = 'Alexei Gladkikh'

logging = module_logging.getLogger(__name__)
logging.setLevel(module_logging.INFO)
helpers.logStreamEnable(logging)


def _normalize_slot(slot):
    if type(slot) is not types.MethodType and hasattr(slot, "__self__") and hasattr(slot, "__func__"):
        try:
            return types.MethodType(slot.__func__, slot.__self__)
        except Exception:
            pass
    return slot


def connect(signal, *slots, **kwargs):
    """
    :type signal: Signal
    :type slots: list of Slot
    """
    connection_type = kwargs.get("connection_type", QtCore.Qt.AutoConnection)
    logging.debug("Connect %s with %s" % (signal, slots))
    for slot in slots:
        signal.connect(_normalize_slot(slot), connection_type)


def disconnect(signal, slot):
    """
    :type signal: Signal
    :type slot: Slot
    """
    logging.debug("Disconnect %s with %s" % (signal, slot))
    slot = _normalize_slot(slot)
    try:
        signal.disconnect(slot)
    except (TypeError, RuntimeError) as e:
        logging.debug("Disconnect failed: %s" % e)


class _GlobalSignalsClass(QtCore.QObject):

    changed = Signal()

    @QSlot()
    def onChanged(self):
        self.changed.emit()


GlobalSignals = _GlobalSignalsClass()
