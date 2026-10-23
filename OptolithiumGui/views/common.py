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

import sys
import math
import os
import threading
import traceback
import logging as module_logging
from collections import deque

from qt import QtGui, QtCore, connect, disconnect, Signal, QSlot, GlobalSignals, backend_name

from metrics import MetricNotImplementedError

from resources import Resources
# from database.base import Float, Integer

from config import APPLICATION_NAME, KILOBYTE, MEGABYTE, GIGABYTE

from numpy import isnan
from matplotlib import rcParams
from matplotlib.colors import LinearSegmentedColormap

try:
    from matplotlib import colormaps
    register_cmap = colormaps.register
except (ImportError, AttributeError):
    try:
        from matplotlib.cm import register_cmap
    except (ImportError, AttributeError):
        from matplotlib.pyplot import register_cmap

try:
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.backends.backend_qtagg import NavigationToolbar2QT
except ImportError:
    try:
        from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
        from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT
    except ImportError:
        from matplotlib.backends.backend_qt4agg import FigureCanvasQTAgg as FigureCanvas
        from matplotlib.backends.backend_qt4agg import NavigationToolbar2QT

from matplotlib.figure import Figure

import config
import helpers
import options

from options.structures import get_field


__author__ = 'Alexei Gladkikh'


logging = module_logging.getLogger(__name__)
logging.setLevel(module_logging.INFO)
helpers.logStreamEnable(logging)


NavigationToolbar = NavigationToolbar2QT
msgBox = QtGui.QMessageBox


ProlithColormap = LinearSegmentedColormap.from_list("prolith", ["#0000FF", "#00FFFF", "#00FF00", "#FFFF00", "#FF6209"])
register_cmap(cmap=ProlithColormap)


# noinspection PyPep8Naming
def QuestionBox(parent, message, buttons=msgBox.Yes | msgBox.No, default=msgBox.Yes):
    """
    :type parent: QtGui.QWidget
    :type message: str
    :type buttons: int
    :type default: int
    :rtype: int
    """
    # noinspection PyCallByClass,PyTypeChecker
    return msgBox.question(parent, APPLICATION_NAME, message, buttons, default)


# noinspection PyPep8Naming
def WarningBox(parent, message):
    """
    :type parent: QtGui.QWidget
    :type message: str
    :rtype: int
    """
    # noinspection PyCallByClass,PyTypeChecker
    return msgBox.warning(parent, APPLICATION_NAME, message, msgBox.Ok)


# noinspection PyPep8Naming
def ErrorBox(parent, message):
    """
    :type parent: QtGui.QWidget
    :type message: str
    :rtype: int
    """
    # noinspection PyCallByClass,PyTypeChecker
    return msgBox.critical(parent, APPLICATION_NAME, message, msgBox.Ok)


# noinspection PyPep8Naming
def InformationBox(parent, message, buttons=msgBox.Abort, default=msgBox.Abort):
    """
    :type parent: QtGui.QWidget
    :type message: str
    :type buttons: int
    :type default: int
    :rtype: int
    """
    # noinspection PyCallByClass,PyTypeChecker
    return msgBox.information(parent, APPLICATION_NAME, message, buttons, default)


class ExtendedErrorBox(msgBox):
    def __init__(self, title, message, info):
        # noinspection PyCallByClass
        msgBox.__init__(self)
        self.setWindowTitle("%s error" % APPLICATION_NAME)
        self.setText(title)
        self.setInformativeText(message)
        self.setStandardButtons(msgBox.Close | msgBox.Ok)
        self.setDefaultButton(msgBox.Ok)
        self.setIcon(msgBox.Warning)
        self.setWindowIcon(Resources("icons/Logo"))
        # exc_type, exc_value, exc_traceback = sys.exc_info()
        # exc_string = traceback.format_tb(exc_traceback)
        self.setDetailedText(info)


class QTracebackMessageBox(msgBox):
    def __init__(self):
        # noinspection PyCallByClass
        msgBox.__init__(self)
        self.setWindowTitle("%s runtime error" % APPLICATION_NAME)
        self.setText("An error has occurred during perform action!")
        self.setInformativeText(traceback.format_exc(limit=1))
        self.setStandardButtons(msgBox.Close | msgBox.Ok)
        self.setDefaultButton(msgBox.Ok)
        self.setIcon(msgBox.Warning)
        self.setWindowIcon(Resources("icons/Logo"))
        exc_type, exc_value, exc_traceback = sys.exc_info()
        exc_string = traceback.format_tb(exc_traceback)
        self.setDetailedText("\n".join(exc_string))


