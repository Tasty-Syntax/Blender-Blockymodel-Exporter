"""Stand-ins for Blender's bundled modules, so the add-on's pure-Python code can be
tested outside Blender. Does nothing when the real modules are importable (inside Blender)."""
import importlib.util
import sys
import types
from unittest import mock


class _Base:
    """Stand-in for bpy.types.Operator, Panel, FileHandler and ExportHelper."""


def _module(name, **attrs):
    mod = types.ModuleType(name)
    mod.__dict__.update(attrs)
    sys.modules[name] = mod
    return mod


IN_BLENDER = importlib.util.find_spec("bpy") is not None


def install():
    if IN_BLENDER:
        return
    props = _module("bpy.props", **{name: mock.Mock() for name in
                                    ("BoolProperty", "EnumProperty", "IntProperty", "PointerProperty", "StringProperty")})
    types_mod = _module("bpy.types", Operator=_Base, Panel=_Base, FileHandler=_Base)
    path = _module("bpy.path", abspath=lambda p: p)
    bpy = _module("bpy", types=types_mod, props=props, path=path,
                  app=mock.Mock(), context=mock.Mock(), data=mock.Mock(), utils=mock.Mock())
    _module("bpy_extras")
    _module("bpy_extras.io_utils", ExportHelper=_Base)
    _module("bmesh", ops=mock.Mock())
    _module("mathutils", Matrix=mock.Mock(), Quaternion=mock.Mock(), Vector=mock.Mock())
    sys.modules["bpy"] = bpy


install()
