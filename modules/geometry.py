"""Reading Blender meshes: coordinate conversion and cube/pane detection."""

from mathutils import Matrix, Quaternion, Vector

from .constants import UV_MAP


# ============================================================================
# Coordinate conversion  Blender (Z-up) -> Hytale (Y-up), a proper rotation
# ============================================================================

def vec_to_hytale(v):
    return Vector((v.x, v.z, -v.y))


def size_to_hytale(s):
    return Vector((s.x, s.z, s.y))


def quat_to_hytale(q):
    return Quaternion((q.w, q.x, q.z, -q.y))


# ============================================================================
# Geometry: split a mesh into loose parts and identify cubes / panes
# ============================================================================

class Part:
    """One cube or pane, in the object's local space (Blender axes, scaled)."""

    def __init__(self, center, size, kind, normal_sign=1, flat_axis=None, clean=True, rot=None):
        self.center = center          # Vector, Blender local (scale applied)
        self.size = size              # Vector, Blender local (scale applied)
        self.kind = kind              # 'BOX' or 'PANE'
        self.normal_sign = normal_sign
        self.flat_axis = flat_axis    # 0/1/2 for panes (Blender axis)
        self.clean = clean            # False -> vertices weren't exactly on a box
        self.rot = rot                # Matrix, piece tilted inside the mesh (None = axis-aligned)
        # One entry per polygon: (normal, [(loop index, position, uv or None)]), with the
        # normal and positions in the piece's own frame and positions relative to its centre
        self.loops = []


def _loose_parts(mesh):
    """Group vertex indices into connected pieces (union-find over edges)."""
    n = len(mesh.vertices)
    parent = list(range(n))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for e in mesh.edges:
        a, b = find(e.vertices[0]), find(e.vertices[1])
        if a != b:
            parent[a] = b
    for p in mesh.polygons:   # in case edges are missing
        vs = list(p.vertices)
        for v in vs[1:]:
            a, b = find(vs[0]), find(v)
            if a != b:
                parent[a] = b

    groups = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)

    poly_groups = {}
    for p in mesh.polygons:
        poly_groups.setdefault(find(p.vertices[0]), []).append(p)
    return [(verts, poly_groups.get(root, [])) for root, verts in groups.items()]


def _scaled_co(mesh, i, scale):
    co = mesh.vertices[i].co
    return Vector((co[0] * scale[0], co[1] * scale[1], co[2] * scale[2]))


def _fit_box(cos):
    """Bounding box of the points, and whether every point sits on one of its faces."""
    mn = Vector((min(c[0] for c in cos), min(c[1] for c in cos), min(c[2] for c in cos)))
    mx = Vector((max(c[0] for c in cos), max(c[1] for c in cos), max(c[2] for c in cos)))
    eps = max(1e-5, max(mx - mn) * 1e-4)
    clean = all(
        all(abs(c[i] - mn[i]) <= eps or abs(c[i] - mx[i]) <= eps for i in range(3))
        for c in cos
    )
    return mn, mx, eps, clean


def _tilt_frame(mesh, polys, scale):
    """Rotation whose axes follow the largest face of a piece, or None.
    Lets a box that was rotated inside Edit Mode still come out as a box."""
    if not polys:
        return None
    face = max(polys, key=lambda p: p.area)
    fv = [_scaled_co(mesh, i, scale) for i in face.vertices]
    n1 = (fv[1] - fv[0]).cross(fv[2] - fv[0])
    if n1.length <= 1e-9:
        return None
    n1.normalize()
    # Shortest edge: for a triangulated quad it is a leg, never the diagonal
    edges = [fv[(k + 1) % len(fv)] - fv[k] for k in range(len(fv))]
    e = min(edges, key=lambda v: v.length)
    t1 = e - n1 * e.dot(n1)
    if t1.length <= 1e-9:
        return None
    t1.normalize()
    n2 = n1.cross(t1)
    return Matrix((t1, n2, n1)).transposed()


def _scaled_normal(p, scale, frame):
    """Polygon normal in scaled space (normals transform with inverse scale),
    in the piece's own frame when it is tilted."""
    n = p.normal
    sn = Vector([n[i] / (scale[i] if abs(scale[i]) > 1e-9 else 1.0) for i in range(3)])
    if frame is not None:
        sn = frame.transposed() @ sn
    return sn


def _analyse_part(mesh, vert_ids, polys, scale, uv_data=None):
    cos = [_scaled_co(mesh, i, scale) for i in vert_ids]
    mn, mx, eps, clean = _fit_box(cos)
    if max(mx - mn) <= 1e-6:
        return None

    # Test build: a piece that is a box in its own rotated frame is still a box
    frame = None
    if not clean:
        frame = _tilt_frame(mesh, polys, scale)
        if frame is not None:
            fitted = [frame.transposed() @ c for c in cos]
            f_mn, f_mx, f_eps, f_clean = _fit_box(fitted)
            if f_clean and max(f_mx - f_mn) > 1e-6:
                mn, mx, eps, clean = f_mn, f_mx, f_eps, True
                cos = fitted
            else:
                frame = None

    size = mx - mn
    thin = [i for i in range(3) if size[i] <= eps]
    if len(thin) >= 2:
        return None   # a line or point, nothing to export
    center = (mn + mx) * 0.5

    co_of = dict(zip(vert_ids, cos))
    loops = []
    for p in polys:
        corners = []
        for li in p.loop_indices:
            uv = tuple(uv_data[li].uv) if uv_data is not None else None
            corners.append((li, co_of[mesh.loops[li].vertex_index] - center, uv))
        loops.append((_scaled_normal(p, scale, frame), corners))

    if frame is not None:
        center, rot = frame @ center, frame.to_quaternion()
    else:
        rot = None
    if len(thin) == 1:
        axis = thin[0]
        size[axis] = 0.0
        # Which way does the pane face? Average polygon normals (scaled space,
        # in the piece's own frame when it is tilted)
        total = 0.0
        for p, (sn, _corners) in zip(polys, loops):
            total += sn[axis] * p.area if hasattr(p, "area") else sn[axis]
        sign = -1 if total < 0 else 1
        part = Part(center, size, 'PANE', normal_sign=sign, flat_axis=axis, clean=clean, rot=rot)
    else:
        part = Part(center, size, 'BOX', clean=clean, rot=rot)
    part.loops = loops
    return part


def mesh_parts(obj, depsgraph):
    """Return the cubes/panes of a mesh object in local, scaled Blender space.
    Each part also records its polygons' loops and their UV_MAP coordinates."""
    _loc, _rot, scale = obj.matrix_world.decompose()
    if depsgraph is not None:
        obj_eval = obj.evaluated_get(depsgraph)
        mesh = obj_eval.to_mesh()
        cleanup = obj_eval.to_mesh_clear
    else:
        mesh = obj.data
        cleanup = None
    try:
        uv_layer = mesh.uv_layers.get(UV_MAP)
        uv_data = uv_layer.data if uv_layer is not None else None
        parts = []
        for verts, polys in _loose_parts(mesh):
            part = _analyse_part(mesh, verts, polys, scale, uv_data)
            if part is not None:
                parts.append(part)
    finally:
        if cleanup:
            cleanup()
    # Stable order: by position, so re-exports keep the same node order
    parts.sort(key=lambda p: (round(p.center.z, 4), round(p.center.y, 4), round(p.center.x, 4)))
    return parts