def show_traceback(function):

    def wrapped(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except:
            msg_box = QTracebackMessageBox()
            reply = msg_box.exec_()
            if reply == msgBox.Close:
                sys.exit(1)
            raise

    return wrapped


def rgbf(color):
    """
    Converts QColor to RGB float.

    :rtype: float, float, float
    """
    return color.red()/255.0, color.green()/255.0, color.blue()/255.0


class QSliderNumeric(QtGui.QSlider):

    def __init__(self, parent, p_object=None, abstract_field=options.Numeric, orientation=QtCore.Qt.Vertical):
        """
        :type parent: QtGui.QWidget
        :type p_object: options.Variable or None
        :type abstract_field: options.Numeric
        """
        QtGui.QSlider.__init__(self, orientation, parent)

        self.__p_object = None
        self.__field = None

        if p_object is not None:
            self.setObject(p_object, abstract_field)

        connect(self.valueChanged, self.__onValueChanged)

    # noinspection PyPep8Naming
    def setObject(self, p_object, abstract_field=options.Numeric):
        self.__p_object = p_object
        self.__field = get_field(p_object, abstract_field)
        """:type: options.Numeric"""

        connect(self.__p_object.signals[self.__field], GlobalSignals.onChanged)

        self.setValue(getattr(p_object, self.__field.key))
        self.setRange(self.__field.min, self.__field.max)

        connect(self.__p_object.signals[self.__field], self.__onValueChanged)

    # noinspection PyPep8Naming
    @QSlot()
    @QSlot(int)
    def __onValueChanged(self, *args):
        # args is not empty only when event come from Gui
        # if event come from p_object then args is empty and it's only flag
        if self.__p_object is not None:
            if args:
                setattr(self.__p_object, self.__field.key, args[0])
            else:
                self.setValue(getattr(self.__p_object, self.__field.key))


class QLineEditNumeric(QtGui.QLineEdit):

    def __init__(self, parent, p_object=None, abstract_field=options.Numeric):
        """
        :type parent: QtGui.QWidget
        :type p_object: options.Variable or None
        :type abstract_field: options.Numeric or options.AttributedProperty or database.orm.Column
        """
        super(QLineEditNumeric, self).__init__(parent)

        self.__p_object = None
        self.__field = None
        self.__validator = None

        if p_object is not None:
            self.setObject(p_object, abstract_field)

        self.setFixedWidth(config.DEFAULT_EDIT_WIDTH)

        connect(self.editingFinished, self.__onEditingFinished)

    # noinspection PyPep8Naming
    def setObject(self, p_object, abstract_field=options.Numeric):
        """
        :type p_object: options.Variable or options.MaterialLayer
        :type abstract_field: options.Numeric or options.AttributedProperty or database.orm.Column
        """
        if self.__p_object is not None:
            disconnect(self.__p_object.signals[self.__field], self.__changeText)

        self.__p_object = p_object
        self.__field = get_field(p_object, abstract_field)
        """:type: options.Numeric"""

        connect(self.__p_object.signals[self.__field], GlobalSignals.onChanged)

        value = getattr(self.__p_object, self.__field.key)

        if isinstance(value, float):
            self.__validator = QtGui.QDoubleValidator(self)
            self.__validator.setNotation(QtGui.QDoubleValidator.StandardNotation)
            precision = (self.__field.precision
                         if self.__field.precision is not None
                         else config.DEFAULT_DECIMAL_COUNT)
            self.__validator.setDecimals(precision)
        elif isinstance(value, int):
            self.__validator = QtGui.QIntValidator(self)

        self.setText(str(value))

        self.setValidator(self.__validator)

        connect(self.__p_object.signals[self.__field], self.__changeText)

    # noinspection PyPep8Naming
    def unsetObject(self):
        if self.__p_object is not None:
            disconnect(self.__p_object.signals[self.__field], self.__changeText)
            disconnect(self.__p_object.signals[self.__field], GlobalSignals.onChanged)
            self.__p_object = None
            self.__field = None
            self.setText(str())

    # noinspection PyPep8Naming
    @QSlot()
    def __changeText(self):
        value = getattr(self.__p_object, self.__field.key)
        self.setText(str(value))

    # noinspection PyPep8Naming
    @QSlot()
    def __onEditingFinished(self):
        # logging.info("Value after edit finished: %s" % self.text())
        if self.__p_object is not None:
            try:
                cast_result = self.__field.type.python_type(self.text())
            except ValueError:
                logging.warning("Can't convert value %s to %s" %
                                (self.text(), self.__field.type.python_type.__name__))
            else:
                setattr(self.__p_object, self.__field.key, cast_result)


class QObjectNumeric(QtCore.QObject):

    def __init__(self, parent, p_object=None, abstract_field=options.Numeric, global_signals=False):
        """
        :type parent: QtGui.QWidget
        :type p_object: options.Variable or None
        :type abstract_field: options.Numeric or options.AttributedProperty or database.orm.Column
        :type global_signals: bool
        """
        super(QObjectNumeric, self).__init__(parent)

        self.__global_signals = global_signals

        self.__p_object = None
        self.__field = None
        self.__value = None

        if p_object is not None:
            self.setObject(p_object, abstract_field)

    @property
    def object(self):
        return self.__p_object

    @property
    def field(self):
        return self.__field

    @property
    def value(self):
        return self.__value

    @value.setter
    def value(self, data):
        if self.__p_object is not None:
            try:
                cast_result = self.__field.type.python_type(data) if data is not None else None
            except ValueError:
                logging.warning("Can't convert value %s to %s" %
                                (self.text(), self.__field.type.python_type.__name__))
            else:
                # v = getattr(self.__p_object, self.__field.key)
                # logging.info(
                #     "Object: %s Field: %s Value: %s -> %s" %
                #     (self.__p_object, self.__field.key, v, cast_result))
                setattr(self.__p_object, self.__field.key, cast_result)
                self.__value = data

    # noinspection PyPep8Naming
    def setObject(self, p_object, abstract_field=options.Numeric):
        """
        :type p_object: options.structures.Variable or options.structures.MaterialLayer
        :type abstract_field: options.Numeric or options.AttributedProperty or database.orm.Column
        """
        if self.__p_object is not None:
            disconnect(self.__p_object.signals[self.__field], self.__field_changed)

        self.__p_object = p_object
        self.__field = get_field(p_object, abstract_field)
        """:type: options.structures.Numeric"""

        if self.__global_signals:
            connect(self.__p_object.signals[self.__field], GlobalSignals.onChanged)

        self.value = getattr(self.__p_object, self.__field.key)

        connect(self.__p_object.signals[self.__field], self.__field_changed)

    # noinspection PyPep8Naming
    def unsetObject(self):
        if self.__p_object is not None:
            disconnect(self.__p_object.signals[self.__field], self.__field_changed)
            if self.__global_signals:
                disconnect(self.__p_object.signals[self.__field], GlobalSignals.onChanged)
            self.__p_object = None
            self.__field = None
            self.__value = None

    # noinspection PyPep8Naming
    @QSlot()
    def __field_changed(self):
        self.__value = getattr(self.__p_object, self.__field.key)


class QComboBoxEnum(QtGui.QComboBox):

    def __init__(self, parent, p_object=None, abstract_field=options.Enum):
        """
        :type parent: QtGui.QWidget
        :type p_object: options.Variable or None
        :type abstract_field: options.Enum
        """
        QtGui.QComboBox.__init__(self, parent)

        self.__p_object = None
        self.__field = None

        if p_object is not None:
            self.setObject(p_object, abstract_field)

        connect(self.currentIndexChanged, self.__onIndexChanged)

    # noinspection PyPep8Naming
    def setObject(self, p_object, abstract_field=options.Enum):
        """
        :type p_object: options.Variable or None
        :type abstract_field: options.Enum
        """
        self.__p_object = p_object
        self.__field = get_field(p_object, abstract_field)
        """:type: options.Enum"""

        connect(self.__p_object.signals[self.__field], GlobalSignals.onChanged)

        self.clear()
        self.addItems(self.__field.variants)
        self.setCurrentIndex(self.findText(getattr(self.__p_object, self.__field.key)))

    # noinspection PyPep8Naming
    @QSlot(int)
    def __onIndexChanged(self, index):
        if self.__p_object is not None:
            value = str(self.itemText(index))
            setattr(self.__p_object, self.__field.key, value)


class QLabelMulti(QtGui.QLabel):

    class _MemoryFormat(object):
        pass

    memory_format = _MemoryFormat()

    def _enum_items(self):
        for item in self._items:
            obj, abstract_field = item
            field = get_field(obj, abstract_field)
            yield obj, field

    def __init__(self, parent, items=None, frmt=None):
        """
        :type parent: QtGui.QWidget
        :type items: list of (options.Variable,
                              options.Abstract or options.AttributedProperty or database.orm.Column) or None
        :type frmt: str or None
        """
        QtGui.QLabel.__init__(self, parent)

        self._items = None
        self._format = frmt

        if items is not None:
            self.setObject(items)

        self.setAlignment(QtCore.Qt.AlignCenter)

    # noinspection PyPep8Naming
    def setObject(self, items, frmt=None):
        """:type items: list of (options.Variable,
                                 options.Abstract or options.AttributedProperty or database.orm.Column)"""

        if self._items is not None:
            if len(items) != len(self._items) and self._format is not None and frmt is None:
                raise ValueError("Number of objects not equal previous object number but format is not changed!")

            for obj, field in self._enum_items():
                disconnect(obj.signals[field], self.__onTextChanged)

        self._items = items
        for obj, field in self._enum_items():
            connect(obj.signals[field], self.__onTextChanged)

        if frmt is not None:
            self._format = frmt
        elif self._format is None:
            self._format = "%s "*len(self._items)

        self.__onTextChanged()

    # noinspection PyPep8Naming
    @QSlot()
    def __onTextChanged(self):
        values = [getattr(obj, field.key) if getattr(obj, field.key) is not None else "- Undefined -"
                  for obj, field in self._enum_items()]

        if self._format is QLabelMulti.memory_format:
            if len(values) != 1:
                raise ValueError("Can't use memory format to more than one item")
            value = float(values[0])
            if value > 10.0*GIGABYTE:
                self.setText("%d GiB" % int(math.ceil(value/10.0/GIGABYTE)))
            elif value > MEGABYTE:
                self.setText("%d MiB" % int(math.ceil(value/MEGABYTE)))
            elif value > KILOBYTE:
                self.setText("%d KiB" % int(math.ceil(value/KILOBYTE)))
            else:
                self.setText("%d Bytes" % int(math.ceil(value)))
        else:
            self.setText(self._format % tuple(values))


class QLabel(QLabelMulti):

    def __init__(self, parent, p_object=None, abstract_field=options.Abstract, frmt=None):
        """
        :type parent: QtGui.QWidget
        :type p_object: options.Variable or None
        :type abstract_field: options.Abstract or options.AttributedProperty or database.orm.Column
        :type frmt: str or None
        """
        # QLabelMulti constructor can't be called because that result in incontinence.
        # QLabelMulti.__init__ call setObject thinking that constructor belongs to QLabelMulti
        # but in really setObject override by QLabel class.
        QtGui.QLabel.__init__(self, parent)

        self._items = None
        self._format = frmt

        if p_object is not None:
            self.setObject(p_object, abstract_field)

        self.setAlignment(QtCore.Qt.AlignRight)

    def setObject(self, p_object, abstract_field=options.Abstract):
        """
        :type p_object: options.Variable or None
        :type abstract_field: options.Abstract or options.AttributedProperty or database.orm.Column
        """
        QLabelMulti.setObject(self, [(p_object, abstract_field)])


class QFramedLabel(QLabel):

    def __init__(self, parent, p_object=None, abstract_field=options.Abstract, frmt=None):
        """
        :type parent: QtGui.QWidget
        :type p_object: options.Variable or None
        :type abstract_field: options.Abstract or options.AttributedProperty or database.orm.Column
        :type frmt: str or None
        """
        QLabel.__init__(self, parent, p_object, abstract_field, frmt)
        self.setAlignment(QtCore.Qt.AlignRight)
        self.setFrameStyle(QtGui.QFrame.Box | QtGui.QFrame.Sunken)
        self.setStyleSheet("QLabel{padding: 3px 3px 3px 3px;}")


class QStackWidgetTab(QtGui.QWidget):

    def __init__(self, parent):
        super(QStackWidgetTab, self).__init__(parent)
        self.__vlayout = None
        self.__hlayout = None

    # noinspection PyPep8Naming
    def onSetActive(self):
        pass

    def reset(self):
        pass

    # noinspection PyPep8Naming
    def setUnstretchable(self, layout):

        self.__vlayout = QtGui.QVBoxLayout()
        self.__vlayout.addLayout(layout)
        self.__vlayout.addStretch(1)

        self.__hlayout = QtGui.QHBoxLayout(self)
        self.__hlayout.addLayout(self.__vlayout)
        self.__hlayout.addStretch(1)


class CalculationWorker(QtCore.QThread):
    """Run a simulation stage without blocking the application's UI thread."""

    succeeded = QtCore.pyqtSignal(object) if hasattr(QtCore, "pyqtSignal") else QtCore.Signal(object)
    failed = QtCore.pyqtSignal(str) if hasattr(QtCore, "pyqtSignal") else QtCore.Signal(str)

    def __init__(self, calculate, parent=None):
        super(CalculationWorker, self).__init__(parent)
        self.__calculate = calculate

    def run(self):
        try:
            self.succeeded.emit(self.__calculate())
        except Exception as error:
            logging.exception("Simulation calculation failed")
            self.failed.emit(str(error))


class _BoundedTextBuffer(object):
    """Store the beginning and end of a potentially large native output stream."""

    MAX_CHARS = 512 * 1024
    PREFIX_CHARS = 32 * 1024

    def __init__(self):
        self.__lines = deque()
        self.__size = 0
        self.__prefix = ""
        self.__truncated = False

    def append(self, text):
        if not text:
            return
        if len(self.__prefix) < self.PREFIX_CHARS:
            prefix_size = self.PREFIX_CHARS - len(self.__prefix)
            self.__prefix += text[:prefix_size]
            text = text[prefix_size:]
        if not text:
            return
        self.__lines.append(text)
        self.__size += len(text)
        while self.__size > self.MAX_CHARS - self.PREFIX_CHARS and self.__lines:
            self.__size -= len(self.__lines.popleft())
            self.__truncated = True

    @property
    def text(self):
        omitted = "\n[Middle output omitted after reaching the 512 KiB log limit.]\n" if self.__truncated else ""
        return self.__prefix + omitted + "".join(self.__lines)


class NativeOutputCapture(object):
    """Drain stdout and stderr during a native call without a pipe deadlock."""

    def __init__(self):
        self.__buffer = _BoundedTextBuffer()
        self.__reader = None
        self.__read_fd = None
        self.__saved_stdout = None
        self.__saved_stderr = None
        self.__active = False

    @staticmethod
    def __flush_streams():
        for stream in (sys.stdout, sys.stderr):
            try:
                stream.flush()
            except (AttributeError, IOError, OSError):
                pass

    def start(self):
        self.__flush_streams()
        read_fd, write_fd = os.pipe()
        saved_stdout = None
        saved_stderr = None
        try:
            saved_stdout = os.dup(1)
            saved_stderr = os.dup(2)
        except Exception:
            for descriptor in (read_fd, write_fd, saved_stdout, saved_stderr):
                if descriptor is not None:
                    try:
                        os.close(descriptor)
                    except OSError:
                        pass
            raise

        self.__read_fd = read_fd
        self.__saved_stdout = saved_stdout
        self.__saved_stderr = saved_stderr

        def drain():
            try:
                while True:
                    chunk = os.read(read_fd, 8192)
                    if not chunk:
                        break
                    self.__buffer.append(chunk.decode("utf-8", errors="replace"))
            finally:
                os.close(read_fd)

        self.__reader = threading.Thread(target=drain, name="SimulationLogReader", daemon=True)
        try:
            self.__reader.start()
        except Exception:
            for descriptor in (read_fd, write_fd, saved_stdout, saved_stderr):
                try:
                    os.close(descriptor)
                except OSError:
                    pass
            raise
        try:
            os.dup2(write_fd, 1)
            os.dup2(write_fd, 2)
        except Exception:
            os.dup2(saved_stdout, 1)
            os.dup2(saved_stderr, 2)
            os.close(write_fd)
            os.close(saved_stdout)
            os.close(saved_stderr)
            self.__reader.join()
            raise
        finally:
            try:
                os.close(write_fd)
            except OSError:
                pass
        self.__active = True

    def stop(self):
        if self.__active:
            self.__flush_streams()
            try:
                os.dup2(self.__saved_stdout, 1)
            finally:
                try:
                    os.dup2(self.__saved_stderr, 2)
                finally:
                    os.close(self.__saved_stdout)
                    os.close(self.__saved_stderr)
                    self.__active = False
                    self.__reader.join()
        return self.__buffer.text


class _SimulationCalculationWorker(QtCore.QThread):
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, stage, parent=None):
        super(_SimulationCalculationWorker, self).__init__(parent)
        self.__stage = stage
        self.native_output = ""

    def run(self):
        capture = NativeOutputCapture()
        try:
            capture.start()
            result = self.__stage.calculate()
            self.native_output = capture.stop()
            validate_simulation_result(result)
            self.succeeded.emit(result)
        except Exception:
            self.native_output = capture.stop()
            self.failed.emit(traceback.format_exc())


