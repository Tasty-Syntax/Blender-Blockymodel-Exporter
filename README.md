# Hytale Blocky Model Exporter — Blender Extension

Exports models built from **cubes and panes** in Blender 1:1 to Hytale's
`.blockymodel` format. Requires **Blender 5.2 LTS** (tested with 5.2.3). No dependencies:
only what ships with Blender is used.

Based on `export2blockymodel.py` from
https://github.com/MDufJokeAIR/Blender-Hytale-Converter, simplified to a direct
exporter: no mesh cutting or approximation.

## Install

1. Blender: **Edit → Preferences → Get Extensions**
2. Top-right **⌄** menu → **Install from Disk…**
3. Pick `hytale_blockymodel_exporter-1.0.0.zip`

The zip is built by the **Build extension** GitHub workflow and attached to releases.

## Modelling rules

- **1 Blender unit (m) = 1 block.** Prop format = 32 px/block, Character = 64 px/block.
  A 1×1×1 cube becomes a 32×32×32 box (or 64³ as a character).
- **Cube** = any box (cuboid). **Pane** = a flat rectangle (e.g. a Plane). Panes become
  Hytale quads; the face normal decides which way they face.
- Move/rotate/scale in **Object Mode**. Edit-mode rotations make a piece "not a clean box"
  (it is then exported as its bounding box, with a warning).
- One element per object, or join several (Ctrl+J): each separate piece becomes its own element.
- Parenting is kept: parented objects become nested nodes; the object origin is the pivot.
  Empties work as pivots/groups.
- Keep sizes whole numbers of pixels (e.g. multiples of 1/32 m for props) so UVs line up
  with texture pixels. The exporter warns otherwise.
- Hytale allows at most 255 nodes per model.

## Export panel

Open the **Hytale** tab in the 3D viewport sidebar (N panel) and use the **Export** panel:

- **Collection**: the collection to export as groups. Leave it empty to export the selected objects.
- **File**: the full path of the `.blockymodel` file. Type it, or use the browse button
  next to it to pick a folder and name. Clicking an existing file in the picker fills in its name.
  `.blockymodel` is added if you leave it off.
- **Overwrite Existing**: off by default. If the model or its texture already exists and this is
  off, the export stops with an error. Turning it off also turns off Overwrite Texture.
- **Overwrite Texture**: only available with Overwrite Existing. When off, an existing
  `<name>.png` is kept and only the model is replaced.
- **Export**: writes `<name>.blockymodel` and `<name>.png`. A success message shows the full path.

The format (Prop or Character) comes from the **Format** setting in the Pixel Grid Lock panel.

## Pixel grid lock (optional)

Open the **Hytale** tab in the 3D viewport sidebar (N panel) to snap element sizes to
whole pixels:

- **Format**: 32 px/block for prop, 64 for character. Each box/pane side is rounded to
  whole pixels at this density. Panes keep their flat side as is.
- **Set Grid Snapping**: turns on increment snapping at one pixel (1/32 m or 1/64 m).
- **Lock Collection**: only objects in this collection are snapped (empty = whole scene).
  Use it to leave reference geometry alone.
- **Snap Now**: rounds the lock collection (or the selection) once, on demand. It reports how
  many objects changed, or that all of them were already aligned.

Limits: only sizes are snapped, not positions; the base mesh is changed, so modifiers
are not applied first; unclean pieces (not a box or pane) are skipped; the snap scales
each side about the piece's centre. A snap can change a mesh that shares its data with
another object.

## Use (File menu)

**File → Export → Hytale Blocky Model (.blockymodel)**, or add it under
**Collection Properties → Exporters**. This opens the full export options, including the
Collection, Model format, Apply Modifiers and texture size.

Output: `<name>.blockymodel` and `<name>.png`. The texture has every face laid out
(box-UV net per cube) and filled with the object's material viewport color, shaded per
side, ready to paint over. Width and height are always multiples of 32
(or powers of two).

## Axes

Blender (X, Y, Z), Z-up → Hytale (X, Z, −Y), Y-up. Blender's front view (−Y) is the
Hytale front (+Z).

## Development

Source is in `modules/`; `__init__.py` registers it. Tests are in `tests/`.

```
# Pure-Python tests (mesh tests are skipped outside Blender)
python3 -m unittest discover -s tests -t .

# Full suite inside Blender
blender -b --factory-startup --python-exit-code 1 --python tests/run_in_blender.py

# Statement coverage of modules/
blender -b --factory-startup --python tests/measure_coverage.py
```

Replace `blender` with the path to your Blender binary.
