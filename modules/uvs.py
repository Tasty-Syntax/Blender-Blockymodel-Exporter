"""UV layout: packs every element's faces into one texture atlas."""

import math

import bmesh
import bpy

from .constants import UV_MAP
from .model import _pane_axes
from .texture import pastel


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


def _face_color(node, face):
    """Placeholder color of one face: a pastel that stays the same between exports."""
    return pastel(f"{node['id']}:{face}")


UV_PADDING = 1   # default px of empty texture kept after every island so neighbours never overlap


def layout_uvs(uv_requests, size_mode, per_face=False, padding=UV_PADDING):
    """Shelf-pack every element's net into one atlas. Writes textureLayout into
    the nodes and returns (width, height, rects_to_paint).
    per_face: each face is packed as its own rectangle (cube edges are seams).
    Every island gets padding px of gap to its right and below."""
    nets = []
    for node, uv_faces, *_source in uv_requests:
        if per_face and len(uv_faces) == 6:
            for face, (fw, fh) in uv_faces.items():
                w, h = _px(fw), _px(fh)
                nets.append((node, w, h, {face: (0, 0, w, h)}))
        else:
            w, h, rects = _net(uv_faces)
            nets.append((node, w, h, rects))
    if not nets:
        return 0, 0, []

    area = sum((max(w, 1) + padding) * (max(h, 1) + padding) for _, w, h, _ in nets)
    widest = max(w for _, w, _, _ in nets) + padding
    atlas_w = max(widest, snap_texture_dimension(math.sqrt(area * 1.15)))
    order = sorted(range(len(nets)), key=lambda i: (-nets[i][2], -nets[i][1]))

    x = y = shelf_h = 0
    used_w = 0
    paint = []
    for i in order:
        node, w, h, rects = nets[i]
        if x + w + padding > atlas_w and x > 0:
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
                paint.append((x + fx, y + fy, fw, fh, face, _face_color(node, face)))
        node["shape"]["textureLayout"].update(layout)
        x += w + padding
        used_w = max(used_w, x)
        shelf_h = max(shelf_h, h + padding)
    used_h = y + shelf_h
    return (snap_texture_dimension(used_w, size_mode),
            snap_texture_dimension(used_h, size_mode),
            paint)


# ============================================================================
# Editable UVs: textureLayout <-> the UV_MAP of the Blender meshes
# ============================================================================

# Each face as a Blockbench cube face, in node-local Hytale axes (the same as
# Blockbench's): (u axis, v axis). Vertex 0 (the first UV corner) sits at -u -v,
# vertex 1 one step along u, vertex 2 one step along v. From three.js BoxGeometry,
# which Blockbench uses for cubes.
FACE_AXES = {
    "front":  ((1, 0, 0), (0, -1, 0)),    # +Z (south)
    "back":   ((-1, 0, 0), (0, -1, 0)),   # -Z (north)
    "right":  ((0, 0, -1), (0, -1, 0)),   # +X (east)
    "left":   ((0, 0, 1), (0, -1, 0)),    # -X (west)
    "top":    ((1, 0, 0), (0, 0, 1)),     # +Y (up)
    "bottom": ((1, 0, 0), (0, 0, -1)),    # -Y (down)
}

UV_TOLERANCE = 0.05   # px a corner may be off before a face no longer counts as a whole rectangle


def _face_of(n):
    """Hytale face whose outward normal is closest to n (node-local Hytale axes)."""
    axis = max(range(3), key=lambda i: abs(n[i]))
    return (("left", "right"), ("bottom", "top"), ("back", "front"))[axis][n[axis] > 0]


def _hytale_local(part, v):
    """A vector in the part's own (Blender) frame, in the node-local Hytale axes
    the box or quad is built in (see model._child_orientation)."""
    if part.kind == 'PANE':
        u_ax, v_ax = _pane_axes(part.flat_axis, part.normal_sign)
        return (v[u_ax], v[v_ax], v[part.flat_axis] * part.normal_sign)
    return (v[0], v[2], -v[1])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def face_loops(part, uv_faces):
    """Group a part's loops by Hytale face. Returns {face: [(loop index, s, t, uv)]}
    where s, t (0..1) is the loop's place on the face: 0, 0 at vertex 0, s along
    the u axis and t along the v axis. Faces not in uv_faces (the back of a pane) are left out."""
    by_face = {}
    for normal, corners in part.loops:
        face = _face_of(_hytale_local(part, normal))
        if face not in uv_faces:
            continue
        u, v = FACE_AXES[face]
        for li, pos, uv in corners:
            p = _hytale_local(part, pos)
            by_face.setdefault(face, []).append((li, _dot(p, u), _dot(p, v), uv))
    result = {}
    for face, items in by_face.items():
        lo_u, hi_u = min(i[1] for i in items), max(i[1] for i in items)
        lo_v, hi_v = min(i[2] for i in items), max(i[2] for i in items)
        su, sv = max(hi_u - lo_u, 1e-9), max(hi_v - lo_v, 1e-9)
        result[face] = [(li, (du - lo_u) / su, (dv - lo_v) / sv, uv) for li, du, dv, uv in items]
    return result