def validate_simulation_result(result):
    """Reject missing or structurally empty results before making them viewable."""
    if result is None:
        raise ValueError("The simulation returned no result.")
    if not hasattr(result, "values"):
        raise ValueError("The simulation result has no values array.")
    values = result.values
    shape = getattr(values, "shape", None)
    if values is None or (shape is not None and
                          (len(shape) == 0 or any(size <= 0 for size in shape))):
        raise ValueError("The simulation returned an empty or malformed values array.")


class SimulationManager(QtCore.QObject):
    """Serialize in-process simulation work and publish its lifecycle to views."""

    stateChanged = Signal(object, str, str)
    busyChanged = Signal(bool)

    IDLE = "IDLE"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

    def __init__(self, parent=None):
        super(SimulationManager, self).__init__(parent)
        self.__worker = None
        self.__active_stage = None
        self.__external_job = None
        self.__states = {}
        self.__results = {}
        self.__errors = {}
        self.__logs = {}

    @property
    def busy(self):
        return self.__worker is not None or self.__external_job is not None

    def begin_external_job(self, name):
        """Reserve the shared simulation slot for a workflow with its own worker."""
        if self.busy:
            return False
        self.__external_job = name
        self.busyChanged.emit(True)
        return True

    def end_external_job(self, name):
        if self.__external_job == name:
            self.__external_job = None
            self.busyChanged.emit(False)

    def register_stage(self, stage):
        if stage not in self.__states:
            self.__states[stage] = self.IDLE
            connect(stage.invalidated, lambda stage=stage: self.__on_stage_invalidated(stage))

    def state(self, stage):
        self.register_stage(stage)
        if stage in self.__results and stage.has_result:
            return self.COMPLETED
        return self.__states.get(stage, self.IDLE)

    def result(self, stage):
        if stage in self.__results and stage.has_result:
            return self.__results[stage]
        return None

    def error_log(self, stage):
        return self.__errors.get(stage, "")

    def output_log(self, stage):
        return self.__logs.get(stage, "")

    def start(self, stage):
        self.register_stage(stage)
        if self.busy:
            return False

        self.__active_stage = stage
        self.__results.pop(stage, None)
        self.__errors.pop(stage, None)
        self.__logs.pop(stage, None)
        self.__set_state(stage, self.STARTING, "Preparing simulation…")

        worker = _SimulationCalculationWorker(stage, self)
        self.__worker = worker
        connect(worker.succeeded, self.__on_worker_succeeded)
        connect(worker.failed, self.__on_worker_failed)
        connect(worker.finished, self.__on_worker_finished)
        self.busyChanged.emit(True)
        try:
            worker.start()
        except Exception:
            self.__worker = None
            self.__active_stage = None
            self.__errors[stage] = "Simulation mode: %s\n\nWorker could not start:\n%s" % (
                stage.name, traceback.format_exc())
            self.__set_state(stage, self.FAILED, "Simulation failed to start. Open Error Log for details.")
            self.busyChanged.emit(False)
            worker.deleteLater()
            return True
        self.__set_state(stage, self.RUNNING, "Simulation is running…")
        return True

    def __set_state(self, stage, state, message=""):
        self.__states[stage] = state
        self.stateChanged.emit(stage, state, message)

    @QSlot(object)
    def __on_worker_succeeded(self, result):
        stage = self.__active_stage
        if stage is None:
            return
        self.__results[stage] = result
        self.__logs[stage] = self.__worker.native_output
        self.__errors.pop(stage, None)
        self.__set_state(stage, self.COMPLETED, "Simulation completed. Results are ready.")

    @QSlot(str)
    def __on_worker_failed(self, details):
        stage = self.__active_stage
        if stage is None:
            return
        try:
            stage.invalidate()
        except Exception:
            logging.exception("Could not clear a failed simulation result")
        logs = self.__worker.native_output if self.__worker is not None else ""
        report = ["Simulation mode: %s" % stage.name,
                  "Failure reason and Python traceback:", details,
                  "Backend exit code: not applicable (in-process C++ binding)."]
        if logs:
            report.extend(["Captured stdout and stderr (bounded to 512 KiB; first and last portions retained):", logs])
        else:
            report.append("Captured stdout and stderr: no output was emitted.")
        self.__errors[stage] = "\n\n".join(report)
        self.__results.pop(stage, None)
        self.__set_state(stage, self.FAILED, "Simulation failed. Open Error Log for details.")

    @QSlot()
    def __on_worker_finished(self):
        worker = self.__worker
        self.__worker = None
        self.__active_stage = None
        self.busyChanged.emit(False)
        if worker is not None:
            worker.deleteLater()

    def __on_stage_invalidated(self, stage):
        self.__results.pop(stage, None)
        self.__errors.pop(stage, None)
        self.__logs.pop(stage, None)
        if self.__states.get(stage) in (self.COMPLETED, self.FAILED):
            self.__set_state(stage, self.IDLE, "Inputs changed. Run the simulation again.")


