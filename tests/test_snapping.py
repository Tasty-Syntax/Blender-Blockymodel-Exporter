import unittest

from tests import _blender_stubs  # noqa: F401  (must come before bpy is imported)

import bpy

from tests.mesh_helpers import add_box, add_quad, make_object, reset_scene
from modules import snapping


def extent_x(obj):
    xs = [v.co.x for v in obj.data.vertices]
    return max(xs) - min(xs)


@unittest.skipUnless(_blender_stubs.IN_BLENDER, "needs Blender's bmesh and mathutils")
class SnapObject(unittest.TestCase):
    def setUp(self):
        reset_scene()

    def test_off_grid_box_snaps_to_next_pixel(self):
        obj = make_object("box", lambda bm: add_box(bm, (0, 0, 0), (1.02, 1, 1)))
        self.assertTrue(snapping._snap_object(obj, 32))
        self.assertAlmostEqual(extent_x(obj), 33 / 32, places=5)

    def test_character_density_uses_64_pixels(self):
        obj = make_object("box", lambda bm: add_box(bm, (0, 0, 0), (1.02, 1, 1)))
        self.assertTrue(snapping._snap_object(obj, 64))
        self.assertAlmostEqual(extent_x(obj), 65 / 64, places=5)

    def test_aligned_box_is_left_alone(self):
        obj = make_object("box", lambda bm: add_box(bm, (0, 0, 0), (1, 1, 1)))
        self.assertFalse(snapping._snap_object(obj, 32))
        self.assertAlmostEqual(extent_x(obj), 1.0, places=5)

    def test_pane_flat_side_is_ignored(self):
        obj = make_object("pane", lambda bm: add_quad(bm, [(0, 0, 0.5), (0.5, 0, 0.5), (0.5, 0.5, 0.5), (0, 0.5, 0.5)]))
        self.assertFalse(snapping._snap_object(obj, 32))

    def test_empty_object_is_skipped(self):
        obj = bpy.data.objects.new("empty", None)
        bpy.context.scene.collection.objects.link(obj)
        self.assertFalse(snapping._snap_object(obj, 32))


if __name__ == "__main__":
    unittest.main()
