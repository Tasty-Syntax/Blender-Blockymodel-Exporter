"""The Hytale Blocky Model exporter operator (File -> Export)."""

import json
import os
import time

import bpy
from bpy.props import BoolProperty, EnumProperty, IntProperty, StringProperty
from bpy.types import FileHandler, Operator
from bpy_extras.io_utils import ExportHelper

from .constants import MAX_NODES, UNITS_PER_BLOCK
from .model import build_model
from .texture import write_png
from .uvs import UV_PADDING, _cube_seams_ok, layout_uvs, read_mesh_uvs


SELECTED_ITEM = "__selected__"
_COLLECTION_ITEMS = []   # keeps the enum strings alive while Blender uses them


def _collection_items(self, context):
    _COLLECTION_ITEMS.clear()
    _COLLECTION_ITEMS.append((SELECTED_ITEM, "Selected / Scene Objects",
                              "Export objects directly, not grouped by collection"))
    for coll in bpy.data.collections:
        _COLLECTION_ITEMS.append((coll.name, coll.name, f"Export collection '{coll.name}' as groups"))
    return list(_COLLECTION_ITEMS)


class EXPORT_SCENE_OT_blockymodel(Operator, ExportHelper):
    """Export cubes and panes to a Hytale Blocky Model"""
    bl_idname = "export_scene.blockymodel"
    bl_label = "Export Blocky Model"
    bl_options = {'PRESET'}

    filename_ext = ".blockymodel"
    filter_glob: StringProperty(default="*.blockymodel", options={'HIDDEN'})

    # Set automatically by Collection Exporters
    collection: StringProperty(
        name="Source Collection",
        description="Export only objects from this collection (and its children)",
        default="",
        options={'SKIP_SAVE'},   # never remember a collection from an earlier export
    )

    export_selected_only: BoolProperty(
        name="Selected Only",
        description="Export only selected objects",
        default=True,
    )

    apply_modifiers: BoolProperty(
        name="Apply Modifiers",
        description="Export the evaluated mesh (modifiers applied)",
        default=True,
    )

    model_format: EnumProperty(
        name="Format",
        description="Hytale model type; sets the size of one Blender unit (1 block)",
        items=[
            ('prop', "Prop (32 px/block)", "Blocks, furniture, world props: 1 m = 32 units"),
            ('character', "Character (64 px/block)",
             "Characters, mobs, weapons, cosmetics: 1 m = 64 units"),
        ],
        default='prop',
    )

    double_sided_panes: BoolProperty(
        name="Double-Sided Panes",
        description="Render panes (quads) from both sides",
        default=True,
    )

    export_texture: BoolProperty(
        name="Export Texture",
        description="Write a placeholder texture (<file>.png) with every UV island in its own pastel color, "
                    "ready to paint over",
        default=True,
    )

    texture_size_mode: EnumProperty(
        name="Texture Size",
        description="Grid the texture width and height are rounded up to",
        items=[
            ('MULTIPLE_32', "Multiple of 32", "32, 64, 96, 128, 160 ... px"),
            ('POWER_OF_TWO', "Power of Two", "32, 64, 128, 256 ... px"),
        ],
        default='MULTIPLE_32',
    )

    uv_source: EnumProperty(
        name="UVs",
        description="Where the texture layout comes from",
        items=[
            ('AUTO', "Generate at Export", "Pack every face automatically on each export"),
            ('MESH', "From UV Map",
             "Use the 'Hytale' UV map made with Generate UVs and arranged in the UV Editor"),
        ],
        default='AUTO',
    )

    per_face_uvs: BoolProperty(
        name="Per-Face UVs",
        description="Mark every cube edge as a seam so each face gets its own UV island",
        default=True,
    )

    padding: IntProperty(
        name="Island Padding",
        description="Empty pixels kept between UV islands",
        default=UV_PADDING,
        min=0,
        soft_max=16,
    )

    source_collection: EnumProperty(
        name="Collection",
        description="Collection to export as groups. Selected / Scene Objects exports objects directly",
        items=_collection_items,
        options={'SKIP_SAVE'},
    )

    def invoke(self, context, event):
        self.model_format = context.scene.hytale_format
        self.uv_source = context.scene.hytale_uv_source
        return super().invoke(context, event)

    def _gather_objects(self, context):
        """Return (objects, root collection, error)."""
        name = self.collection or ("" if self.source_collection == SELECTED_ITEM
                                   else self.source_collection)
        if name:
            coll = bpy.data.collections.get(name)
            if coll is None:
                return None, None, f"Collection '{name}' not found"
            objs = coll.all_objects
            return [o for o in objs if o.type in {'MESH', 'EMPTY'}], coll, None
        objs = context.selected_objects if self.export_selected_only else context.scene.objects
        return ([o for o in objs if o.type in {'MESH', 'EMPTY'}],
                context.scene.collection, None)

    def execute(self, context):
        t0 = time.time()
        objects, root, err = self._gather_objects(context)
        if err:
            self.report({'ERROR'}, err)
            return {'CANCELLED'}
        if not any(o.type == 'MESH' for o in objects):
            self.report({'ERROR'}, "No mesh objects to export")
            return {'CANCELLED'}

        if context.mode != 'OBJECT' and context.active_object is not None:
            try:
                bpy.ops.object.mode_set(mode='OBJECT')
            except RuntimeError:
                pass

        depsgraph = context.evaluated_depsgraph_get() if self.apply_modifiers else None
        units = UNITS_PER_BLOCK[self.model_format]
        res = build_model(objects, units, depsgraph, self.double_sided_panes, root)

        filepath = bpy.path.abspath(self.filepath)
        out_dir = os.path.dirname(filepath)
        if out_dir and not os.path.isdir(out_dir):
            os.makedirs(out_dir, exist_ok=True)

        if self.uv_source == 'MESH':
            tex_w, tex_h = context.scene.hytale_uv_width, context.scene.hytale_uv_height
            paint, uv_warnings = read_mesh_uvs(res.uv_requests, tex_w, tex_h)
            res.warnings.extend(uv_warnings)
        else:
            per_face = False
            if self.per_face_uvs:
                try:
                    per_face = _cube_seams_ok()
                    if not per_face:
                        res.warnings.append("cube seams did not separate faces; box UVs used")
                except Exception as e:
                    res.warnings.append(f"per-face UVs unavailable ({e}); box UVs used")
            tex_w, tex_h, paint = layout_uvs(res.uv_requests, self.texture_size_mode, per_face,
                                             self.padding)
        tex_note = ""
        if self.export_texture and paint:
            png_path = os.path.splitext(filepath)[0] + ".png"
            try:
                write_png(png_path, tex_w, tex_h, paint)
                tex_note = f", texture {tex_w}x{tex_h}"
            except OSError as e:
                res.warnings.append(f"texture not written: {e}")

        model = {"nodes": res.nodes, "format": self.model_format, "lod": "auto"}
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(model, f, indent=2)
        except OSError as e:
            self.report({'ERROR'}, f"Could not write file: {e}")
            return {'CANCELLED'}

        if res.node_count > MAX_NODES:
            res.warnings.append(f"{res.node_count} nodes - Hytale allows at most {MAX_NODES}")
        if res.non_integer:
            res.warnings.append(
                f"{res.non_integer} element(s) have non-whole sizes at {units} px/block "
                "(sizes are not whole pixels)")

        elements = len(res.uv_requests)
        msg = f"Exported {elements} element(s), {res.node_count} node(s){tex_note}"
        print(f"[Hytale export] {msg} in {time.time() - t0:.2f}s -> {filepath}")
        for w in res.warnings:
            print(f"[Hytale export] warning: {w}")
        if res.warnings:
            self.report({'WARNING'}, msg + " | " + "; ".join(res.warnings))
        else:
            self.report({'INFO'}, msg)
        return {'FINISHED'}

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        header, body = layout.panel("HYTALE_export_include", default_closed=False)
        header.label(text="Include")
        if body:
            if not self.collection:
                body.prop(self, "source_collection")
                if self.source_collection == SELECTED_ITEM:
                    body.prop(self, "export_selected_only")
            body.prop(self, "apply_modifiers")

        header, body = layout.panel("HYTALE_export_model", default_closed=False)
        header.label(text="Model", icon='MESH_CUBE')
        if body:
            body.prop(self, "model_format")
            body.prop(self, "double_sided_panes")


        header, body = layout.panel("HYTALE_export_texture", default_closed=False)
        header.use_property_split = False
        header.prop(self, "export_texture", text="")
        header.label(text="Texture", icon='TEXTURE')
        if body:
            body.prop(self, "uv_source")
            if self.uv_source == 'AUTO':
                body.prop(self, "texture_size_mode")
                body.prop(self, "per_face_uvs")
                body.prop(self, "padding")
            else:
                scene = context.scene
                body.label(text=f"Texture {scene.hytale_uv_width} x {scene.hytale_uv_height} px")
            if not self.export_texture:
                body.label(text="UVs are still laid out", icon='INFO')


class IO_FH_hytale_blockymodel(FileHandler):
    bl_idname = "IO_FH_hytale_blockymodel"
    bl_label = "Hytale Blocky Model"
    bl_export_operator = "export_scene.blockymodel"
    bl_file_extensions = ".blockymodel"


def menu_func_export(self, context):
    self.layout.operator(EXPORT_SCENE_OT_blockymodel.bl_idname,
                         text="Hytale Blocky Model (.blockymodel)")
