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
        return {"id": "1", "shape": {"textureLayout": {}}}

    def test_writes_a_layout_entry_for_every_face(self):
        node = self.make_node()
        uvs.layout_uvs([(node, box_faces(32, 32, 32))], 'MULTIPLE_32')
        self.assertEqual(set(node["shape"]["textureLayout"]), set(box_faces(1, 1, 1)))
        for entry in node["shape"]["textureLayout"].values():
            self.assertEqual(entry["angle"], 0)
            self.assertFalse(entry["mirror"]["x"] or entry["mirror"]["y"])

    def test_atlas_size_is_a_multiple_of_32(self):
        node = self.make_node()
        w, h, _ = uvs.layout_uvs([(node, box_faces(32, 32, 32))], 'MULTIPLE_32')
        self.assertEqual(w % 32, 0)
        self.assertEqual(h % 32, 0)

    def test_islands_stay_inside_the_atlas_and_do_not_overlap(self):
        requests = []
        for size in (16, 32, 48, 8):
            requests.append((self.make_node(), box_faces(size, size, size)))
        w, h, paint = uvs.layout_uvs(requests, 'MULTIPLE_32')
        cells = set()
        for x, y, pw, ph, _face, _color in paint:
            self.assertLessEqual(x + pw, w)
            self.assertLessEqual(y + ph, h)
            for i in range(x, x + pw):
                for j in range(y, y + ph):
                    self.assertNotIn((i, j), cells)
                    cells.add((i, j))

    def test_padding_sets_the_gap_between_islands(self):
        for padding in (0, 1, 4):
            nodes = [self.make_node(), self.make_node()]
            requests = [(n, {"front": (8, 8)}) for n in nodes]
            uvs.layout_uvs(requests, 'MULTIPLE_32', padding=padding)
            xs = sorted(n["shape"]["textureLayout"]["front"]["offset"]["x"] for n in nodes)
            self.assertEqual(xs, [0, 8 + padding])

    def test_faces_get_pastel_colors_that_differ(self):
        node = self.make_node()
        node["id"] = "1"
        _, _, paint = uvs.layout_uvs([(node, box_faces(32, 32, 32))], 'MULTIPLE_32', per_face=True)
        colors = [p[5] for p in paint]
        self.assertEqual(len(set(colors)), 6)
        self.assertTrue(all(min(c) >= 150 for c in colors))

    def test_empty_input_gives_empty_atlas(self):
        self.assertEqual(uvs.layout_uvs([], 'MULTIPLE_32'), (0, 0, []))

    def test_per_face_mode_packs_each_face_separately(self):
        node = self.make_node()
        _, _, paint = uvs.layout_uvs([(node, box_faces(32, 32, 32))],
                                     'MULTIPLE_32', per_face=True)
        self.assertEqual(len(paint), 6)
        self.assertEqual(len(node["shape"]["textureLayout"]), 6)



def corners_of(mirror, angle, w=4, h=2, offset=(10, 20)):
    return uvs._face_corners(offset, mirror, angle, w, h)


class FaceCorners(unittest.TestCase):
    def test_unturned_face_starts_at_the_offset(self):
        self.assertEqual(corners_of((False, False), 0), ((10, 20), (14, 20), (10, 22)))

    def test_turned_faces_keep_their_pixel_rectangle(self):
        for mirror, angle in uvs._CANDIDATES:
            c0, c1, c2 = corners_of(mirror, angle)
            c3 = (c1[0] + c2[0] - c0[0], c1[1] + c2[1] - c0[1])
            xs = sorted({c[0] for c in (c0, c1, c2, c3)})
            ys = sorted({c[1] for c in (c0, c1, c2, c3)})
            size = (xs[-1] - xs[0], ys[-1] - ys[0])
            self.assertEqual(size, (2, 4) if angle in (90, 270) else (4, 2), (mirror, angle))

    def test_every_candidate_places_the_face_differently(self):
        placements = {tuple(c for c in corners_of(m, a, offset=(0, 0))) for m, a in uvs._CANDIDATES}
        self.assertEqual(len(placements), 8)   # 4 turns x mirrored or not


class DecodeFace(unittest.TestCase):
    def points(self, corners, grid=(0, 0.5, 1)):
        return [(s, t, uvs._corner_at(corners, s, t)) for s in grid for t in grid]

    def test_every_layout_is_found_again(self):
        for mirror, angle in uvs._CANDIDATES:
            corners = corners_of(mirror, angle)
            found = uvs.decode_face(self.points(corners), 4, 2)
            self.assertIsNotNone(found, (mirror, angle))
            m, a, offset = found
            self.assertEqual(uvs._face_corners(offset, m, a, 4, 2), corners, (mirror, angle))

    def test_stretched_face_is_not_decoded(self):
        corners = ((0, 0), (8, 0), (0, 2))   # twice as wide as the face
        self.assertIsNone(uvs.decode_face(self.points(corners), 4, 2))

    def test_offset_is_not_rounded(self):
        corners = corners_of((False, False), 0, offset=(1.5, 2))
        self.assertEqual(uvs.decode_face(self.points(corners), 4, 2)[2], (1.5, 2))


class FaceOf(unittest.TestCase):
    def test_dominant_axis_picks_the_face(self):
        self.assertEqual(uvs._face_of((0, 0, 1)), "front")
        self.assertEqual(uvs._face_of((0, 0, -1)), "back")
        self.assertEqual(uvs._face_of((1, 0.2, 0)), "right")
        self.assertEqual(uvs._face_of((-1, 0, 0)), "left")
        self.assertEqual(uvs._face_of((0, 1, 0)), "top")
        self.assertEqual(uvs._face_of((0, -1, 0)), "bottom")

    def test_axes_point_away_from_the_normal(self):
        normals = {"front": (0, 0, 1), "back": (0, 0, -1), "right": (1, 0, 0),
                   "left": (-1, 0, 0), "top": (0, 1, 0), "bottom": (0, -1, 0)}
        for face, (u, v) in uvs.FACE_AXES.items():
            n = normals[face]
            # u x v points into the face, so the texture is not mirrored seen from outside
            cross = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
            self.assertEqual(cross, tuple(-c for c in n), face)


if __name__ == "__main__":
    unittest.main()
