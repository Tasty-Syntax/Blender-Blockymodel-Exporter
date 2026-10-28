import unittest

from tests import _blender_stubs  # noqa: F401
from modules import model


class Numbers(unittest.TestCase):
    def test_whole_floats_become_ints(self):
        self.assertEqual(model._num(2.0), 2)
        self.assertIsInstance(model._num(2.0), int)

    def test_fractions_are_rounded_to_four_places(self):
        self.assertEqual(model._num(1.23456), 1.2346)

    def test_vector_json_has_xyz_keys(self):
        self.assertEqual(model._vec_json((1.0, 2.5, -3.0)), {"x": 1, "y": 2.5, "z": -3})


if __name__ == "__main__":
    unittest.main()
