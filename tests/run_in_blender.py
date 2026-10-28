"""Runs the unit tests inside Blender, where the real bpy and mathutils are used.
Used by CI: blender -b --factory-startup --python-exit-code 1 --python tests/run_in_blender.py"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

suite = unittest.defaultTestLoader.discover(os.path.join(ROOT, "tests"), top_level_dir=ROOT)
result = unittest.TextTestRunner(verbosity=2).run(suite)
if not result.wasSuccessful():
    raise RuntimeError("unit tests failed")
