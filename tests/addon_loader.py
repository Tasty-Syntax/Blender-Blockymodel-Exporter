"""Loads the add-on the way Blender does (as a package), so register() and the
operators can be exercised from tests. Only use inside Blender."""
import importlib.util
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACKAGE = "hytale_blockymodel_exporter_under_test"
_addon = None


def load_addon():
    global _addon
    if _addon is None:
        spec = importlib.util.spec_from_file_location(
            PACKAGE, os.path.join(ROOT, "__init__.py"), submodule_search_locations=[ROOT])
        module = importlib.util.module_from_spec(spec)
        sys.modules[PACKAGE] = module
        spec.loader.exec_module(module)
        module.register()
        _addon = module
    return _addon