class SimulationErrorDialog(QtGui.QDialog):
    """Detailed, copyable, and savable simulation failure report."""

    def __init__(self, parent, report):
        super(SimulationErrorDialog, self).__init__(parent)
        self.setWindowTitle("Simulation Error Log")
        self.resize(760, 520)
        self.__log = QtGui.QPlainTextEdit(self)
        self.__log.setReadOnly(True)
        self.__log.setPlainText(report)

        copy_button = QtGui.QPushButton("Copy", self)
        save_button = QtGui.QPushButton("Save…", self)
        close_button = QtGui.QPushButton("Close", self)
        connect(copy_button.clicked, self.__copy)
        connect(save_button.clicked, self.__save)
        connect(close_button.clicked, self.accept)

        buttons = QtGui.QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(copy_button)
        buttons.addWidget(save_button)
        buttons.addWidget(close_button)
        layout = QtGui.QVBoxLayout(self)
        layout.addWidget(self.__log)
        layout.addLayout(buttons)

    def __copy(self):
        QtGui.QApplication.clipboard().setText(self.__log.toPlainText())

    def __save(self):
        path, _ = QtGui.QFileDialog.getSaveFileName(
            self, "Save Simulation Error Log", "simulation-error.log", "Log files (*.log);;All files (*)")
        if path:
            try:
                with open(path, "w", encoding="utf-8") as log_file:
                    log_file.write(self.__log.toPlainText())
            except (IOError, OSError) as error:
                ErrorBox(self, "Could not save the error log:\n%s" % error)


