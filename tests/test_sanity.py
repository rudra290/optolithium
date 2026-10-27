#!/usr/bin/env python3
"""
Optolithium Sanity & Integration Test Suite
============================================
Runs in CI/CD pipeline to verify core C++ simulation engine, SWIG bindings,
Clipper library, plugins, and GUI modules.
"""

import os
import sys
from pathlib import Path

# Add OptolithiumGui to Python path
REPO_ROOT = Path(__file__).resolve().parent.parent
GUI_DIR = REPO_ROOT / "OptolithiumGui"
sys.path.insert(0, str(GUI_DIR))

# Ensure Qt can run in headless CI environments
os.environ["QT_QPA_PLATFORM"] = "offscreen"


def test_version_info():
    print("--> Testing info.py version metadata...")
    import info
    assert hasattr(info, "__version__"), "info module missing __version__"
    assert hasattr(info, "__name__"), "info module missing __name__"
    print(f"    Version: {info.__version__}")


def test_optolithiumc_core():
    print("--> Testing OptolithiumC SWIG bindings...")
    import _optolithiumc
    import optolithiumc

    # Test basic geometric types
    p2 = optolithiumc.Point2d(10.5, 20.25)
    assert p2.x == 10.5 and p2.y == 20.25, f"Point2d mismatch: {p2.x}, {p2.y}"

    p3 = optolithiumc.Point3d(1.0, 2.0, 3.0)
    assert p3.x == 1.0 and p3.y == 2.0 and p3.z == 3.0, "Point3d mismatch"

    print("    OptolithiumC core types instantiated successfully.")


def test_clipper():
    print("--> Testing Clipper polygon library...")
    import _clipper
    import clipper

    c = clipper.Clipper()
    pt = clipper.IntPoint(100, 200)
    assert pt.X == 100 and pt.Y == 200, "IntPoint coordinates mismatch"
    print(f"    Clipper version: {clipper.CLIPPER_VERSION}")


def test_plugins_installed():
    print("--> Testing compiled simulation plugins...")
    plugins_dir = GUI_DIR / "plugins"
    assert plugins_dir.exists(), f"Plugins directory missing: {plugins_dir}"

    expected_groups = ["dev_models", "masks", "pupil_filters", "source_shapes"]
    found_plugins = []
    for group in expected_groups:
        group_path = plugins_dir / group
        assert group_path.exists(), f"Missing plugin category: {group}"
        so_files = list(group_path.glob("*.so"))
        assert len(so_files) > 0, f"No compiled .so plugins found in {group_path}"
        found_plugins.extend([f.name for f in so_files])

    print(f"    Verified {len(found_plugins)} compiled plugins across {len(expected_groups)} categories.")


def test_gui_core_modules():
    print("--> Testing GUI core modules (headless Qt offscreen)...")
    import config
    import auxmath
    import core
    import metrics
    print("    GUI core modules imported and initialized successfully.")


def main():
    print("==================================================")
    print(" Running Optolithium Sanity Tests")
    print("==================================================")
    test_version_info()
    test_optolithiumc_core()
    test_clipper()
    test_plugins_installed()
    test_gui_core_modules()
    print("==================================================")
    print(" All Optolithium Sanity Tests Passed Successfully!")
    print("==================================================")


if __name__ == "__main__":
    main()
