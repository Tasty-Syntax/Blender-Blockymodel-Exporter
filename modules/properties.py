"""Scene properties shared by the Pixel Grid Lock and Export panels."""

import bpy
from bpy.props import BoolProperty, EnumProperty, IntProperty, PointerProperty, StringProperty


def _reset_overwrite_texture(self, context):
    # Overwrite Texture only applies while Overwrite Existing is on.
    if not self.hytale_export_overwrite:
        self.hytale_export_overwrite_texture = False


def register_properties():
    bpy.types.Scene.hytale_format = EnumProperty(
        name="Format",
        description="Pixel density for the lock: 32 px/block (prop) or 64 px/block (character)",
        items=[
            ('prop', "Prop (32 px/block)", "1 m = 32 units"),
            ('character', "Character (64 px/block)", "1 m = 64 units"),
        ],
        default='prop',
    )
    bpy.types.Scene.hytale_lock_collection = PointerProperty(
        name="Lock Collection",
        description="Only lock objects in this collection (empty = whole scene)",
        type=bpy.types.Collection,
    )
    bpy.types.Scene.hytale_export_collection = PointerProperty(
        name="Collection",
        description="Collection to export as groups (empty = selected objects)",
        type=bpy.types.Collection,
    )
    bpy.types.Scene.hytale_export_name = StringProperty(
        name="File",
        description="Full path of the .blockymodel file to write",
    )
    bpy.types.Scene.hytale_export_texture = BoolProperty(
        name="Export Texture",
        description="Write a placeholder texture (<file>.png) with every UV island in its own "
                    "pastel color, ready to paint over",
        default=True,
    )
    bpy.types.Scene.hytale_export_overwrite = BoolProperty(
        name="Overwrite Existing",
        description="Replace the model and texture if they already exist",
        default=False,
        update=_reset_overwrite_texture,
    )
    bpy.types.Scene.hytale_export_overwrite_texture = BoolProperty(
        name="Overwrite Texture",
        description="Replace an existing texture (<file>.png) when exporting over an existing model",
        default=False,
    )
    bpy.types.Scene.hytale_uv_source = EnumProperty(
        name="UVs",
        description="Where the exported texture layout comes from",
        items=[
            ('AUTO', "Generate at Export", "Pack every face automatically on each export"),
            ('MESH', "From UV Map", "Use the 'Hytale' UV map, arranged in the UV Editor"),
        ],
        default='AUTO',
    )
    # Size of the texture the 'Hytale' UV maps are laid out on; set by Generate UVs
    bpy.types.Scene.hytale_uv_width = IntProperty(name="Texture Width", default=64, min=1)
    bpy.types.Scene.hytale_uv_height = IntProperty(name="Texture Height", default=64, min=1)
    # Generate UVs options
    bpy.types.Scene.hytale_uv_per_face = BoolProperty(
        name="Per-Face Islands",
        description="Give every cube face its own UV island instead of one box net per cube",
        default=True,
    )
    bpy.types.Scene.hytale_uv_square = BoolProperty(
        name="Square Texture",
        description="Make the texture as tall as it is wide, so faces also look square "
                    "in a UV Editor that shows no image",
        default=True,
    )
    bpy.types.Scene.hytale_uv_padding = IntProperty(
        name="Island Padding",
        description="Empty pixels kept between UV islands",
        default=1,
        min=0,
        soft_max=16,
    )
    bpy.types.Scene.hytale_uv_size_mode = EnumProperty(
        name="Texture Size",
        description="Grid the texture width and height are rounded up to",
        items=[
            ('MULTIPLE_32', "Multiple of 32", "32, 64, 96, 128, 160 ... px"),
            ('POWER_OF_TWO', "Power of Two", "32, 64, 128, 256 ... px"),
        ],
        default='MULTIPLE_32',
    )


def unregister_properties():
    del bpy.types.Scene.hytale_uv_size_mode
    del bpy.types.Scene.hytale_uv_padding
    del bpy.types.Scene.hytale_uv_square
    del bpy.types.Scene.hytale_uv_per_face
    del bpy.types.Scene.hytale_uv_height
    del bpy.types.Scene.hytale_uv_width
    del bpy.types.Scene.hytale_uv_source
    del bpy.types.Scene.hytale_export_overwrite_texture
    del bpy.types.Scene.hytale_export_overwrite
    del bpy.types.Scene.hytale_export_texture
    del bpy.types.Scene.hytale_export_name
    del bpy.types.Scene.hytale_export_collection
    del bpy.types.Scene.hytale_lock_collection
    del bpy.types.Scene.hytale_format