class QStackedWidget(QtGui.QStackedWidget):

    def setCurrentWidget(self, widget):
        if isinstance(widget, QStackWidgetTab):
            widget.onSetActive()
        QtGui.QStackedWidget.setCurrentWidget(self, widget)


class QGraphPlot(FigureCanvas):

    def __init__(self, parent, width=None, height=None, figsize=None):
        """
        :type parent: QtGui.QWidget
        :type width: int
        :type height: int
        """
        self._figure = Figure(dpi=config.Configuration.dpi, figsize=figsize)
        """:type: matplotlib.figure.Figure"""

        super(QGraphPlot, self).__init__(self._figure)
        self.setParent(parent)

        if width is not None and height is not None:
            self.setFixedSize(width, height)

        color = self.palette().color(QtGui.QPalette.Window)
        self._figure.patch.set_facecolor(rgbf(color))

    def add_subplot(self, position=111, **kwargs):
        """:rtype: matplotlib.axes.Axes"""
        return self._figure.add_subplot(position, **kwargs)
        # if aspect is None:
        #     return self._figure.add_subplot(position)
        # else:
        #     return self._figure.add_subplot(position, aspect=aspect)

    def clear(self):
        self._figure.clf()

    def redraw(self):
        if self._figure.get_axes():
            self._figure.tight_layout(pad=0.1)
            self.draw()

    def resizeEvent(self, event=None):
        FigureCanvas.resizeEvent(self, event)
        self.redraw()


