"""UV section of the Export panel: writes the texture layout into a 'Hytale' UV map to edit in the UV Editor."""

import bpy
from bpy.types import Operator

from .constants import UNITS_PER_BLOCK, UV_MAP
from .model import build_model
from .texture import paint_rows
from .uvs import layout_uvs, read_mesh_uvs, snap_texture_dimension, write_mesh_uvs

IMAGE_NAME = "Hytale UV"   # placeholder image the layout is drawn on, for pixel snapping in the UV Editor


def _update_image(width, height, paint):
    """Create or resize the IMAGE_NAME image and draw the placeholder texture on it."""
    image = bpy.data.images.get(IMAGE_NAME)
    if image is None:
        image = bpy.data.images.new(IMAGE_NAME, width, height, alpha=True)
    elif tuple(image.size) != (width, height):
        image.scale(width, height)
    rows = paint_rows(width, height, paint)
    # Blender stores the bottom row first
    image.pixels.foreach_set([b / 255.0 for row in reversed(rows) for b in row])
    image.update()
    try:
        image.pack()   # keep the drawing when the .blend is saved and reopened
    except RuntimeError:
        pass
    return image


def _show_image(image):
    """Show the image in the UV Editors of every workspace (UV Editing too): without it a
    UV Editor shows UV space as a square, which stretches a texture that is not square."""
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == 'IMAGE_EDITOR':
                space = area.spaces.active
                space.image = image
                # Moved UVs land on whole pixels, as textureLayout offsets must
                space.uv_editor.pixel_round_mode = 'CORNER'
                space.uv_editor.show_pixel_coords = True


def _uv_requests(context):
    """UV requests of the export collection (or the selection), read from the base mesh
    (no modifiers), one object per mesh: linked duplicates share their mesh's UVs.
    Returns (requests, error)."""
    scene = context.scene
    coll = scene.hytale_export_collection
    objs = coll.all_objects if coll else context.selected_objects
    objs = [o for o in objs if o.type in {'MESH', 'EMPTY'}]
    if not any(o.type == 'MESH' for o in objs):
        return None, "No mesh objects to lay out"
    res = build_model(objs, UNITS_PER_BLOCK[scene.hytale_format], None, True,
                      coll or scene.collection)
    first_user = {}
    for _node, _uv, obj, _part in res.uv_requests:
        first_user.setdefault(obj.data, obj)
    return [r for r in res.uv_requests if first_user[r[2].data] == r[2]], None


class HYTALE_OT_generate_uvs(Operator):
    bl_idname = "hytale.generate_uvs"
    bl_label = "Generate UVs"
    bl_description = ("Lay out every face of the export collection (or the selection) in a "
                      f"'{UV_MAP}' UV map, ready to rearrange in the UV Editor")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene
        if context.mode != 'OBJECT':
            self.report({'ERROR'}, "Switch to Object Mode first")
            return {'CANCELLED'}
        requests, err = _uv_requests(context)
        if err:
            self.report({'ERROR'}, err)
            return {'CANCELLED'}
        width, height, paint = layout_uvs(requests, scene.hytale_uv_size_mode,
                                         scene.hytale_uv_per_face, scene.hytale_uv_padding)
        if not paint:
            self.report({'ERROR'}, "No cube or pane faces to lay out")
            return {'CANCELLED'}
        if scene.hytale_uv_square:
            width = height = max(width, height)
        write_mesh_uvs(requests, width, height)
        scene.hytale_uv_width = width
        scene.hytale_uv_height = height
        scene.hytale_uv_source = 'MESH'

        _show_image(_update_image(width, height, paint))
        self.report({'INFO'}, f"Laid out {len(requests)} element(s) on a "
                              f"{width}x{height} texture in the '{UV_MAP}' UV map")
        return {'FINISHED'}


class HYTALE_OT_fit_texture(Operator):
    bl_idname = "hytale.fit_texture"
    bl_label = "Fit Texture"
    bl_description = ("Resize the texture to the UV islands as they are arranged now (islands keep "
                      "their pixels) and repaint each island in its own pastel color")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene
        # UVs edited in Edit Mode only reach the mesh when Edit Mode is left
        edit_mode = context.mode == 'EDIT_MESH'
        if edit_mode:
            bpy.ops.object.mode_set(mode='OBJECT')
        try:
            return self._fit(scene, context)
        finally:
            if edit_mode:
                bpy.ops.object.mode_set(mode='EDIT')

    def _fit(self, scene, context):
        requests, err = _uv_requests(context)
        if err:
            self.report({'ERROR'}, err)
            return {'CANCELLED'}
        meshes = {obj.data for _node, _uv, obj, _part in requests}
        if not any(UV_MAP in m.uv_layers for m in meshes):
            self.report({'ERROR'}, f"No '{UV_MAP}' UV map. Click Generate UVs first")
            return {'CANCELLED'}
        old_w, old_h = scene.hytale_uv_width, scene.hytale_uv_height
        paint, _warnings = read_mesh_uvs(requests, old_w, old_h)
        if not paint:
            self.report({'ERROR'}, "No UV islands to fit")
            return {'CANCELLED'}
        mode = scene.hytale_uv_size_mode
        width = snap_texture_dimension(max(x + w for x, _y, w, _h, _f, _c in paint), mode)
        height = snap_texture_dimension(max(y + h for _x, y, _w, h, _f, _c in paint), mode)
        if scene.hytale_uv_square:
            width = height = max(width, height)

        # Same pixels on the new texture: pixel x = u * width, pixel y = (1 - v) * height
        for mesh in meshes:
            layer = mesh.uv_layers.get(UV_MAP)
            if layer is None:
                continue
            for d in layer.data:
                u, v = d.uv
                d.uv = (u * old_w / width, 1.0 - (1.0 - v) * old_h / height)
        scene.hytale_uv_width = width
        scene.hytale_uv_height = height

        # Read again on the new size, for the colors and for what is still wrong
        requests, _err = _uv_requests(context)
        paint, warnings = read_mesh_uvs(requests, width, height)
        _show_image(_update_image(width, height, paint))
        msg = f"Texture fitted to {width}x{height} (was {old_w}x{old_h})"
        if warnings:
            self.report({'WARNING'}, msg + " | " + "; ".join(warnings))
        else:
            self.report({'INFO'}, msg)
        return {'FINISHED'}


def draw_uv_section(layout, scene):
    """UV source and, for From UV Map, the Generate UVs options, drawn inside the Export panel."""
    layout.row().prop(scene, "hytale_uv_source", expand=True)
    if scene.hytale_uv_source == 'MESH':
        layout.prop(scene, "hytale_uv_per_face")
        layout.prop(scene, "hytale_uv_square")
        layout.prop(scene, "hytale_uv_padding")
        layout.prop(scene, "hytale_uv_size_mode")
        layout.separator(factor=0.5)
        layout.operator(HYTALE_OT_generate_uvs.bl_idname, icon='UV')
        layout.operator(HYTALE_OT_fit_texture.bl_idname, icon='FULLSCREEN_EXIT')
        layout.label(text=f"Texture {scene.hytale_uv_width} x {scene.hytale_uv_height} px")
    else:
        layout.label(text="Faces are packed on each export", icon='INFO')
