"""Builds the .blockymodel node tree from the cubes and panes of the scene."""

import bpy
from mathutils import Matrix, Quaternion, Vector

from .geometry import Part, mesh_parts, quat_to_hytale, size_to_hytale, vec_to_hytale


def _num(v, nd=4):
    r = round(float(v), nd)
    if r == int(r):
        return int(r)
    return r


def _vec_json(v):
    return {"x": _num(v[0]), "y": _num(v[1]), "z": _num(v[2])}


# ============================================================================
# Node building
# ============================================================================

HYTALE_FACES = ("front", "back", "left", "right", "top", "bottom")


def _quat_json(q):
    return {"x": _num(q.x, 6), "y": _num(q.y, 6), "z": _num(q.z, 6), "w": _num(q.w, 6)}


def _new_node(node_id, name, position, orientation):
    return {
        "id": str(node_id),
        "name": name.replace(":", "_"),
        "position": _vec_json(position),
        "orientation": {
            "x": _num(orientation.x, 6), "y": _num(orientation.y, 6),
            "z": _num(orientation.z, 6), "w": _num(orientation.w, 6),
        },
        "shape": {
            "type": "none",
            "offset": {"x": 0, "y": 0, "z": 0},
            "stretch": {"x": 1, "y": 1, "z": 1},
            "settings": {"isPiece": False},
            "textureLayout": {},
            "unwrapMode": "custom",
            "visible": True,
            "doubleSided": False,
            "shadingMode": "flat",
        },
    }


def _pane_axes(axis, sign):
    """Blender axes for a quad's local X and Y. Their cross product is the pane's
    normal, so the quad is never mirrored."""
    u_ax, v_ax = (axis + 1) % 3, (axis + 2) % 3
    return (v_ax, u_ax) if sign < 0 else (u_ax, v_ax)


def _child_orientation(part):
    """Hytale orientation of the child node that holds this piece (relative to its parent)."""
    if part.kind == 'PANE':
        # A Blockbench quad is flat in X/Y (Z = 0) with its normal along +Z;
        # this rotation turns that quad into the pane's plane.
        frame = part.rot.to_matrix() if part.rot is not None else Matrix.Identity(3)
        u_ax, v_ax = _pane_axes(part.flat_axis, part.normal_sign)

        def to_hytale(i):
            e = Vector((0.0, 0.0, 0.0))
            e[i] = 1.0
            return vec_to_hytale(frame @ e)

        normal = to_hytale(part.flat_axis) * part.normal_sign
        return Matrix((to_hytale(u_ax), to_hytale(v_ax), normal)).transposed().to_quaternion()
    if part.rot is not None:
        return quat_to_hytale(part.rot)
    return Quaternion((1, 0, 0, 0))


def _shape_from_part(node, part, units, double_sided_panes):
    """Turn node into a box/quad. Returns (offset_h, uv_faces) where uv_faces
    maps Hytale face name -> (width_px, height_px)."""
    offset_h = vec_to_hytale(part.center) * units
    size_h = size_to_hytale(part.size) * units
    shape = node["shape"]
    shape["offset"] = _vec_json(offset_h)

    if part.kind == 'BOX':
        shape["type"] = "box"
        shape["settings"]["size"] = _vec_json(size_h)
        sx, sy, sz = size_h
        uv_faces = {
            "front": (sx, sy), "back": (sx, sy),
            "left": (sz, sy), "right": (sz, sy),
            "top": (sx, sz), "bottom": (sx, sz),
        }
    else:
        # Flat quad in its own X/Y plane (Z is always 0); the node's orientation
        # (see _child_orientation) turns it into the pane's plane
        u_ax, v_ax = _pane_axes(part.flat_axis, part.normal_sign)
        qsize = (part.size[u_ax] * units, part.size[v_ax] * units)
        shape["type"] = "quad"
        # Blockbench quads face +Z by default; the node orientation turns that into the pane's normal
        shape["settings"]["normal"] = "+Z"
        shape["settings"]["size"] = {"x": _num(qsize[0]), "y": _num(qsize[1])}
        shape["doubleSided"] = bool(double_sided_panes)
        uv_faces = {"front": qsize}
    return offset_h, uv_faces


class ExportResult:
    def __init__(self):
        self.nodes = []
        self.node_count = 0
        self.uv_requests = []   # (node, uv_faces, color)
        self.warnings = []
        self.non_integer = 0


def _object_color(obj):
    mat = obj.active_material if hasattr(obj, "active_material") else None
    if mat is not None and hasattr(mat, "diffuse_color"):
        c = mat.diffuse_color
        return tuple(int(max(0.0, min(1.0, c[i])) * 255) for i in range(3))
    return (160, 160, 160)