class ParameterGroupBox(QtGui.QGroupBox):

    def edit(self, p_object=None):
        result = QLineEditNumeric(self, p_object)
        result.setFixedWidth(config.DEFAULT_EDIT_WIDTH)
        return result

    def framed_label(self, p_object=None):
        result = QFramedLabel(self, p_object)
        result.setAlignment(QtCore.Qt.AlignCenter | QtCore.Qt.AlignVCenter)
        # result.setFixedWidth(config.DEFAULT_EDIT_WIDTH)
        result.setMinimumWidth(80)
        result.setFixedHeight(25)
        return result

    def __init__(self, title, parent):
        super(ParameterGroupBox, self).__init__(title, parent)
        self.__prms = dict()
        self.setSizePolicy(QtGui.QSizePolicy.MinimumExpanding, QtGui.QSizePolicy.Maximum)
        # self.setMinimumWidth(250)
        # self.setFixedWidth(390)

    def _add_plugin_parameters(self, p_object, layout):
        for item in self.__prms.values():
            item["edit"].unsetObject()
            container = item["layout"].takeAt(0)
            while container:
                del container
                container = item["layout"].takeAt(0)
            item["edit"].setParent(None)
            item["label"].setParent(None)
            item["layout"].setParent(None)

        self.__prms.clear()

        for variable in p_object.variables:
            hlayout = QtGui.QHBoxLayout()
            label = QtGui.QLabel(variable.name, self)
            edit = self.edit(variable)
            self.__prms[variable.name] = {"layout": hlayout, "edit": edit, "label": label}
            hlayout.addWidget(label)
            hlayout.addStretch()
            hlayout.addWidget(edit)
            layout.addLayout(hlayout)


