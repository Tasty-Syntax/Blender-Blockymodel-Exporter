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


def extent_x(obj):
    xs = [v.co.x for v in obj.data.vertices]
    return max(xs) - min(xs)


@unittest.skipUnless(_blender_stubs.IN_BLENDER, "needs Blender")
class PixelGridOperators(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.addon = load_addon()

    def setUp(self):
        reset_scene()
        self.scene = bpy.context.scene
        self.scene.hytale_format = 'prop'
        self.scene.hytale_lock_collection = None

    def off_grid_cube(self, name="box"):
        return make_object(name, lambda bm: add_box(bm, (0, 0, 0), (1.02, 1, 1)))

    def test_snap_now_rounds_the_selection(self):
        obj = self.off_grid_cube()
        select_only(obj)
        bpy.ops.hytale.snap_to_pixel_grid()
        self.assertAlmostEqual(extent_x(obj), 33 / 32, places=5)

    def test_snap_now_with_nothing_selected_does_nothing(self):
        obj = self.off_grid_cube()
        for other in self.scene.objects:
            other.select_set(False)
        bpy.ops.hytale.snap_to_pixel_grid()
        self.assertAlmostEqual(extent_x(obj), 1.02, places=5)

    def test_snap_now_uses_the_lock_collection(self):
        coll = bpy.data.collections.new("Locked")
        self.scene.collection.children.link(coll)
        obj = self.off_grid_cube()
        self.scene.collection.objects.unlink(obj)
        coll.objects.link(obj)
        self.scene.hytale_lock_collection = coll
        bpy.ops.hytale.snap_to_pixel_grid()
        self.assertAlmostEqual(extent_x(obj), 33 / 32, places=5)

    def test_snap_now_with_no_meshes_reports_and_finishes(self):
        for other in self.scene.objects:
            other.select_set(False)
        self.assertEqual(bpy.ops.hytale.snap_to_pixel_grid(), {'FINISHED'})

    def test_snap_now_in_edit_mode_is_an_error(self):
        obj = self.off_grid_cube()
        select_only(obj)
        bpy.ops.object.mode_set(mode='EDIT')
        try:
            with self.assertRaises(RuntimeError):
                bpy.ops.hytale.snap_to_pixel_grid()
        finally:
            bpy.ops.object.mode_set(mode='OBJECT')

    def test_set_grid_snapping_turns_on_increment_snapping(self):
        bpy.ops.hytale.set_grid_snapping()
        self.assertTrue(bpy.context.tool_settings.use_snap)
        self.assertEqual(set(bpy.context.tool_settings.snap_elements), {'INCREMENT'})

    def test_pixel_grid_panel_draws(self):
        panel = SimpleNamespace(layout=mock.MagicMock())
        self.addon.modules.pixel_grid_ui.HYTALE_PT_pixel_grid.draw(panel, bpy.context)
        self.assertTrue(panel.layout.prop.called)
        self.assertTrue(panel.layout.operator.called)


@unittest.skipUnless(_blender_stubs.IN_BLENDER, "needs Blender")
class ExporterUi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.addon = load_addon()

    def test_export_menu_entry_is_added(self):
        layout = mock.MagicMock()
        self.addon.modules.exporter.menu_func_export(SimpleNamespace(layout=layout), None)
        layout.operator.assert_called_once()

    def test_model_export_panel_draws_every_section(self):
        from unittest.mock import MagicMock
        layout = MagicMock()
        layout.panel.return_value = (MagicMock(), MagicMock())
        ns = SimpleNamespace(layout=layout, collection="", source_collection="__selected__",
                             export_selected_only=True, apply_modifiers=True, model_format="prop",
                             double_sided_panes=True, export_texture=False, texture_size_mode="MULTIPLE_32",
                             per_face_uvs=True, uv_source="AUTO", padding=1)
        self.addon.modules.exporter.EXPORT_SCENE_OT_blockymodel.draw(ns, bpy.context)
        self.assertEqual(layout.panel.call_count, 3)

    def test_collection_list_has_selected_item_first(self):
        coll = bpy.data.collections.new("Parts")
        bpy.context.scene.collection.children.link(coll)
        items = self.addon.modules.exporter._collection_items(None, bpy.context)
        self.assertEqual(items[0][0], "__selected__")
        self.assertIn("Parts", [item[0] for item in items])


@unittest.skipUnless(_blender_stubs.IN_BLENDER, "needs Blender")
class Registration(unittest.TestCase):
    def test_properties_are_removed_and_added_again(self):
        addon = load_addon()
        addon.unregister()
        self.assertFalse(hasattr(bpy.types.Scene, "hytale_export_name"))
        addon.register()
        self.assertTrue(hasattr(bpy.types.Scene, "hytale_export_name"))
        self.assertTrue(hasattr(bpy.types.Scene, "hytale_export_overwrite_texture"))


@unittest.skipUnless(_blender_stubs.IN_BLENDER, "needs Blender")
class CubeSeamCheck(unittest.TestCase):
    def test_cube_seam_check_runs_and_is_cached(self):
        from modules import uvs
        uvs._CUBE_SEAMS_OK = None
        first = uvs._cube_seams_ok()
        self.assertIsInstance(first, bool)
        self.assertEqual(uvs._cube_seams_ok(), first)


if __name__ == "__main__":
    unittest.main()
