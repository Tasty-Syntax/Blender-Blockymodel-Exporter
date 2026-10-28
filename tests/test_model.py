import unittest

from tests import _blender_stubs  # noqa: F401  (must come before bpy is imported)

import bpy

from tests.mesh_helpers import add_box, add_quad, make_object, reset_scene
from modules import model


def build(objects, units=32, double_sided=True):
    return model.build_model(objects, units, None, double_sided, bpy.context.scene.collection)


@unittest.skipUnless(_blender_stubs.IN_BLENDER, "needs Blender's bmesh and mathutils")
class BuildModel(unittest.TestCase):
    def setUp(self):
        reset_scene()

    def test_cube_becomes_one_box_node(self):
        obj = make_object("cube", lambda bm: add_box(bm, (0, 0, 0), (1, 1, 1)))
        res = build([obj])
        self.assertEqual(len(res.nodes), 1)
        node = res.nodes[0]
        self.assertEqual(node["shape"]["type"], "box")
        self.assertEqual(node["shape"]["settings"]["size"], {"x": 32, "y": 32, "z": 32})
        self.assertEqual(res.node_count, 1)
        self.assertEqual(len(res.uv_requests), 1)
        self.assertEqual(res.non_integer, 0)

    def test_character_units_double_the_size(self):
        obj = make_object("cube", lambda bm: add_box(bm, (0, 0, 0), (1, 1, 1)))
        node = build([obj], units=64).nodes[0]
        self.assertEqual(node["shape"]["settings"]["size"], {"x": 64, "y": 64, "z": 64})

    def test_pane_becomes_quad_node(self):
        obj = make_object("pane", lambda bm: add_quad(bm, [(0, 0, 0.5), (1, 0, 0.5), (1, 1, 0.5), (0, 1, 0.5)]))
        node = build([obj]).nodes[0]
        self.assertEqual(node["shape"]["type"], "quad")
        self.assertEqual(node["shape"]["settings"]["normal"], "+Z")

    def test_double_sided_option_reaches_the_quad(self):
        obj = make_object("pane", lambda bm: add_quad(bm, [(0, 0, 0.5), (1, 0, 0.5), (1, 1, 0.5), (0, 1, 0.5)]))
        self.assertTrue(build([obj], double_sided=True).nodes[0]["shape"]["doubleSided"])
        self.assertFalse(build([obj], double_sided=False).nodes[0]["shape"]["doubleSided"])

    def test_off_grid_size_is_counted(self):
        obj = make_object("odd", lambda bm: add_box(bm, (0, 0, 0), (1.01, 1, 1)))
        self.assertGreaterEqual(build([obj]).non_integer, 1)

    def test_joined_pieces_become_child_nodes(self):
        def two_boxes(bm):
            add_box(bm, (0, 0, 0), (1, 1, 1))
            add_box(bm, (0, 0, 2), (1, 1, 3))
        obj = make_object("joined", two_boxes)
        res = build([obj])
        node = res.nodes[0]
        self.assertEqual(len(node["children"]), 1)
        self.assertEqual(node["children"][0]["name"], "joined--C1")
        self.assertEqual(len(res.uv_requests), 2)

    def test_child_object_is_nested_under_parent(self):
        parent = make_object("parent", lambda bm: add_box(bm, (0, 0, 0), (1, 1, 1)))
        child = make_object("child", lambda bm: add_box(bm, (0, 0, 0), (1, 1, 1)))
        child.location = (3, 0, 0)
        child.parent = parent
        bpy.context.view_layer.update()
        res = build([parent, child])
        self.assertEqual(len(res.nodes), 1)
        self.assertEqual([c["name"] for c in res.nodes[0]["children"]], ["child"])

    def test_collection_becomes_group_node(self):
        obj = make_object("part", lambda bm: add_box(bm, (0, 0, 0), (1, 1, 1)))
        coll = bpy.data.collections.new("Parts")
        bpy.context.scene.collection.children.link(coll)
        bpy.context.scene.collection.objects.unlink(obj)
        coll.objects.link(obj)
        res = build([obj])
        self.assertEqual(res.nodes[0]["name"], "Parts")
        self.assertEqual(res.nodes[0]["children"][0]["name"], "part")


if __name__ == "__main__":
    unittest.main()