def _collection_chain(root, obj):
    """Collections from root down to the one that holds obj (root first)."""
    def search(coll, chain):
        chain = chain + [coll]
        if any(o == obj for o in coll.objects):
            return chain
        for child in coll.children:
            found = search(child, chain)
            if found:
                return found
        return None
    return search(root, []) or [root]


def build_model(objects, units, depsgraph, double_sided_panes, root):
    res = ExportResult()
    exported = set(objects)

    def exported_parent(obj):
        p = obj.parent
        while p is not None and p not in exported:
            p = p.parent
        return p

    children = {o: [] for o in objects}
    roots = []
    for o in objects:
        p = exported_parent(o)
        (children[p] if p is not None else roots).append(o)
    sort_key = lambda o: o.name
    roots.sort(key=sort_key)
    for k in children:
        children[k].sort(key=sort_key)

    groups = {}

    def holder_for(obj):
        """Node list a root object goes into: one group node per collection on its path."""
        holder = res.nodes
        for coll in _collection_chain(root, obj):
            if coll == bpy.context.scene.collection:
                continue
            group = groups.get(coll.name)
            if group is None:
                group = _new_node(res.node_count + 1, coll.name, Vector((0, 0, 0)),
                                  Quaternion((1, 0, 0, 0)))
                res.node_count += 1
                groups[coll.name] = group
                holder.append(group)
            holder = group.setdefault("children", [])
        return holder

    def check_size(size_h, part_name):
        for v in size_h:
            if abs(v - round(v)) > 1e-3:
                res.non_integer += 1
                return

    def add_object(obj, parent_obj, parent_offset_h):
        loc, rot, _scale = obj.matrix_world.decompose()
        if parent_obj is not None:
            ploc, prot, _ = parent_obj.matrix_world.decompose()
            inv = prot.inverted()
            rel_pos = inv @ (loc - ploc)
            rel_rot = inv @ rot
        else:
            rel_pos, rel_rot = loc, rot

        pos_h = vec_to_hytale(rel_pos) * units - parent_offset_h
        node = _new_node(res.node_count + 1, obj.name, pos_h, quat_to_hytale(rel_rot))
        res.node_count += 1

        own_offset = Vector((0, 0, 0))
        extra_parts = []
        if obj.type == 'MESH':
            parts = mesh_parts(obj, depsgraph)
            if not parts:
                res.warnings.append(f"{obj.name}: no cube or pane found")
            unclean = [p for p in parts if not p.clean]
            if unclean:
                res.warnings.append(
                    f"{obj.name}: {len(unclean)} piece(s) are not clean boxes "
                    "(exported as their bounding box). Rotate in Object Mode, not Edit Mode")
            if len(parts) == 1 and not children.get(obj):
                # One piece and nothing parented to it: the piece is the node itself,
                # its orientation is the object's rotation plus the piece's
                part = parts[0]
                part_q = _child_orientation(part)
                piece_offset, uv = _shape_from_part(node, part, units, double_sided_panes)
                res.uv_requests.append((node, uv, _object_color(obj)))
                node["orientation"] = _quat_json(quat_to_hytale(rel_rot) @ part_q)
                node["shape"]["offset"] = _vec_json(part_q.inverted() @ piece_offset)
                check_size(size_to_hytale(part.size) * units, obj.name)
            else:
                # Panes and tilted pieces become child nodes carrying their own orientation
                plain = [p for p in parts if p.kind == 'BOX' and p.rot is None]
                if plain:
                    own_offset, uv = _shape_from_part(node, plain[0], units, double_sided_panes)
                    res.uv_requests.append((node, uv, _object_color(obj)))
                    check_size(size_to_hytale(plain[0].size) * units, obj.name)
                extra_parts = [p for p in parts if p not in plain[:1]]

        kids = []
        # Extra pieces of a joined mesh become child nodes (pivot at their center)
        for i, part in enumerate(extra_parts, start=1):
            orient = _child_orientation(part)
            child = _new_node(res.node_count + 1, f"{obj.name}--C{i}",
                              vec_to_hytale(part.center) * units - own_offset, orient)
            res.node_count += 1
            sub_part = Part(Vector((0, 0, 0)), part.size, part.kind,
                            part.normal_sign, part.flat_axis, part.clean)
            _, uv = _shape_from_part(child, sub_part, units, double_sided_panes)
            check_size(size_to_hytale(part.size) * units, obj.name)
            child["shape"]["settings"]["isStaticBox"] = True
            res.uv_requests.append((child, uv, _object_color(obj)))
            kids.append(child)

        for c in children.get(obj, []):
            kids.append(add_object(c, obj, own_offset))

        if kids:
            node["children"] = kids
        elif node["shape"]["type"] != "none":
            # A bare cube/pane with nothing attached
            node["shape"]["settings"]["isStaticBox"] = True
        return node

    for r in roots:
        holder_for(r).append(add_object(r, None, Vector((0, 0, 0))))
    return res
