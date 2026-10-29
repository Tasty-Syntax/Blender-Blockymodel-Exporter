import json
import math
import os
import tempfile
import unittest

from tests import _blender_stubs  # noqa: F401  (must come before bpy is imported)

import bpy

from tests.addon_loader import load_addon
from tests.mesh_helpers import add_box, add_quad, make_object, reset_scene

UV_MAP = "Hytale"


def select_only(obj):
    for other in bpy.context.scene.objects:
        other.select_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def build(objects):
    from modules import model
    return model.build_model(objects, 32, None, True, bpy.context.scene.collection)


@unittest.skipUnless(_blender_stubs.IN_BLENDER, "needs Blender")
class GenerateUvs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.addon = load_addon()

    def setUp(self):
        reset_scene()
        self.scene = bpy.context.scene
        self.scene.hytale_format = 'prop'
        self.scene.hytale_export_collection = None
        self.scene.hytale_uv_source = 'AUTO'
        self.scene.hytale_uv_per_face = True
        self.scene.hytale_uv_square = True
        self.scene.hytale_uv_padding = 1
        self.scene.hytale_uv_size_mode = 'MULTIPLE_32'
        self.dir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.dir.name, "model.blockymodel")
        self.cube = make_object("cube", lambda bm: add_box(bm, (0, 0, 0), (1, 1, 0.5)))
        select_only(self.cube)

    def tearDown(self):
        self.dir.cleanup()

    def export(self, **kwargs):
        bpy.ops.export_scene.blockymodel('EXEC_DEFAULT', filepath=self.path, **kwargs)
        with open(self.path, encoding="utf-8") as f:
            return json.load(f)["nodes"][0]["shape"]["textureLayout"]

    def face_loops(self, obj, face):
        """Loop indices of one Hytale face of a single-piece object."""
        from modules import uvs
        _node, uv_faces, _obj, part = build([obj]).uv_requests[0]
        return [li for li, _s, _t, _uv in uvs.face_loops(part, uv_faces)[face]]

    def test_writes_the_uv_map_and_switches_to_it(self):
        self.assertEqual(bpy.ops.hytale.generate_uvs(), {'FINISHED'})
        self.assertIn(UV_MAP, self.cube.data.uv_layers)
        self.assertEqual(self.cube.data.uv_layers.active.name, UV_MAP)
        self.assertEqual(self.scene.hytale_uv_source, 'MESH')
        self.assertEqual((self.scene.hytale_uv_width % 32, self.scene.hytale_uv_height % 32), (0, 0))
        image = bpy.data.images[self.addon.modules.uv_ui.IMAGE_NAME]
        self.assertEqual(tuple(image.size), (self.scene.hytale_uv_width, self.scene.hytale_uv_height))

    def test_texture_is_square_unless_turned_off(self):
        bpy.ops.hytale.generate_uvs()
        self.assertEqual(self.scene.hytale_uv_width, self.scene.hytale_uv_height)
        self.scene.hytale_uv_square = False
        self.scene.hytale_uv_per_face = False
        bpy.ops.hytale.generate_uvs()
        self.assertNotEqual(self.scene.hytale_uv_width, self.scene.hytale_uv_height)

    def test_padding_is_used(self):
        self.scene.hytale_uv_padding = 0
        bpy.ops.hytale.generate_uvs()
        tight = self.export(uv_source='MESH')
        self.scene.hytale_uv_padding = 5
        bpy.ops.hytale.generate_uvs()
        loose = self.export(uv_source='MESH')
        self.assertNotEqual(tight, loose)
        self.assertEqual(self.export(uv_source='AUTO', padding=5), loose)

    def test_faces_keep_their_pixel_size(self):
        bpy.ops.hytale.generate_uvs()
        w, h = self.scene.hytale_uv_width, self.scene.hytale_uv_height
        uv = self.cube.data.uv_layers[UV_MAP].data
        loops = self.face_loops(self.cube, "front")
        xs = [uv[li].uv[0] * w for li in loops]
        ys = [uv[li].uv[1] * h for li in loops]
        self.assertAlmostEqual(max(xs) - min(xs), 32, places=3)
        self.assertAlmostEqual(max(ys) - min(ys), 16, places=3)

    def test_image_is_shown_in_every_workspace(self):
        bpy.ops.hytale.generate_uvs()
        image = bpy.data.images[self.addon.modules.uv_ui.IMAGE_NAME]
        spaces = [a.spaces.active for screen in bpy.data.screens for a in screen.areas
                  if a.type == 'IMAGE_EDITOR']
        self.assertTrue(spaces)
        for space in spaces:
            self.assertEqual(space.image, image)

    def test_untouched_uvs_export_like_the_automatic_layout(self):
        auto = self.export(uv_source='AUTO')
        bpy.ops.hytale.generate_uvs()
        self.assertEqual(self.export(uv_source='MESH'), auto)

    def test_front_texture_starts_at_the_top_left_corner(self):
        # Seen from the front (-Y), the top-left corner is min X, max Z
        bpy.ops.hytale.generate_uvs()
        layout = self.export(uv_source='MESH')["front"]
        mesh = self.cube.data
        uv = mesh.uv_layers[UV_MAP].data
        for li in self.face_loops(self.cube, "front"):
            co = mesh.vertices[mesh.loops[li].vertex_index].co
            if co.x < 0.5 and co.z > 0.25:
                x = uv[li].uv[0] * self.scene.hytale_uv_width
                y = (1 - uv[li].uv[1]) * self.scene.hytale_uv_height
                self.assertAlmostEqual(x, layout["offset"]["x"], places=3)
                self.assertAlmostEqual(y, layout["offset"]["y"], places=3)
                return
        self.fail("no top-left loop on the front face")

    def test_moved_island_moves_the_offset(self):
        bpy.ops.hytale.generate_uvs()
        before = self.export(uv_source='MESH')["front"]["offset"]
        uv = self.cube.data.uv_layers[UV_MAP].data
        for li in self.face_loops(self.cube, "front"):
            uv[li].uv[0] += 3 / self.scene.hytale_uv_width
        after = self.export(uv_source='MESH')["front"]["offset"]
        self.assertEqual(after, {"x": before["x"] + 3, "y": before["y"]})

    def test_turned_island_sets_the_angle(self):
        bpy.ops.hytale.generate_uvs()
        w, h = self.scene.hytale_uv_width, self.scene.hytale_uv_height
        uv = self.cube.data.uv_layers[UV_MAP].data
        loops = self.face_loops(self.cube, "front")
        # Turn the island by 90 degrees about its first corner, in pixel space
        px = [(uv[li].uv[0] * w, (1 - uv[li].uv[1]) * h) for li in loops]
        cx, cy = min(p[0] for p in px), min(p[1] for p in px) + 40
        for li, (x, y) in zip(loops, px):
            nx, ny = cx - (y - cy), cy + (x - cx)
            uv[li].uv = (nx / w, 1 - ny / h)
        entry = self.export(uv_source='MESH')["front"]
        self.assertIn(entry["angle"], (90, 270))

    def test_stretched_island_is_a_warning(self):
        bpy.ops.hytale.generate_uvs()
        uv = self.cube.data.uv_layers[UV_MAP].data
        for li in self.face_loops(self.cube, "front"):
            uv[li].uv[0] *= 1.5
        bpy.ops.export_scene.blockymodel('EXEC_DEFAULT', filepath=self.path, uv_source='MESH')
        # Still exported; the face is placed at the top-left of its UVs
        self.assertTrue(os.path.exists(self.path))

    def test_mesh_source_without_uv_map_still_exports(self):
        self.export(uv_source='MESH')
        self.assertTrue(os.path.exists(os.path.splitext(self.path)[0] + ".png"))

    def test_linked_duplicates_are_laid_out_once(self):
        def painted_pixels():
            image = bpy.data.images[self.addon.modules.uv_ui.IMAGE_NAME]
            return sum(1 for a in list(image.pixels)[3::4] if a > 0)

        bpy.ops.hytale.generate_uvs()
        alone = painted_pixels()
        twin = self.cube.copy()   # Alt+D: shares the cube's mesh
        twin.location.x = 3
        self.scene.collection.objects.link(twin)
        twin.select_set(True)
        bpy.ops.hytale.generate_uvs()
        self.assertEqual(painted_pixels(), alone)

    def pixel_layout(self):
        return self.export(uv_source='MESH')

    def test_fit_texture_shrinks_to_the_islands_and_keeps_their_pixels(self):
        self.scene.hytale_uv_square = False
        self.scene.hytale_uv_padding = 40   # leaves a lot of empty texture
        bpy.ops.hytale.generate_uvs()
        before = self.pixel_layout()
        size_before = (self.scene.hytale_uv_width, self.scene.hytale_uv_height)
        self.assertEqual(bpy.ops.hytale.fit_texture(), {'FINISHED'})
        size_after = (self.scene.hytale_uv_width, self.scene.hytale_uv_height)
        self.assertLessEqual(size_after[0], size_before[0])
        self.assertLessEqual(size_after[1], size_before[1])
        self.assertLess(size_after[0] * size_after[1], size_before[0] * size_before[1])
        self.assertEqual(self.pixel_layout(), before)
        image = bpy.data.images[self.addon.modules.uv_ui.IMAGE_NAME]
        self.assertEqual(tuple(image.size), size_after)

    def test_fit_texture_grows_for_an_island_moved_outside(self):
        bpy.ops.hytale.generate_uvs()
        w, h = self.scene.hytale_uv_width, self.scene.hytale_uv_height
        uv = self.cube.data.uv_layers[UV_MAP].data
        for li in self.face_loops(self.cube, "front"):
            uv[li].uv[0] += 100 / w
        moved = self.pixel_layout()
        bpy.ops.hytale.fit_texture()
        self.assertGreater(self.scene.hytale_uv_width, w)
        self.assertEqual(self.pixel_layout(), moved)

    def test_fit_texture_works_from_edit_mode(self):
        bpy.ops.hytale.generate_uvs()
        bpy.ops.object.mode_set(mode='EDIT')
        try:
            self.assertEqual(bpy.ops.hytale.fit_texture(), {'FINISHED'})
            self.assertEqual(bpy.context.mode, 'EDIT_MESH')
        finally:
            bpy.ops.object.mode_set(mode='OBJECT')

    def test_fit_texture_without_uv_map_is_an_error(self):
        with self.assertRaises(RuntimeError):
            bpy.ops.hytale.fit_texture()

    def test_edit_mode_is_an_error(self):
        bpy.ops.object.mode_set(mode='EDIT')
        try:
            with self.assertRaises(RuntimeError):
                bpy.ops.hytale.generate_uvs()
        finally:
            bpy.ops.object.mode_set(mode='OBJECT')

    def test_nothing_selected_is_an_error(self):
        self.cube.select_set(False)
        with self.assertRaises(RuntimeError):
            bpy.ops.hytale.generate_uvs()

    def test_panel_passes_the_uv_source(self):
        bpy.ops.hytale.generate_uvs()
        self.scene.hytale_export_name = self.path
        self.scene.hytale_export_overwrite = True
        try:
            uv = self.cube.data.uv_layers[UV_MAP].data
            for li in self.face_loops(self.cube, "top"):
                uv[li].uv[1] -= 2 / self.scene.hytale_uv_height
            bpy.ops.hytale.export_model('EXEC_DEFAULT')
        finally:
            self.scene.hytale_export_overwrite = False
        with open(self.path, encoding="utf-8") as f:
            top = json.load(f)["nodes"][0]["shape"]["textureLayout"]["top"]
        auto = build([self.cube])
        from modules import uvs
        uvs.layout_uvs(auto.uv_requests, 'MULTIPLE_32', per_face=True)
        expected = auto.nodes[0]["shape"]["textureLayout"]["top"]["offset"]
        self.assertEqual(top["offset"], {"x": expected["x"], "y": expected["y"] + 2})

    def test_export_panel_draws_the_uv_section(self):
        from types import SimpleNamespace
        from unittest import mock
        panel = SimpleNamespace(layout=mock.MagicMock())
        self.scene.hytale_uv_source = 'AUTO'
        self.addon.modules.export_ui.HYTALE_PT_export.draw(panel, bpy.context)
        drawn = [c.args[1] for c in panel.layout.prop.call_args_list]
        self.assertNotIn("hytale_uv_padding", drawn)
        self.scene.hytale_uv_source = 'MESH'
        self.addon.modules.export_ui.HYTALE_PT_export.draw(panel, bpy.context)
        drawn = [c.args[1] for c in panel.layout.prop.call_args_list]
        for name in ("hytale_uv_per_face", "hytale_uv_square", "hytale_uv_padding",
                     "hytale_uv_size_mode"):
            self.assertIn(name, drawn)
        panel.layout.operator.assert_any_call("hytale.generate_uvs", icon='UV')
        ops = [c.args[0] for c in panel.layout.operator.call_args_list]
        self.assertEqual(ops.index("hytale.fit_texture"), ops.index("hytale.generate_uvs") + 1)


