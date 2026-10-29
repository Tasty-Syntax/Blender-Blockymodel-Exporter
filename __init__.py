"""
Hytale Blocky Model Exporter (direct mode) - UV TEST BUILD

Test build: pieces that are boxes in a rotated frame (rotated in Edit Mode)
are exported as rotated boxes/quads instead of their bounding box.
Writes per-face UVs (every cube edge is a seam) and a placeholder texture.

Exports Blender models built from cubes and panes 1:1 to Hytale's
.blockymodel format. Every mesh object, or every separate piece inside a
joined mesh, must be an axis-aligned box (cube/cuboid) or a flat rectangle
(pane) in the object's own local space. It becomes a "box" or "quad" node
with the object's exact position, rotation and size.

Conventions (from the official Hytale Blockbench plugin codec):
  * 1 Blender unit (metre) = 1 block = 32 units (prop) or 64 units (character)
  * 1 unit = 1 texture pixel; texture width/height are multiples of 32
  * Blender (x, y, z) Z-up  ->  Hytale (x, z, -y) Y-up; Blender front (-Y) = Hytale front (+Z)
  * child node position is relative to the parent's pivot plus its shape offset

No third-party dependencies: only Blender's bundled Python is used.
"""

import bpy

from .modules import export_ui, exporter, item_ui, pixel_grid_ui, properties, uv_ui

classes = (
    exporter.EXPORT_SCENE_OT_blockymodel,
    exporter.IO_FH_hytale_blockymodel,
    pixel_grid_ui.HYTALE_OT_snap_to_pixel_grid,
    pixel_grid_ui.HYTALE_OT_set_grid_snapping,
    pixel_grid_ui.HYTALE_PT_pixel_grid,
    uv_ui.HYTALE_OT_generate_uvs,
    uv_ui.HYTALE_OT_fit_texture,
    export_ui.HYTALE_OT_choose_export_file,
    export_ui.HYTALE_OT_export_model,
    export_ui.HYTALE_PT_export,
    item_ui.HYTALE_PT_item,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.TOPBAR_MT_file_export.append(exporter.menu_func_export)
    properties.register_properties()
    item_ui.register_properties()


def unregister():
    item_ui.unregister_properties()
    properties.unregister_properties()
    bpy.types.TOPBAR_MT_file_export.remove(exporter.menu_func_export)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
