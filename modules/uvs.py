"""UV layout: packs every element's faces into one texture atlas."""

import math

import bmesh
import bpy


def snap_texture_dimension(px, mode='MULTIPLE_32', step=32):
    """MULTIPLE_32 -> 32, 64, 96, 128 ... / POWER_OF_TWO -> 32, 64, 128, 256 ..."""
    px = max(int(math.ceil(px)), 1)
    if mode == 'POWER_OF_TWO':
        size = step
        while size < px:
            size *= 2
        return size
    return int(math.ceil(px / step)) * step


def _px(v):
    """Pixel extent of a face side. Fractions are truncated, as Blockbench does
    (6.517 -> 6, 9.4839 -> 9); whole numbers stay exact."""
    r = round(v)
    return int(r) if abs(v - r) <= 1e-3 else int(math.floor(v))


def _net(uv_faces):
    """Lay out one element's faces like Blockbench's box UV net.
    Returns (width, height, {face: (x, y, w, h)})."""
    if set(uv_faces) == {"front"}:
        w, h = (_px(v) for v in uv_faces["front"])
        return w, h, {"front": (0, 0, w, h)}
    x = _px(uv_faces["front"][0])
    y = _px(uv_faces["front"][1])
    z = _px(uv_faces["left"][0])
    rects = {
        "top":    (z, 0, x, z),
        "bottom": (z + x, 0, x, z),
        "right":  (0, z, z, y),
        "front":  (z, z, x, y),
        "left":   (z + x, z, z, y),
        "back":   (2 * z + x, z, x, y),
    }
    return 2 * z + 2 * x, z + y, rects


_CUBE_SEAMS_OK = None


def _cube_seams_ok():
    """Blender check, run once per session: mark every edge of a cube as a seam,
    unwrap, and confirm that no edge is still joined across its two faces, i.e.
    every face is its own UV island. Done on a temporary unit cube, because island
    separation does not depend on size."""
    global _CUBE_SEAMS_OK
    if _CUBE_SEAMS_OK is not None:
        return _CUBE_SEAMS_OK
    mesh = bpy.data.meshes.new("_hytale_uv_probe")
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new("_hytale_uv_probe", mesh)
    bpy.context.collection.objects.link(obj)
    view_layer = bpy.context.view_layer
    prev_active = view_layer.objects.active
    view_layer.objects.active = obj
    obj.select_set(True)
    try:
        with bpy.context.temp_override(active_object=obj, object=obj,
                                       selected_objects=[obj], selected_editable_objects=[obj]):
            bpy.ops.object.mode_set(mode='EDIT')
            bm = bmesh.from_edit_mesh(mesh)
            for edge in bm.edges:
                edge.seam = True
            bmesh.update_edit_mesh(mesh)
            bpy.ops.mesh.select_all(action='SELECT')
            bpy.ops.uv.unwrap(method='ANGLE_BASED', margin=0.001)
            bpy.ops.object.mode_set(mode='OBJECT')

        uv = mesh.uv_layers.active.data
        uv_at = {}     # (face index, vertex index) -> uv
        faces_of = {}  # edge index -> the faces that use it
        for poly in mesh.polygons:
            for li in poly.loop_indices:
                loop = mesh.loops[li]
                uv_at[(poly.index, loop.vertex_index)] = uv[li].uv.copy()
                faces_of.setdefault(loop.edge_index, []).append(poly.index)

        ok = True
        for edge in mesh.edges:
            faces = faces_of.get(edge.index, [])
            if len(faces) != 2:
                ok = False
                break
            a, b = faces
            joined = all((uv_at[(a, v)] - uv_at[(b, v)]).length < 1e-5 for v in edge.vertices)
            if joined:
                ok = False
                break
        _CUBE_SEAMS_OK = ok
    finally:
        view_layer.objects.active = prev_active
        bpy.data.objects.remove(obj)
        bpy.data.meshes.remove(mesh)
    return _CUBE_SEAMS_OK


UV_PADDING = 1   # px of empty texture kept after every island so neighbours never overlap


def layout_uvs(uv_requests, size_mode, per_face=False):
    """Shelf-pack every element's net into one atlas. Writes textureLayout into
    the nodes and returns (width, height, rects_to_paint).
    per_face: each face is packed as its own rectangle (cube edges are seams).
    Every island gets UV_PADDING px of gap to its right and below."""
    nets = []
    for node, uv_faces, color in uv_requests:
        if per_face and len(uv_faces) == 6:
            for face, (fw, fh) in uv_faces.items():
                w, h = _px(fw), _px(fh)
                nets.append((node, w, h, {face: (0, 0, w, h)}, color))
        else:
            w, h, rects = _net(uv_faces)
            nets.append((node, w, h, rects, color))
    if not nets:
        return 0, 0, []

    area = sum((max(w, 1) + UV_PADDING) * (max(h, 1) + UV_PADDING) for _, w, h, _, _ in nets)
    widest = max(w for _, w, _, _, _ in nets) + UV_PADDING
    atlas_w = max(widest, snap_texture_dimension(math.sqrt(area * 1.15)))
    order = sorted(range(len(nets)), key=lambda i: (-nets[i][2], -nets[i][1]))

    x = y = shelf_h = 0
    used_w = 0
    paint = []
    for i in order:
        node, w, h, rects, color = nets[i]
        if x + w + UV_PADDING > atlas_w and x > 0:
            y += shelf_h
            x = shelf_h = 0
        layout = {}
        for face, (fx, fy, fw, fh) in rects.items():
            layout[face] = {
                "offset": {"x": x + fx, "y": y + fy},
                "mirror": {"x": False, "y": False},
                "angle": 0,
            }
            if fw > 0 and fh > 0:
                paint.append((x + fx, y + fy, fw, fh, face, color))
        node["shape"]["textureLayout"].update(layout)
        x += w + UV_PADDING
        used_w = max(used_w, x)
        shelf_h = max(shelf_h, h + UV_PADDING)
    used_h = y + shelf_h
    return (snap_texture_dimension(used_w, size_mode),
            snap_texture_dimension(used_h, size_mode),
            paint)
