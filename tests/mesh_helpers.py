"""Builds meshes and objects inside Blender for the tests that need real mesh data.
Only import this from tests that are skipped outside Blender."""
import bmesh
import bpy
from mathutils import Vector


def add_box(bm, lo, hi):
    """Add an axis-aligned box spanning lo..hi (Blender local units)."""
    res = bmesh.ops.create_cube(bm, size=1.0)
    cx, cy, cz = ((lo[i] + hi[i]) / 2 for i in range(3))
    sx, sy, sz = (hi[i] - lo[i] for i in range(3))
    for v in res["verts"]:
        v.co = Vector((v.co.x * sx + cx, v.co.y * sy + cy, v.co.z * sz + cz))


def add_quad(bm, corners):
    """Add one flat face through the given corners, in order."""
    bm.faces.new([bm.verts.new(c) for c in corners])


def make_object(name, build):
    """Create a mesh object in the scene. build(bm) fills the bmesh."""
    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()
    build(bm)
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def reset_scene():
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj)
    for coll in list(bpy.data.collections):
        bpy.data.collections.remove(coll)
