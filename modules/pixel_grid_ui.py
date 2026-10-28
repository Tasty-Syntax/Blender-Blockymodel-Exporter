"""Pixel Grid Lock panel: format, grid snapping and the Snap Now button."""

from bpy.types import Operator, Panel

from .constants import UNITS_PER_BLOCK
from .snapping import _snap_object


class HYTALE_OT_snap_to_pixel_grid(Operator):
    bl_idname = "hytale.snap_to_pixel_grid"
    bl_label = "Snap Now"
    bl_description = "Round every element of the lock collection (or the selection) to whole pixels"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene
        if context.mode != 'OBJECT':
            self.report({'ERROR'}, "Switch to Object Mode first")
            return {'CANCELLED'}
        lock = scene.hytale_lock_collection
        objs = lock.all_objects if lock else context.selected_objects
        units = UNITS_PER_BLOCK[scene.hytale_format]
        meshes = [o for o in objs if o.type == 'MESH']
        if not meshes:
            self.report({'INFO'}, "No mesh objects to snap")
            return {'FINISHED'}
        changed = sum(1 for o in meshes if _snap_object(o, units))
        if changed:
            self.report({'INFO'}, f"Snapped {changed} of {len(meshes)} object(s) to the {units} px grid")
        else:
            self.report({'INFO'}, f"All {len(meshes)} object(s) already pixel-grid aligned")
        return {'FINISHED'}


class HYTALE_OT_set_grid_snapping(Operator):
    bl_idname = "hytale.set_grid_snapping"
    bl_label = "Set Grid Snapping"
    bl_description = "Turn on increment snapping at one pixel of the Format's density (1/32 m or 1/64 m)"

    def execute(self, context):
        units = UNITS_PER_BLOCK[context.scene.hytale_format]
        ts = context.tool_settings
        ts.use_snap = True
        ts.snap_elements = {'INCREMENT'}
        space = context.space_data
        if space is not None and space.type == 'VIEW_3D':
            space.overlay.grid_scale = 1.0 / units
        return {'FINISHED'}


class HYTALE_PT_pixel_grid(Panel):
    bl_label = "Pixel Grid Lock"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Hytale"

    def draw(self, context):
        scene = context.scene
        layout = self.layout
        layout.prop(scene, "hytale_format")
        layout.operator(HYTALE_OT_set_grid_snapping.bl_idname)
        layout.separator()
        layout.prop(scene, "hytale_lock_collection")
        layout.operator(HYTALE_OT_snap_to_pixel_grid.bl_idname)
