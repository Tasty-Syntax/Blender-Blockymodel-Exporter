import unittest

from tests import _blender_stubs  # noqa: F401  (must come before bpy is imported)

import bpy
from mathutils import Vector

from tests.mesh_helpers import add_box, add_quad, make_object, reset_scene
from modules import geometry


@unittest.skipUnless(_blender_stubs.IN_BLENDER, "needs Blender's bmesh and mathutils")
class MeshParts(unittest.TestCase):
    def setUp(self):
        reset_scene()

    def test_cube_is_one_box(self):
        obj = make_object("cube", lambda bm: add_box(bm, (0, 0, 0), (1, 1, 1)))
        parts = geometry.mesh_parts(obj, None)
        self.assertEqual(len(parts), 1)
        part = parts[0]
        self.assertEqual(part.kind, 'BOX')
        self.assertTrue(part.clean)
        self.assertIsNone(part.rot)
        for i in range(3):
            self.assertAlmostEqual(part.size[i], 1.0, places=5)
            self.assertAlmostEqual(part.center[i], 0.5, places=5)

    def test_flat_quad_is_a_pane(self):
        obj = make_object("pane", lambda bm: add_quad(bm, [(0, 0, 0.5), (1, 0, 0.5), (1, 1, 0.5), (0, 1, 0.5)]))
        part = geometry.mesh_parts(obj, None)[0]
        self.assertEqual(part.kind, 'PANE')
        self.assertEqual(part.flat_axis, 2)
        self.assertAlmostEqual(part.size[2], 0.0, places=5)
        self.assertAlmostEqual(part.size[0], 1.0, places=5)

    def test_pane_facing_follows_winding(self):
        corners = [(0, 0, 0.5), (1, 0, 0.5), (1, 1, 0.5), (0, 1, 0.5)]
        up = geometry.mesh_parts(make_object("up", lambda bm: add_quad(bm, corners)), None)[0]
        down = geometry.mesh_parts(make_object("down", lambda bm: add_quad(bm, corners[::-1])), None)[0]
        self.assertEqual(up.normal_sign, 1)
        self.assertEqual(down.normal_sign, -1)

    def test_two_separate_boxes_are_two_parts_sorted_by_position(self):
        def build(bm):
            add_box(bm, (0, 0, 2), (1, 1, 3))
            add_box(bm, (0, 0, 0), (1, 1, 1))
        parts = geometry.mesh_parts(make_object("pair", build), None)
        self.assertEqual(len(parts), 2)
        self.assertLess(parts[0].center.z, parts[1].center.z)

    def test_object_scale_is_applied(self):
        obj = make_object("scaled", lambda bm: add_box(bm, (0, 0, 0), (1, 1, 1)))
        obj.scale = (2.0, 2.0, 2.0)
        bpy.context.view_layer.update()
        part = geometry.mesh_parts(obj, None)[0]
        self.assertAlmostEqual(part.size[0], 2.0, places=5)

    def test_single_vertex_is_ignored(self):
        def build(bm):
            bm.verts.new((0, 0, 0))
        self.assertEqual(geometry.mesh_parts(make_object("dot", build), None), [])

    def test_bent_box_is_flagged_unclean(self):
        def build(bm):
            add_box(bm, (0, 0, 0), (1, 1, 1))
            bm.verts.ensure_lookup_table()
            bm.verts[0].co = bm.verts[0].co + Vector((0.3, 0.3, 0.3))
        part = geometry.mesh_parts(make_object("bent", build), None)[0]
        self.assertFalse(part.clean)



if __name__ == "__main__":
    unittest.main()
