import unittest

from tests import _blender_stubs  # noqa: F401  (must come before the add-on imports)
from modules import uvs


def box_faces(sx, sy, sz):
    return {
        "front": (sx, sy), "back": (sx, sy),
        "left": (sz, sy), "right": (sz, sy),
        "top": (sx, sz), "bottom": (sx, sz),
    }


class SnapTextureDimension(unittest.TestCase):
    def test_multiple_of_32_rounds_up(self):
        self.assertEqual(uvs.snap_texture_dimension(1), 32)
        self.assertEqual(uvs.snap_texture_dimension(32), 32)
        self.assertEqual(uvs.snap_texture_dimension(33), 64)
        self.assertEqual(uvs.snap_texture_dimension(129), 160)

    def test_power_of_two(self):
        self.assertEqual(uvs.snap_texture_dimension(1, 'POWER_OF_TWO'), 32)
        self.assertEqual(uvs.snap_texture_dimension(33, 'POWER_OF_TWO'), 64)
        self.assertEqual(uvs.snap_texture_dimension(129, 'POWER_OF_TWO'), 256)

    def test_zero_is_clamped_to_one_step(self):
        self.assertEqual(uvs.snap_texture_dimension(0), 32)


class PixelExtent(unittest.TestCase):
    def test_whole_numbers_stay_exact(self):
        self.assertEqual(uvs._px(32), 32)
        self.assertEqual(uvs._px(32.0004), 32)

    def test_fractions_are_truncated_like_blockbench(self):
        self.assertEqual(uvs._px(6.517), 6)
        self.assertEqual(uvs._px(9.4839), 9)


class BoxNet(unittest.TestCase):
    def test_single_cube_net_is_a_cross(self):
        w, h, rects = uvs._net(box_faces(32, 32, 32))
        self.assertEqual((w, h), (128, 64))
        self.assertEqual(rects["front"], (32, 32, 32, 32))
        self.assertEqual(rects["top"], (32, 0, 32, 32))

    def test_pane_net_is_one_rectangle(self):
        w, h, rects = uvs._net({"front": (64, 32)})
        self.assertEqual((w, h), (64, 32))
        self.assertEqual(rects, {"front": (0, 0, 64, 32)})

    def test_faces_do_not_overlap(self):
        _, _, rects = uvs._net(box_faces(10, 20, 30))
        cells = set()
        for x, y, w, h in rects.values():
            for i in range(x, x + w):
                for j in range(y, y + h):
                    self.assertNotIn((i, j), cells)
                    cells.add((i, j))


class LayoutUvs(unittest.TestCase):
    def make_node(self):
        return {"shape": {"textureLayout": {}}}

    def test_writes_a_layout_entry_for_every_face(self):
        node = self.make_node()
        uvs.layout_uvs([(node, box_faces(32, 32, 32), (200, 100, 50))], 'MULTIPLE_32')
        self.assertEqual(set(node["shape"]["textureLayout"]), set(box_faces(1, 1, 1)))
        for entry in node["shape"]["textureLayout"].values():
            self.assertEqual(entry["angle"], 0)
            self.assertFalse(entry["mirror"]["x"] or entry["mirror"]["y"])

    def test_atlas_size_is_a_multiple_of_32(self):
        node = self.make_node()
        w, h, _ = uvs.layout_uvs([(node, box_faces(32, 32, 32), (1, 2, 3))], 'MULTIPLE_32')
        self.assertEqual(w % 32, 0)
        self.assertEqual(h % 32, 0)

    def test_islands_stay_inside_the_atlas_and_do_not_overlap(self):
        requests = []
        for size in (16, 32, 48, 8):
            requests.append((self.make_node(), box_faces(size, size, size), (9, 9, 9)))
        w, h, paint = uvs.layout_uvs(requests, 'MULTIPLE_32')
        cells = set()
        for x, y, pw, ph, _face, _color in paint:
            self.assertLessEqual(x + pw, w)
            self.assertLessEqual(y + ph, h)
            for i in range(x, x + pw):
                for j in range(y, y + ph):
                    self.assertNotIn((i, j), cells)
                    cells.add((i, j))

    def test_empty_input_gives_empty_atlas(self):
        self.assertEqual(uvs.layout_uvs([], 'MULTIPLE_32'), (0, 0, []))

    def test_per_face_mode_packs_each_face_separately(self):
        node = self.make_node()
        _, _, paint = uvs.layout_uvs([(node, box_faces(32, 32, 32), (1, 2, 3))],
                                     'MULTIPLE_32', per_face=True)
        self.assertEqual(len(paint), 6)
        self.assertEqual(len(node["shape"]["textureLayout"]), 6)


if __name__ == "__main__":
    unittest.main()
