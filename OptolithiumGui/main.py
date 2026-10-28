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
import os
import argparse
import warnings

# Fast-path metadata import (no heavy dependencies)
from info import __version__


__author__ = 'Alexei Gladkikh'


def parse_arguments(args=None):
    """Build and parse command line options for Optolithium."""
    parser = argparse.ArgumentParser(
        prog="optolithium",
        description="Optolithium - Modern Optical Lithography Simulation Suite",
        epilog="For more information and documentation, visit: https://bitbucket.org/gladkikhalexei/lithography",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "file",
        nargs="?",
        default=None,
        metavar="FILE",
        help="Path to an Optolithium simulation options file (*.opl) to load on startup",
    )
    parser.add_argument(
        "-v", "-V", "--version",
        action="version",
        version="%(prog)s " + __version__,
        help="Show program's version number and exit",
    )
    parser.add_argument(
        "--log-level",
        dest="log_level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default=None,
        help="Set console logging verbosity level (default: INFO)",
    )
    parser.add_argument(
        "-d", "--debug",
        action="store_true",
        help="Enable verbose debug logging (equivalent to --log-level DEBUG)",
    )
    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Suppress informational log messages (equivalent to --log-level WARNING)",
    )
    parser.add_argument(
        "--style",
        dest="style",
        metavar="STYLE",
        default=None,
        help="Override Qt GUI application style (e.g., Fusion, Windows)",
    )
    parser.add_argument(
        "--platform",
        dest="platform",
        metavar="PLATFORM",
        default=None,
        help="Qt platform plugin to use (e.g., xcb, wayland, offscreen)",
    )

    window_mode = parser.add_mutually_exclusive_group()
    window_mode.add_argument(
        "--maximized",
        action="store_true",
        help="Start application window maximized",
    )
    window_mode.add_argument(
        "--fullscreen",
        action="store_true",
        help="Start application window in full screen mode",
    )

    parsed_args = parser.parse_args(args)

    # Validate options file if provided
    if parsed_args.file and not os.path.exists(parsed_args.file):
        parser.error("Options file not found: '%s'" % parsed_args.file)

    return parsed_args


def main():
    parsed_args = parse_arguments()

    # Determine logging level
    import logging as py_logging
    if parsed_args.debug:
        py_logging.getLogger().setLevel(py_logging.DEBUG)
    elif parsed_args.quiet:
        py_logging.getLogger().setLevel(py_logging.WARNING)
    elif parsed_args.log_level:
        py_logging.getLogger().setLevel(getattr(py_logging, parsed_args.log_level))

    # Silence SQLAlchemy deprecation / schema overlap warnings on console
    try:
        from sqlalchemy import exc as sa_exc
        warnings.filterwarnings("ignore", category=sa_exc.SAWarning)
    except ImportError:
        pass

    # Handle Qt platform override if requested
    if parsed_args.platform:
        os.environ["QT_QPA_PLATFORM"] = parsed_args.platform

    # During development the freshly built C++ extension lives beside the CMake
    # build tree, while an older installed copy may remain in this directory.
    _native_build_dir = os.path.abspath(os.path.join(
        os.path.dirname(__file__), "..", "OptolithiumC", "build"))
    if os.path.isfile(os.path.join(_native_build_dir, "_optolithiumc.so")):
        sys.path.insert(0, _native_build_dir)

    # Import heavy GUI modules only after CLI arguments are parsed and validated
    import config
    from qt import QtGui, QtCore
    from optolithium import MainWindow

    qt_args = [sys.argv[0]]
    if parsed_args.style:
        qt_args.extend(["-style", parsed_args.style])
    if parsed_args.platform:
        qt_args.extend(["-platform", parsed_args.platform])

    app = QtGui.QApplication(qt_args)

    QtCore.QThread.currentThread().setObjectName("MainThread")

    app_style = parsed_args.style or config.application_style
    QtGui.QApplication.setStyle(app_style)
    QtGui.QApplication.setApplicationName(config.APPLICATION_NAME)
    QtGui.QApplication.setApplicationVersion(__version__)

    # noinspection PyUnusedLocal
    main_window = MainWindow(
        options_file=os.path.abspath(parsed_args.file) if parsed_args.file else None,
        maximized=parsed_args.maximized,
        fullscreen=parsed_args.fullscreen
    )
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
