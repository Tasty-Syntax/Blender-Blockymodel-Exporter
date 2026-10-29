"""Item panel: Blender's Item > Transform panel, with lengths in Hytale pixels of the Format."""

import bmesh
import bpy
from bpy.props import EnumProperty, FloatVectorProperty
from bpy.types import Panel
from mathutils import Vector

from .constants import UNITS_PER_BLOCK

AXES = "XYZ"
# Object types without a bounding box, for which Blender shows no Dimensions
_NO_DIMENSIONS = {'EMPTY', 'LIGHT', 'LIGHT_PROBE', 'CAMERA', 'SPEAKER'}


def _units():
    """Pixels per Blender unit (metre) of the Format: 32 for props, 64 for characters."""
    scene = bpy.context.scene
    return UNITS_PER_BLOCK[scene.hytale_format] if scene is not None else UNITS_PER_BLOCK['prop']


def _get_location(self):
    units = _units()
    return [c * units for c in self.location]


def _set_location(self, value):
    units = _units()
    self.location = [c / units for c in value]


def _get_dimensions(self):
    units = _units()
    return [c * units for c in self.dimensions]


def _set_dimensions(self, value):
    units = _units()
    self.dimensions = [c / units for c in value]


def _selected_verts(obj):
    """Selected vertices of a mesh in Edit Mode, or [] otherwise."""
    if obj.type != 'MESH' or obj.mode != 'EDIT':
        return []
    return [v for v in bmesh.from_edit_mesh(obj.data).verts if v.select]


def _median(obj, verts):
    """Median of the vertices, in local or global space as set by Item Space."""
    median = sum((v.co for v in verts), Vector()) / len(verts)
    if bpy.context.scene.hytale_item_space == 'GLOBAL':
        median = obj.matrix_world @ median
    return median


def _get_median(self):
    verts = _selected_verts(self)
    if not verts:
        return [0.0, 0.0, 0.0]
    units = _units()
    return [c * units for c in _median(self, verts)]


def _set_median(self, value):
    verts = _selected_verts(self)
    if not verts:
        return
    delta = Vector(value) / _units() - _median(self, verts)
    if bpy.context.scene.hytale_item_space == 'GLOBAL':
        mw = self.matrix_world
        inv = mw.inverted_safe()
        for v in verts:
            v.co = inv @ (mw @ v.co + delta)
    else:
        for v in verts:
            v.co += delta
    bmesh.update_edit_mesh(self.data)


def register_properties():
    # Pixel views of the real transform: editing them changes location/dimensions/vertices
    bpy.types.Object.hytale_location_px = FloatVectorProperty(
        name="Location",
        description="Location of the object, in pixels of the Format",
        size=3, subtype='XYZ', precision=2, step=100,
        get=_get_location, set=_set_location,
    )
    bpy.types.Object.hytale_dimensions_px = FloatVectorProperty(
        name="Dimensions",
        description="Size of the object's bounding box, in pixels of the Format",
        size=3, subtype='XYZ', precision=2, step=100,
        get=_get_dimensions, set=_set_dimensions,
    )
    bpy.types.Object.hytale_median_px = FloatVectorProperty(
        name="Median",
        description="Median of the selected vertices, in pixels of the Format",
        size=3, subtype='XYZ', precision=2, step=100,
        get=_get_median, set=_set_median,
    )
    bpy.types.Scene.hytale_item_space = EnumProperty(
        name="Space",
        description="Space the Edit Mode median is shown and edited in",
        items=[
            ('GLOBAL', "Global", "Median in world space"),
            ('LOCAL', "Local", "Median in the object's own space"),
        ],
        default='GLOBAL',
    )


def unregister_properties():
    del bpy.types.Scene.hytale_item_space
    del bpy.types.Object.hytale_median_px
    del bpy.types.Object.hytale_dimensions_px
    del bpy.types.Object.hytale_location_px


def _draw_vector(layout, obj, prop, label, lock=None, labels=AXES):
    """A label above one row per axis, with the axis lock in front, like Blender's Item panel."""
    col = layout.column(align=True)
    col.label(text=label)
    for i, axis in enumerate(labels):
        row = col.row(align=True)
        if lock is None:
            row.label(text="", icon='BLANK1')
        else:
            lock_prop, lock_index = lock(i)
            row.prop(obj, lock_prop, index=lock_index, text="", emboss=False,
                     icon='DECORATE_UNLOCKED')
        row.prop(obj, prop, index=i, text=axis)


def _draw_object(layout, obj):
    _draw_vector(layout, obj, "hytale_location_px", "Location (px):",
                 lambda i: ("lock_location", i))
    layout.separator(factor=0.5)
    mode = obj.rotation_mode
    if mode in {'QUATERNION', 'AXIS_ANGLE'}:
        prop = "rotation_quaternion" if mode == 'QUATERNION' else "rotation_axis_angle"
        # W first, then X, Y, Z
        _draw_vector(layout, obj, prop, "Rotation:",
                     lambda i: ("lock_rotation_w", -1) if i == 0 else ("lock_rotation", i - 1),
                     labels="WXYZ")
    else:
        _draw_vector(layout, obj, "rotation_euler", "Rotation:", lambda i: ("lock_rotation", i))
    row = layout.row(align=True)
    row.label(text="", icon='BLANK1')
    row.prop(obj, "rotation_mode", text="")
    layout.separator(factor=0.5)
    _draw_vector(layout, obj, "scale", "Scale:", lambda i: ("lock_scale", i))
    if obj.type not in _NO_DIMENSIONS:
        layout.separator(factor=0.5)
        _draw_vector(layout, obj, "hytale_dimensions_px", "Dimensions (px):")


def _draw_edit_mesh(layout, obj, scene):
    verts = _selected_verts(obj)
    if not verts:
        layout.label(text="Nothing selected")
        return
    label = "Vertex (px):" if len(verts) == 1 else "Median (px):"
    _draw_vector(layout, obj, "hytale_median_px", label)
    layout.row().prop(scene, "hytale_item_space", expand=True)


class HYTALE_PT_item(Panel):
    bl_label = "Item"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Hytale"

    @classmethod
    def poll(cls, context):
        return context.object is not None

    def draw(self, context):
        layout = self.layout
        obj = context.object
        if obj.mode == 'EDIT':
            if obj.type == 'MESH':
                _draw_edit_mesh(layout, obj, context.scene)
            else:
                layout.label(text="Only meshes are supported in Edit Mode", icon='INFO')
            return
        _draw_object(layout, obj)
        units = UNITS_PER_BLOCK[context.scene.hytale_format]
        layout.label(text=f"1 block = {units} px (Format)", icon='INFO')
