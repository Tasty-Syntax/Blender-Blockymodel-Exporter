import json
import os
import tempfile
import unittest

from tests import _blender_stubs  # noqa: F401  (must come before bpy is imported)

import bpy

from tests.addon_loader import load_addon
from tests.mesh_helpers import add_box, make_object, reset_scene

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def select_only(obj):
    for other in bpy.context.scene.objects:
        other.select_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


@unittest.skipUnless(_blender_stubs.IN_BLENDER, "needs Blender")
class ExportOperator(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        load_addon()

    def setUp(self):
        reset_scene()
        self.dir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.dir.name, "model.blockymodel")
        self.cube = make_object("cube", lambda bm: add_box(bm, (0, 0, 0), (1, 1, 1)))
        select_only(self.cube)

    def tearDown(self):
        self.dir.cleanup()

    def export(self, **kwargs):
        return bpy.ops.export_scene.blockymodel('EXEC_DEFAULT', filepath=self.path, **kwargs)

    def read_model(self):
        with open(self.path, encoding="utf-8") as f:
            return json.load(f)

    def test_writes_model_and_texture(self):
        self.assertEqual(self.export(), {'FINISHED'})
        model = self.read_model()
        self.assertEqual(len(model["nodes"]), 1)
        self.assertEqual(model["format"], "prop")
        with open(os.path.splitext(self.path)[0] + ".png", "rb") as f:
            self.assertEqual(f.read(8), PNG_SIGNATURE)

    def test_export_texture_off_writes_no_png(self):
        self.export(export_texture=False)
        self.assertFalse(os.path.exists(os.path.splitext(self.path)[0] + ".png"))

    def test_character_format_doubles_the_size(self):
        self.export(model_format="character")
        size = self.read_model()["nodes"][0]["shape"]["settings"]["size"]
        self.assertEqual(size, {"x": 64, "y": 64, "z": 64})

    def test_collection_is_exported_as_a_group(self):
        coll = bpy.data.collections.new("Parts")
        bpy.context.scene.collection.children.link(coll)
        bpy.context.scene.collection.objects.unlink(self.cube)
        coll.objects.link(self.cube)
        self.export(collection="Parts")
        self.assertEqual(self.read_model()["nodes"][0]["name"], "Parts")

    def test_source_collection_choice_is_used(self):
        coll = bpy.data.collections.new("Parts")
        bpy.context.scene.collection.children.link(coll)
        bpy.context.scene.collection.objects.unlink(self.cube)
        coll.objects.link(self.cube)
        self.export(source_collection="Parts")
        self.assertEqual(self.read_model()["nodes"][0]["name"], "Parts")

    def test_nothing_selected_is_an_error(self):
        for obj in bpy.context.scene.objects:
            obj.select_set(False)
        with self.assertRaises(RuntimeError):
            self.export()

    def test_unknown_collection_is_an_error(self):
        with self.assertRaises(RuntimeError):
            self.export(collection="Missing")

    def test_unwritable_path_is_an_error(self):
        with self.assertRaises(RuntimeError):
            bpy.ops.export_scene.blockymodel('EXEC_DEFAULT', filepath=self.dir.name)


@unittest.skipUnless(_blender_stubs.IN_BLENDER, "needs Blender")
class PanelExport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.addon = load_addon()

    def setUp(self):
        reset_scene()
        self.dir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.dir.name, "model.blockymodel")
        self.texture = os.path.join(self.dir.name, "model.png")
        select_only(make_object("cube", lambda bm: add_box(bm, (0, 0, 0), (1, 1, 1))))
        self.scene = bpy.context.scene
        self.scene.hytale_export_name = self.path
        self.attempted = self.addon.modules.export_ui._EXPORT_ATTEMPTED
        self.attempted[0] = False
        self.scene.hytale_export_texture = True

    def tearDown(self):
        self.dir.cleanup()
        self.scene.hytale_export_texture = True
        self.scene.hytale_export_overwrite = False
        self.scene.hytale_export_overwrite_texture = False

    def press_export(self):
        return bpy.ops.hytale.export_model('EXEC_DEFAULT')

    def test_writes_the_file_named_in_the_path_field(self):
        self.press_export()
        self.assertTrue(os.path.exists(self.path))

    def test_extension_is_added_when_missing(self):
        self.scene.hytale_export_name = os.path.join(self.dir.name, "bare")
        self.press_export()
        self.assertTrue(os.path.exists(os.path.join(self.dir.name, "bare.blockymodel")))

    def test_empty_name_is_an_error_and_highlights_the_field(self):
        self.scene.hytale_export_name = ""
        with self.assertRaises(RuntimeError):
            self.press_export()
        self.assertTrue(self.attempted[0])

    def test_success_clears_the_highlight(self):
        self.attempted[0] = True
        self.press_export()
        self.assertFalse(self.attempted[0])

    def test_existing_file_needs_overwrite(self):
        with open(self.path, "w") as f:
            f.write("old")
        with self.assertRaises(RuntimeError):
            self.press_export()
        self.scene.hytale_export_overwrite = True
        self.press_export()
        self.assertNotEqual(open(self.path).read(), "old")

    def test_existing_texture_is_kept_unless_overwrite_texture(self):
        with open(self.texture, "wb") as f:
            f.write(b"keep")
        self.scene.hytale_export_overwrite = True
        self.press_export()
        with open(self.texture, "rb") as f:
            self.assertEqual(f.read(), b"keep")

    def test_overwrite_texture_replaces_the_texture(self):
        with open(self.texture, "wb") as f:
            f.write(b"keep")
        self.scene.hytale_export_overwrite = True
        self.scene.hytale_export_overwrite_texture = True
        self.press_export()
        with open(self.texture, "rb") as f:
            self.assertEqual(f.read(8), PNG_SIGNATURE)

    def test_export_texture_off_writes_no_texture(self):
        self.scene.hytale_export_texture = False
        self.press_export()
        self.assertTrue(os.path.exists(self.path))
        self.assertFalse(os.path.exists(self.texture))

    def test_export_texture_off_ignores_an_existing_texture(self):
        with open(self.texture, "wb") as f:
            f.write(b"keep")
        self.scene.hytale_export_texture = False
        self.press_export()   # no Overwrite Existing needed: the texture is not written
        self.assertTrue(os.path.exists(self.path))
        with open(self.texture, "rb") as f:
            self.assertEqual(f.read(), b"keep")

    def test_unchecking_overwrite_also_unchecks_overwrite_texture(self):
        self.scene.hytale_export_overwrite = True
        self.scene.hytale_export_overwrite_texture = True
        self.scene.hytale_export_overwrite = False
        self.assertFalse(self.scene.hytale_export_overwrite_texture)

    def test_file_picker_sets_the_path_field(self):
        bpy.ops.hytale.choose_export_file('EXEC_DEFAULT', filepath=os.path.join(self.dir.name, "picked.blockymodel"))
        self.assertEqual(self.scene.hytale_export_name, os.path.join(self.dir.name, "picked.blockymodel"))

    def test_export_panel_draws(self):
        from types import SimpleNamespace
        from unittest import mock
        panel = SimpleNamespace(layout=mock.MagicMock())
        self.addon.modules.export_ui.HYTALE_PT_export.draw(panel, bpy.context)
        self.attempted[0] = True
        self.addon.modules.export_ui.HYTALE_PT_export.draw(panel, bpy.context)
        self.assertTrue(panel.layout.operator.called)


if __name__ == "__main__":
    unittest.main()
