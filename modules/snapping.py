"""Pixel grid snapping: rounds box and pane sizes to whole pixels."""

from mathutils import Matrix, Vector

from .geometry import _fit_box, _loose_parts, _scaled_co, _tilt_frame


def _snap_piece(mesh, verts, polys, scale, units):
    """Scale one clean box/pane piece so its non-flat sides are whole pixels.
    Returns {vertex index: new local co}, or {} when nothing has to move."""
    frame = Matrix.Identity(3)
    cos = [_scaled_co(mesh, i, scale) for i in verts]
    mn, mx, eps, clean = _fit_box(cos)
    if not clean:
        tilt = _tilt_frame(mesh, polys, scale)
        if tilt is None:
            return {}
        local = [tilt.transposed() @ c for c in cos]
        mn, mx, eps, clean = _fit_box(local)
        if not clean:
            return {}
        frame, cos = tilt, local
    if max(mx - mn) <= 1e-6:
        return {}

    center = (mn + mx) * 0.5
    size = mx - mn
    factor = [1.0, 1.0, 1.0]
    for i in range(3):
        if size[i] <= eps:   # flat side of a pane: nothing to round
            continue
        factor[i] = max(1, round(size[i] * units)) / units / size[i]
    if all(abs(f - 1.0) < 1e-6 for f in factor):
        return {}

    moves = {}
    for idx, c in zip(verts, cos):
        p = Vector([center[i] + (c[i] - center[i]) * factor[i] for i in range(3)])
        world = frame @ p
        moves[idx] = Vector([world[i] / scale[i] for i in range(3)])
    return moves


def _snap_object(obj, units):
    """Round every clean box/pane of a mesh to whole pixels. Object Mode only;
    changes the base mesh (modifiers are not applied). Returns True if anything moved."""
    if obj.type != 'MESH' or obj.mode != 'OBJECT':
        return False
    _loc, _rot, scale = obj.matrix_world.decompose()
    if any(abs(s) < 1e-9 for s in scale):
        return False
    mesh = obj.data
    moves = {}
    for verts, polys in _loose_parts(mesh):
        moves.update(_snap_piece(mesh, verts, polys, scale, units))
    if not moves:
        return False
    for idx, co in moves.items():
        mesh.vertices[idx].co = co
    mesh.update()
    return True