# noinspection PyPep8Naming
def QLoadDialogFactory(db_type, plugin_type, plot_type):

    class QLoadDialog(QtGui.QDialog):

        def __init__(self, parent, appdb):
            """
            :type parent: QtGui.QMainWindow
            :type appdb: ApplicationDatabase
            """
            QtGui.QDialog.__init__(self, parent)

            name = db_type.title

            self.setWindowTitle("Load %s" % name)
            self.setWindowIcon(parent.windowIcon())

            self.__appdb = appdb

            self.__db_type = db_type
            self.__plugin_type = plugin_type

            self.__select_group = QtGui.QGroupBox("Select Parametric (Plugin) or Database %s" % name, self)
            self.__select_group_layout = QtGui.QHBoxLayout(self.__select_group)

            self.__parametric_label = QtGui.QLabel("Parametric:")
            self.__parametric_list = QtGui.QListWidget(self.__select_group)
            self.__parametric_layout = QtGui.QVBoxLayout()
            self.__parametric_layout.addWidget(self.__parametric_label)
            self.__parametric_layout.addWidget(self.__parametric_list)
            self.__select_group_layout.addLayout(self.__parametric_layout)

            self.__database_label = QtGui.QLabel("Database:")
            self.__database_list = QtGui.QListWidget(self.__select_group)
            self.__database_layout = QtGui.QVBoxLayout()
            self.__database_layout.addWidget(self.__database_label)
            self.__database_layout.addWidget(self.__database_list)
            self.__select_group_layout.addLayout(self.__database_layout)
            self.__select_group.setFixedHeight(200)

            self.__plot = plot_type(self)
            self.__plot.setEnabled(False)

            self.__plot_hlay = QtGui.QHBoxLayout()
            self.__plot_hlay.addWidget(self.__plot)
            self.__plot_hlay.setAlignment(QtCore.Qt.AlignCenter)

            self.__buttons_layout = QtGui.QHBoxLayout()
            self.__load_button = QtGui.QPushButton("Load", self)
            self.__load_button.setFixedWidth(config.MAXIMUM_DIALOG_BUTTON_WIDTH)
            self.__cancel_button = QtGui.QPushButton("Cancel", self)
            self.__cancel_button.setFixedWidth(config.MAXIMUM_DIALOG_BUTTON_WIDTH)

            self.__buttons_layout.addStretch()
            self.__buttons_layout.addWidget(self.__load_button)
            self.__buttons_layout.addWidget(self.__cancel_button)

            for plugin in self.__appdb[self.__plugin_type]:
                self.__parametric_list.addItem(plugin.name)

            connect(self.__load_button.clicked, self.accept)
            connect(self.__cancel_button.clicked, self.reject)

            connect(self.__parametric_list.itemSelectionChanged, self._accept_state_handler)
            connect(self.__database_list.itemSelectionChanged, self._accept_state_handler)
            connect(self.__parametric_list.itemSelectionChanged, self._change_material)
            connect(self.__database_list.itemSelectionChanged, self._change_material)

            self.__layout = QtGui.QVBoxLayout(self)
            self.__layout.addWidget(self.__select_group)
            self.__layout.addLayout(self.__plot_hlay)
            self.__layout.addLayout(self.__buttons_layout)

            self._accept_state_handler()

        def update_database_list(self):
            self.__database_list.clear()
            for p_object in self.__appdb[self.__db_type]:
                self.__database_list.addItem(p_object.name)

        def showEvent(self, *args, **kwargs):
            self.update_database_list()
            super(QLoadDialog, self).showEvent(*args, **kwargs)

        # noinspection PyUnusedLocal
        def _accept_state_handler(self, *args):
            self.__plot.setEnabled(self.is_item_selected)
            self.__load_button.setEnabled(self.is_item_selected)

        def _change_material(self):
            if self.sender() is self.__parametric_list:
                self.__database_list.clearSelection()
            elif self.sender() is self.__database_list:
                self.__parametric_list.clearSelection()

            if self.object is not None:
                self.__plot.setObject(self.object)

        @property
        def object(self):
            if self.__database_list.selectedItems():
                item = self.__database_list.currentItem()
                return self.__appdb[self.__db_type].filter(self.__db_type.name == item.text()).one()

            elif self.__parametric_list.selectedItems():
                item = self.__parametric_list.currentItem()
                abstract = self.__appdb[self.__plugin_type].\
                    filter(self.__plugin_type.name == item.text()).one()
                return abstract.produce()

        @property
        def is_item_selected(self):
            return bool(self.__parametric_list.selectedItems() or self.__database_list.selectedItems())

    return QLoadDialog


