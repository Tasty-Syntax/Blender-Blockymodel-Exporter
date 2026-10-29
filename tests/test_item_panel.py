import unittest
from types import SimpleNamespace
from unittest import mock

from tests import _blender_stubs  # noqa: F401  (must come before bpy is imported)

import bpy

from tests.addon_loader import load_addon
from tests.mesh_helpers import add_box, make_object, reset_scene


def select_only(obj):
    for other in bpy.context.scene.objects:
        other.select_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


@unittest.skipUnless(_blender_stubs.IN_BLENDER, "needs Blender")
class ItemPanel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.addon = load_addon()

    def setUp(self):
        reset_scene()
        self.scene = bpy.context.scene
        self.scene.hytale_format = 'prop'
        self.scene.hytale_item_space = 'GLOBAL'
        self.obj = make_object("box", lambda bm: add_box(bm, (-0.5, -0.5, -0.5), (0.5, 0.5, 0.5)))
        select_only(self.obj)

    def assertVector(self, actual, expected):
        for a, e in zip(actual, expected):
            self.assertAlmostEqual(a, e, places=4)

    def test_location_is_shown_in_pixels_of_the_format(self):
        self.obj.location = (1.0, 0.5, -0.25)
        self.assertVector(self.obj.hytale_location_px, (32, 16, -8))
        self.scene.hytale_format = 'character'
        self.assertVector(self.obj.hytale_location_px, (64, 32, -16))

    def test_setting_pixels_moves_the_object(self):
        self.obj.hytale_location_px = (16, 0, 64)
        self.assertVector(self.obj.location, (0.5, 0, 2))

    def test_dimensions_round_trip_through_pixels(self):
        self.assertVector(self.obj.hytale_dimensions_px, (32, 32, 32))
        self.obj.hytale_dimensions_px = (48, 32, 8)
        bpy.context.view_layer.update()
        self.assertVector(self.obj.dimensions, (1.5, 1, 0.25))

    def test_edit_mode_median_moves_the_selected_vertices(self):
        self.obj.location = (1, 0, 0)
        bpy.ops.object.mode_set(mode='EDIT')
        try:
            bpy.ops.mesh.select_all(action='SELECT')
            self.assertVector(self.obj.hytale_median_px, (32, 0, 0))
            self.scene.hytale_item_space = 'LOCAL'
            self.assertVector(self.obj.hytale_median_px, (0, 0, 0))
            self.obj.hytale_median_px = (8, 0, 0)
            self.scene.hytale_item_space = 'GLOBAL'
            self.assertVector(self.obj.hytale_median_px, (40, 0, 0))
        finally:
            bpy.ops.object.mode_set(mode='OBJECT')
        xs = [v.co.x for v in self.obj.data.vertices]
        self.assertAlmostEqual(min(xs), -0.25, places=5)

    def test_panel_draws_in_object_and_edit_mode(self):
        for rotation_mode in ('XYZ', 'QUATERNION', 'AXIS_ANGLE'):
            self.obj.rotation_mode = rotation_mode
            panel = SimpleNamespace(layout=mock.MagicMock())
            self.addon.modules.item_ui.HYTALE_PT_item.draw(panel, bpy.context)
        bpy.ops.object.mode_set(mode='EDIT')
        try:
            panel = SimpleNamespace(layout=mock.MagicMock())
            self.addon.modules.item_ui.HYTALE_PT_item.draw(panel, bpy.context)
        finally:
            bpy.ops.object.mode_set(mode='OBJECT')


if __name__ == "__main__":
    unittest.main()