def _face_corners(offset, mirror, angle, w, h):
    """Texture pixel coordinates of a face's vertex 0, 1 and 2 (see FACE_AXES)
    for one textureLayout entry, the way the Hytale Blockbench plugin reads it."""
    ox, oy = offset
    mx = -1 if mirror[0] else 1
    my = -1 if mirror[1] else 1
    if angle == 90:
        rect = (ox, oy + w * mx, ox - h * my, oy)
    elif angle == 270:
        rect = (ox + h * my, oy, ox, oy - w * mx)
    elif angle == 180:
        rect = (ox - w * mx, oy - h * my, ox, oy)
    else:
        rect = (ox, oy, ox + w * mx, oy + h * my)
    u1, v1, u2, v2 = rect
    corners = [(u1, v1), (u2, v1), (u1, v2), (u2, v2)]
    for _ in range(angle // 90 % 4):   # Blockbench's face rotation, 90 degrees per step
        a = corners[0]
        corners[0], corners[2], corners[3], corners[1] = corners[2], corners[3], corners[1], a
    return corners[0], corners[1], corners[2]


def _corner_at(corners, s, t):
    c0, c1, c2 = corners
    return (c0[0] + s * (c1[0] - c0[0]) + t * (c2[0] - c0[0]),
            c0[1] + s * (c1[1] - c0[1]) + t * (c2[1] - c0[1]))


# Mirroring both axes is the same as turning by 180, so it is never needed
_CANDIDATES = [(mirror, angle) for mirror in ((False, False), (True, False), (False, True))
               for angle in (0, 90, 180, 270)]


def decode_face(points, w, h):
    """Find the textureLayout entry that puts a face where its UVs are.
    points: [(s, t, (x, y))] with x, y in texture pixels. Returns (mirror, angle,
    (offset x, offset y)) with an unrounded offset, or None when the UVs are not
    the face's w x h px rectangle (turned in 90 degree steps and/or mirrored)."""
    for mirror, angle in _CANDIDATES:
        corners = _face_corners((0, 0), mirror, angle, w, h)
        deltas = []
        for s, t, (x, y) in points:
            ex, ey = _corner_at(corners, s, t)
            deltas.append((x - ex, y - ey))
        dx, dy = deltas[0]
        if all(abs(a - dx) <= UV_TOLERANCE and abs(b - dy) <= UV_TOLERANCE for a, b in deltas):
            return mirror, angle, (dx, dy)
    return None


def write_mesh_uvs(uv_requests, width, height):
    """Write every face's textureLayout rectangle into its object's UV_MAP, which
    becomes the active UV map. The parts must come from the base mesh (no modifiers)."""
    for node, uv_faces, obj, part in uv_requests:
        mesh = obj.data
        layer = mesh.uv_layers.get(UV_MAP) or mesh.uv_layers.new(name=UV_MAP)
        mesh.uv_layers.active = layer
        layout = node["shape"]["textureLayout"]
        for face, loops in face_loops(part, uv_faces).items():
            entry = layout[face]
            w, h = (_px(v) for v in uv_faces[face])
            corners = _face_corners((entry["offset"]["x"], entry["offset"]["y"]),
                                    (entry["mirror"]["x"], entry["mirror"]["y"]),
                                    entry["angle"], w, h)
            for li, s, t, _uv in loops:
                x, y = _corner_at(corners, s, t)
                layer.data[li].uv = (x / width, 1.0 - y / height)


def read_mesh_uvs(uv_requests, width, height):
    """Build every face's textureLayout from its object's UV_MAP, for a width x height
    texture. Returns (rects_to_paint, warnings). A face whose UVs are not a whole,
    unstretched rectangle is placed at the top-left of its UVs, unturned."""
    paint = []
    missing, stretched, off_grid, outside = {}, {}, {}, {}

    def count(table, obj):
        table[obj.name] = table.get(obj.name, 0) + 1

    for node, uv_faces, obj, part in uv_requests:
        layout = node["shape"]["textureLayout"]
        loops = face_loops(part, uv_faces)
        for face, (fw, fh) in uv_faces.items():
            w, h = _px(fw), _px(fh)
            points = [(s, t, (uv[0] * width, (1.0 - uv[1]) * height))
                      for _li, s, t, uv in loops.get(face, []) if uv is not None]
            mirror, angle, offset = (False, False), 0, (0.0, 0.0)
            if not points:
                count(missing, obj)
            else:
                decoded = decode_face(points, w, h)
                if decoded is None:
                    count(stretched, obj)
                    offset = (min(p[2][0] for p in points), min(p[2][1] for p in points))
                else:
                    mirror, angle, offset = decoded
            ox, oy = round(offset[0]), round(offset[1])
            if abs(offset[0] - ox) > UV_TOLERANCE or abs(offset[1] - oy) > UV_TOLERANCE:
                count(off_grid, obj)
            layout[face] = {
                "offset": {"x": ox, "y": oy},
                "mirror": {"x": mirror[0], "y": mirror[1]},
                "angle": angle,
            }
            c0, c1, c2 = _face_corners((ox, oy), mirror, angle, w, h)
            xs = (c0[0], c1[0], c2[0], c1[0] + c2[0] - c0[0])
            ys = (c0[1], c1[1], c2[1], c1[1] + c2[1] - c0[1])
            x0, y0 = min(xs), min(ys)
            pw, ph = max(xs) - x0, max(ys) - y0
            if x0 < 0 or y0 < 0 or x0 + pw > width or y0 + ph > height:
                count(outside, obj)
            if pw > 0 and ph > 0:
                paint.append((x0, y0, pw, ph, face, _face_color(node, face)))

    warnings = []
    for table, text in (
            (missing, f"face(s) have no '{UV_MAP}' UVs (run Generate UVs)"),
            (stretched, "face(s) are stretched or not rectangular in the UV map "
                        "(move, turn by 90 degrees or mirror islands only)"),
            (off_grid, "face(s) are not on whole texture pixels (rounded)"),
            (outside, "face(s) reach outside the texture")):
        for name, n in table.items():
            warnings.append(f"{name}: {n} {text}")
    return paint, warnings
