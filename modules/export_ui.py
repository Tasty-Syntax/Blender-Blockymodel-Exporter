"""Export panel in the Hytale sidebar tab: file, overwrite options and the Export button."""

import os

import bpy
from bpy.props import BoolProperty, StringProperty
from bpy.types import Operator, Panel
from bpy_extras.io_utils import ExportHelper

from .exporter import EXPORT_SCENE_OT_blockymodel
from .uv_ui import draw_uv_section


class HYTALE_OT_choose_export_file(Operator, ExportHelper):
    """Pick the export file (folder and name) in a file browser"""
    bl_idname = "hytale.choose_export_file"
    bl_label = "Choose Export File"
    bl_options = {'INTERNAL'}

    filename_ext = ".blockymodel"
    filter_glob: StringProperty(default="*.blockymodel", options={'HIDDEN'})
    # No overwrite prompt here: Export checks the Overwrite Existing checkbox instead.
    check_existing: BoolProperty(default=False, options={'HIDDEN'})

    def invoke(self, context, event):
        name = context.scene.hytale_export_name.strip()
        if name:
            self.filepath = bpy.path.abspath(name)
        return super().invoke(context, event)

    def execute(self, context):
        context.scene.hytale_export_name = self.filepath
        return {'FINISHED'}


_EXPORT_ATTEMPTED = [False]   # True after a click on Export with empty fields; drives the red highlight


class HYTALE_OT_export_model(Operator):
    bl_idname = "hytale.export_model"
    bl_label = "Export"
    bl_description = "Export the chosen collection to the path above"

    def execute(self, context):
        scene = context.scene
        if not scene.hytale_export_name.strip():
            _EXPORT_ATTEMPTED[0] = True
            if context.screen is not None:
                for area in context.screen.areas:
                    area.tag_redraw()
            self.report({'ERROR'}, "Fill in the highlighted fields")
            return {'CANCELLED'}
        _EXPORT_ATTEMPTED[0] = False
        filepath = bpy.path.abspath(scene.hytale_export_name.strip())
        if not filepath.lower().endswith(".blockymodel"):
            filepath += ".blockymodel"
        # The texture is written next to the model with the same base name.
        texture = os.path.splitext(filepath)[0] + ".png"
        targets = (filepath, texture) if scene.hytale_export_texture else (filepath,)
        if not scene.hytale_export_overwrite:
            existing = [os.path.basename(p) for p in targets if os.path.exists(p)]
            if existing:
                self.report({'ERROR'}, f"{', '.join(existing)} already exists. "
                                       "Enable Overwrite Existing to replace it")
                return {'CANCELLED'}
        # An existing texture is kept unless Overwrite Texture is checked.
        keep_texture = os.path.exists(texture) and not scene.hytale_export_overwrite_texture
        collection = scene.hytale_export_collection
        # EXEC_DEFAULT skips the file browser; the exporter then runs with the values given here.
        try:
            result = bpy.ops.export_scene.blockymodel(
                'EXEC_DEFAULT',
                filepath=filepath,
                collection=collection.name if collection else "",
                model_format=scene.hytale_format,
                uv_source=scene.hytale_uv_source,
                export_texture=scene.hytale_export_texture and not keep_texture,
            )
        except RuntimeError as e:
            # Blender raises an ERROR report from a Python call as RuntimeError ("Error: ...").
            self.report({'ERROR'}, str(e).removeprefix("Error: "))
            return {'CANCELLED'}
        if result == {'FINISHED'}:
            self.report({'INFO'}, f"Blockymodel exported to {filepath}")
        return result


class HYTALE_PT_export(Panel):
    bl_label = "Export"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Hytale"

    def draw(self, context):
        scene = context.scene
        layout = self.layout
        attempted = _EXPORT_ATTEMPTED[0]
        layout.prop(scene, "hytale_export_collection")
        layout.separator()
        draw_uv_section(layout, scene)
        layout.separator()
        row = layout.row(align=True)
        row.alert = attempted and not scene.hytale_export_name.strip()
        row.prop(scene, "hytale_export_name")
        row.operator(HYTALE_OT_choose_export_file.bl_idname, text="", icon='FILEBROWSER')
        layout.prop(scene, "hytale_export_texture")
        layout.prop(scene, "hytale_export_overwrite")
        row = layout.row()
        row.enabled = scene.hytale_export_overwrite and scene.hytale_export_texture
        row.prop(scene, "hytale_export_overwrite_texture")
        layout.separator()
        layout.operator(HYTALE_OT_export_model.bl_idname, icon='EXPORT')