@unittest.skipUnless(_blender_stubs.IN_BLENDER, "needs Blender")
class UvRoundTrip(unittest.TestCase):
    """Every textureLayout written into the UV map is read back unchanged."""

    def setUp(self):
        reset_scene()

    def round_trip(self, objects):
        from modules import uvs
        res = build(objects)
        uvs.layout_uvs(res.uv_requests, 'MULTIPLE_32', per_face=True)
        width = height = 1024
        for i, (node, _uv_faces, _o, _p) in enumerate(res.uv_requests):
            for j, entry in enumerate(node["shape"]["textureLayout"].values()):
                mirror, angle = uvs._CANDIDATES[(i + j) % len(uvs._CANDIDATES)]
                entry["mirror"] = {"x": mirror[0], "y": mirror[1]}
                entry["angle"] = angle
                entry["offset"] = {"x": entry["offset"]["x"] + 128, "y": entry["offset"]["y"] + 128}
        written = [json.dumps(n["shape"]["textureLayout"], sort_keys=True)
                   for n, *_ in res.uv_requests]
        uvs.write_mesh_uvs(res.uv_requests, width, height)

        again = build(objects)
        _paint, warnings = uvs.read_mesh_uvs(again.uv_requests, width, height)
        self.assertEqual(warnings, [])
        read = [json.dumps(n["shape"]["textureLayout"], sort_keys=True)
                for n, *_ in again.uv_requests]
        self.assertEqual(read, written)

    def test_box(self):
        self.round_trip([make_object("box", lambda bm: add_box(bm, (0, 0, 0), (1, 0.5, 0.25)))])

    def test_pane(self):
        corners = [(0, 0, 0.5), (1, 0, 0.5), (1, 0.5, 0.5), (0, 0.5, 0.5)]
        self.round_trip([make_object("pane", lambda bm: add_quad(bm, corners))])

    def test_upside_down_pane(self):
        corners = [(0, 0, 0.5), (0, 0.5, 0.5), (1, 0.5, 0.5), (1, 0, 0.5)]
        self.round_trip([make_object("pane", lambda bm: add_quad(bm, corners))])

    def test_joined_and_tilted_pieces(self):
        def build_mesh(bm):
            add_box(bm, (0, 0, 0), (1, 1, 1))
            add_box(bm, (2, 0, 0), (2.5, 0.25, 1))
            add_quad(bm, [(4, 0, 0), (4, 1, 0), (4, 1, 1), (4, 0, 1)])
        obj = make_object("joined", build_mesh)
        # Tilt the second box inside the mesh, as an Edit Mode rotation would
        from mathutils import Matrix, Vector
        rot = Matrix.Rotation(math.radians(30), 3, 'Z')
        for v in obj.data.vertices:
            if 1.5 < v.co.x < 3:
                v.co = rot @ (v.co - Vector((2.25, 0.125, 0.5))) + Vector((2.25, 0.125, 0.5))
        self.round_trip([obj])

    def test_scaled_and_rotated_object(self):
        obj = make_object("box", lambda bm: add_box(bm, (0, 0, 0), (1, 1, 1)))
        obj.scale = (2, 0.5, 1)
        obj.rotation_euler = (0.3, 0, 1.2)
        bpy.context.view_layer.update()
        self.round_trip([obj])


if __name__ == "__main__":
    unittest.main()