def calculate_table_width(table_widget):
    """
    :type table_widget: QtGui.QTableView
    :rtype: int
    """
    layout = table_widget.layout()
    if layout is not None:
        left, top, right, bottom = table_widget.layout().getContentsMargins()
    else:
        left, top, right, bottom = 0, 0, 0, 0

    extra_left = left + table_widget.frameWidth()
    extra_right = right + table_widget.frameWidth()

    min_width = extra_left + extra_right

    if table_widget.verticalHeader().isVisible():
        min_width += table_widget.verticalHeader().width()

    for k in range(table_widget.horizontalHeader().count()):
        min_width += table_widget.columnWidth(k)

    min_width += int(table_widget.verticalScrollBar().height() / 2) + table_widget.frameWidth()

    return min_width


class QMetrologyTable(QtGui.QTableWidget):

    CAPTION_INDEX = 0
    VALUE_INDEX = 1
    HEIGHT = 25
    OVERSIZE = 5

    @staticmethod
    def __create_item(text):
        item = QtGui.QTableWidgetItem(text)
        item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEditable)
        return item

    def __init__(self, parent, metrics):
        """
        :type parent: QtGui.QWidget
        :type metrics: list of metrology.MetrologyInterface
        """
        super(QMetrologyTable, self).__init__(parent)
        self.setColumnCount(2)
        self.setHorizontalHeaderLabels(["Metric name", "Metric value"])

        self.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
        self.setSelectionMode(QtGui.QAbstractItemView.SingleSelection)
        self.horizontalHeader().setClickable(False)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(self.HEIGHT)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOn)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.resizeColumnsToContents()

        self.setColumnWidth(self.CAPTION_INDEX, 155)
        self.setColumnWidth(self.VALUE_INDEX, 75)

        self.setFixedWidth(calculate_table_width(self) + self.OVERSIZE)
        self.setMinimumHeight(240)

        self.__p_object = None
        self.__metrics = metrics

    # noinspection PyPep8Naming
    def setObject(self, p_object, **kwargs):
        self.clearContents()
        rows = 0
        self.setRowCount(len(self.__metrics))
        for k, metric in enumerate(self.__metrics):
            try:
                value = metric(p_object, **kwargs)
            except MetricNotImplementedError:
                pass
            else:
                string = metric.format % value if not isnan(value) else "N/A"
                self.setItem(rows, self.CAPTION_INDEX, self.__create_item(metric.caption))
                self.setItem(rows, self.VALUE_INDEX, self.__create_item(string))
                rows += 1

        self.setRowCount(rows)
        self.__p_object = p_object
