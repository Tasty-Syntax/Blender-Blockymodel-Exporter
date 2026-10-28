"""Scene properties shared by the Pixel Grid Lock and Export panels."""

import bpy
from bpy.props import BoolProperty, EnumProperty, PointerProperty, StringProperty


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


def unregister_properties():
    del bpy.types.Scene.hytale_export_overwrite_texture
    del bpy.types.Scene.hytale_export_overwrite
    del bpy.types.Scene.hytale_export_name
    del bpy.types.Scene.hytale_export_collection
    del bpy.types.Scene.hytale_lock_collection
    del bpy.types.Scene.hytale_format
