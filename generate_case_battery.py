import math
import os

import bmesh
import bpy

WORKSPACE = "C:/Users/dsuth/Documents/Code Projects/ESP32 project"
EXPORT_DIR = f"{WORKSPACE}/docs/dimensions/case_stl_battery"
BLEND_PATH = f"{WORKSPACE}/docs/dimensions/ES3C28P_battery_enclosure.blend"
RENDER_PATH = f"{WORKSPACE}/docs/dimensions/battery_enclosure_hero.png"
EXPLODED_PATH = f"{WORKSPACE}/docs/dimensions/battery_enclosure_exploded.png"

PCB_W, PCB_L, PCB_H = 50.0, 86.0, 1.6
SCREEN_W, SCREEN_L, SCREEN_H = 50.0, 69.2, 4.3
SCREEN_Y = 0.18
ACTIVE_W, ACTIVE_L = 43.2, 57.6
ACTIVE_Y, ACTIVE_Z = 3.08, 5.91
HOLES = [(-21.0, 39.0), (21.0, 39.0), (-21.0, -39.0), (21.0, -39.0)]
USB_Y, SD_Y = -43.0, 7.97
RESET_X, BOOT_X, BTN_Y = -11.56, 11.57, -39.74

WALL = 2.0
XY_CLEAR = 0.4
CORNER_R = 6.0
COMPONENT_GAP = 5.0

BAT_T, BAT_W, BAT_L = 6.0, 30.0, 49.0
BAT_POCKET_T = 8.0
BAT_POCKET_W = 32.0
BAT_POCKET_L = 53.0
BAT_CENTER_Y = -7.0

SPK_W, SPK_L, SPK_T = 40.0, 30.0, 10.0
SPK_POCKET_W = 41.6
SPK_POCKET_L = 31.5
SPK_POCKET_T = 11.2
SPK_Y_MIN = 45.4
SPK_CENTER_Y = SPK_Y_MIN + SPK_POCKET_L / 2.0
SPK_FLOOR_Z = -9.8

MAIN_INNER_W = PCB_W + 2.0 * XY_CLEAR
MAIN_INNER_L = PCB_L + 2.0 * XY_CLEAR
MAIN_OUTER_W = MAIN_INNER_W + 2.0 * WALL
MAIN_OUTER_L = MAIN_INNER_L + 2.0 * WALL
PORCH_OUTER_L = 34.0
OUTER_W = MAIN_OUTER_W
OUTER_L = MAIN_OUTER_L + PORCH_OUTER_L
BODY_CENTER_Y = PORCH_OUTER_L / 2.0

INNER_FLOOR_Z = -(COMPONENT_GAP + BAT_POCKET_T)
FLOOR_Z = INNER_FLOOR_Z - WALL
PCB_TOP_Z = PCB_H
BOTTOM_H = PCB_TOP_Z - FLOOR_Z
TOP_H = 5.0
BOSS_H = -INNER_FLOOR_Z
BOSS_R = 5.0
THROUGH_R = 1.7
NUT_BORE_R = 3.4
NUT_BORE_H = 2.2


def _principled(mat):
    return next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")


def get_or_create_collection(name):
    coll = bpy.data.collections.get(name)
    if coll:
        return coll
    coll = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(coll)
    return coll


def link_to_collection(obj, target_coll):
    for coll in list(obj.users_collection):
        coll.objects.unlink(obj)
    target_coll.objects.link(obj)


def get_or_create_mat(name, color, roughness=0.4, metallic=0.0, emission=None, alpha=1.0):
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name=name)
        mat.use_nodes = True
    bsdf = _principled(mat)
    bsdf.inputs["Base Color"].default_value = color
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Alpha"].default_value = alpha
    if emission:
        bsdf.inputs["Emission Color"].default_value = emission
        bsdf.inputs["Emission Strength"].default_value = 2.0
    mat.diffuse_color = color
    if alpha < 1.0:
        mat.blend_method = "BLEND"
    return mat


def create_rounded_box(name, width, length, height, radius, collection, material, location=(0, 0, 0)):
    bm = bmesh.new()
    half_w, half_l = width / 2.0, length / 2.0
    radius = min(radius, half_w, half_l)
    segments = 8
    verts_2d = []
    corners = [
        (half_w - radius, half_l - radius, 0.0, math.pi / 2.0),
        (-half_w + radius, half_l - radius, math.pi / 2.0, math.pi),
        (-half_w + radius, -half_l + radius, math.pi, 3.0 * math.pi / 2.0),
        (half_w - radius, -half_l + radius, 3.0 * math.pi / 2.0, 2.0 * math.pi),
    ]
    for cx, cy, start_ang, end_ang in corners:
        for i in range(segments):
            ang = start_ang + (end_ang - start_ang) * (i / segments)
            verts_2d.append((cx + radius * math.cos(ang), cy + radius * math.sin(ang)))
    bottom = [bm.verts.new((x, y, 0.0)) for x, y in verts_2d]
    face = bm.faces.new(bottom)
    geom = bmesh.ops.extrude_face_region(bm, geom=[face])
    extruded = [v for v in geom["geom"] if isinstance(v, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, vec=(0.0, 0.0, height), verts=extruded)
    bm.normal_update()
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    obj.location = location
    collection.objects.link(obj)
    if material:
        obj.data.materials.append(material)
    return obj


def add_cube(name, location, scale, collection, material=None):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=location, scale=scale)
    obj = bpy.context.active_object
    obj.name = name
    link_to_collection(obj, collection)
    if material:
        obj.data.materials.clear()
        obj.data.materials.append(material)
    return obj


def add_cylinder(name, location, radius, depth, collection, material=None, vertices=24):
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=vertices, radius=radius, depth=depth, location=location
    )
    obj = bpy.context.active_object
    obj.name = name
    link_to_collection(obj, collection)
    if material:
        obj.data.materials.clear()
        obj.data.materials.append(material)
    return obj


def join_objects(objects, name):
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.object.join()
    objects[0].name = name
    return objects[0]


def apply_boolean(target, cutter, operation, solver="FLOAT"):
    bpy.ops.object.select_all(action="DESELECT")
    cutter.select_set(True)
    bpy.context.view_layer.objects.active = cutter
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    mod = target.modifiers.new(name="Bool", type="BOOLEAN")
    mod.operation = operation
    mod.solver = solver
    if solver == "EXACT":
        mod.use_hole_tolerant = True
    mod.object = cutter
    bpy.context.view_layer.objects.active = target
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(cutter, do_unlink=True)


def cut_box(target, x, y, z, sx, sy, sz):
    cutter = add_cube("Cutter", (x, y, z), (sx, sy, sz), target.users_collection[0])
    apply_boolean(target, cutter, "DIFFERENCE")


def cut_cyl(target, x, y, z, radius, depth):
    cutter = add_cylinder("Cutter", (x, y, z), radius, depth, target.users_collection[0])
    apply_boolean(target, cutter, "DIFFERENCE")


def union_obj(target, donor):
    apply_boolean(target, donor, "UNION", solver="EXACT")


def clear_named_collections(names):
    for name in names:
        coll = bpy.data.collections.get(name)
        if not coll:
            continue
        for obj in list(coll.objects):
            bpy.data.objects.remove(obj, do_unlink=True)


def setup_scene():
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.length_unit = "MILLIMETERS"
    scene.unit_settings.scale_length = 0.001
    names = ["V2_Reference", "V2_Case_Bottom", "V2_Case_Top", "V2_Studio"]
    clear_named_collections(names)
    return {name: get_or_create_collection(name) for name in names}


def make_materials():
    return {
        "pcb": get_or_create_mat("V2_PCB", (0.02, 0.12, 0.04, 1.0), roughness=0.4),
        "metal": get_or_create_mat("V2_Metal", (0.85, 0.85, 0.88, 1.0), roughness=0.2, metallic=0.9),
        "glass": get_or_create_mat("V2_Glass", (0.1, 0.1, 0.12, 0.82), roughness=0.05, metallic=0.1, alpha=0.82),
        "ui": get_or_create_mat("V2_UI", (0.05, 0.35, 0.8, 1.0), roughness=0.2, emission=(0.1, 0.5, 1.0, 1.0)),
        "button": get_or_create_mat("V2_Button", (0.9, 0.2, 0.2, 1.0), roughness=0.3, metallic=0.2),
        "bottom": get_or_create_mat("V2_Bottom", (0.12, 0.12, 0.13, 1.0), roughness=0.45, metallic=0.05),
        "top": get_or_create_mat("V2_Top", (0.18, 0.19, 0.21, 1.0), roughness=0.4, metallic=0.05),
        "battery": get_or_create_mat("V2_Battery", (0.05, 0.22, 0.28, 1.0), roughness=0.55),
        "pcm": get_or_create_mat("V2_PCM", (0.02, 0.08, 0.02, 1.0), roughness=0.35),
        "speaker": get_or_create_mat("V2_SpeakerBody", (0.22, 0.2, 0.18, 1.0), roughness=0.5),
        "cone": get_or_create_mat("V2_SpeakerCone", (0.04, 0.04, 0.045, 1.0), roughness=0.7),
    }


def build_reference_board(coll, mats):
    pcb = create_rounded_box("PCB_Board", PCB_W, PCB_L, PCB_H, 3.5, coll, mats["pcb"])
    for hx, hy in HOLES:
        cut_cyl(pcb, hx, hy, PCB_H / 2.0, 1.6, 4.0)
    create_rounded_box("Screen_Glass", SCREEN_W, SCREEN_L, SCREEN_H, 0.5, coll, mats["glass"], (0.0, SCREEN_Y, PCB_H))
    bpy.ops.mesh.primitive_plane_add(size=1.0, location=(0.0, ACTIVE_Y, ACTIVE_Z))
    display = bpy.context.active_object
    display.name = "Screen_Display"
    display.scale = (ACTIVE_W, ACTIVE_L, 1.0)
    link_to_collection(display, coll)
    display.data.materials.append(mats["ui"])
    add_cube("USBC_Receptacle", (0.0, USB_Y, -1.6), (9.0, 7.5, 3.2), coll, mats["metal"])
    add_cube("MicroSD_Socket", (23.5, SD_Y, -0.9), (15.0, 14.5, 1.8), coll, mats["metal"])
    add_cylinder("Button_Reset", (RESET_X, BTN_Y, -1.0), 1.2, 2.0, coll, mats["button"])
    add_cylinder("Button_Boot", (BOOT_X, BTN_Y, -1.0), 1.2, 2.0, coll, mats["button"])
    add_cube("Speaker_JST", (-18.0, 8.0, -1.2), (6.0, 4.0, 2.4), coll, mats["metal"])
    add_cube("Battery_JST", (16.0, -22.0, -1.2), (6.0, 4.0, 2.4), coll, mats["metal"])
    return pcb, display


def build_battery_and_speaker(coll, mats):
    battery = add_cube(
        "Battery_603048",
        (0.0, BAT_CENTER_Y + 1.5, INNER_FLOOR_Z + BAT_T / 2.0),
        (BAT_W, BAT_L, BAT_T),
        coll,
        mats["battery"],
    )
    pcm = add_cube(
        "Battery_PCM",
        (8.0, BAT_CENTER_Y - BAT_L / 2.0 + 1.5 - 2.0, INNER_FLOOR_Z + 2.0),
        (12.0, 4.0, 4.0),
        coll,
        mats["pcm"],
    )
    speaker = add_cube(
        "Speaker_Module",
        (0.0, SPK_CENTER_Y, SPK_FLOOR_Z + 0.6 + SPK_T / 2.0),
        (SPK_W, SPK_L, SPK_T),
        coll,
        mats["speaker"],
    )
    cone = add_cylinder(
        "Speaker_Cone",
        (0.0, SPK_CENTER_Y, SPK_FLOOR_Z + 0.6 + SPK_T + 0.15),
        12.0,
        0.4,
        coll,
        mats["cone"],
        vertices=32,
    )
    return battery, pcm, speaker, cone


def add_standoffs(case, coll):
    overlap = 1.5
    height = BOSS_H + overlap
    z_center = INNER_FLOOR_Z - overlap + height / 2.0
    bosses = []
    for i, (hx, hy) in enumerate(HOLES):
        bosses.append(add_cylinder(f"Boss_{i}", (hx, hy, z_center), BOSS_R, height, coll))
    union_obj(case, join_objects(bosses, "Bosses"))


def add_through_bolts(case, coll):
    hole_z0 = FLOOR_Z - 6.0
    hole_z1 = PCB_TOP_Z + 3.0
    hole_depth = hole_z1 - hole_z0
    hole_z = (hole_z0 + hole_z1) / 2.0
    holes = [
        add_cylinder(f"Through_{i}", (hx, hy, hole_z), THROUGH_R, hole_depth, coll)
        for i, (hx, hy) in enumerate(HOLES)
    ]
    apply_boolean(case, join_objects(holes, "ThroughHoles"), "DIFFERENCE")
    seats = [
        add_cylinder(
            f"NutSeat_{i}",
            (hx, hy, FLOOR_Z + NUT_BORE_H / 2.0 - 0.2),
            NUT_BORE_R,
            NUT_BORE_H + 0.6,
            coll,
        )
        for i, (hx, hy) in enumerate(HOLES)
    ]
    apply_boolean(case, join_objects(seats, "NutSeats"), "DIFFERENCE")


def add_end_vents(case, coll):
    vents = []
    for i, vx in enumerate([-12.0, -6.0, 0.0, 6.0, 12.0]):
        vents.append(
            add_cylinder(
                f"EndVent_{i}",
                (vx, SPK_Y_MIN + SPK_POCKET_L + WALL, SPK_FLOOR_Z + 0.6 + SPK_T / 2.0),
                1.4,
                8.0,
                coll,
            )
        )
        vents[-1].rotation_euler = (math.radians(90.0), 0.0, 0.0)
    apply_boolean(case, join_objects(vents, "EndVents"), "DIFFERENCE")


def build_case_bottom(coll, mats):
    case = create_rounded_box(
        "Case_Bottom",
        OUTER_W,
        OUTER_L,
        BOTTOM_H,
        CORNER_R,
        coll,
        mats["bottom"],
        (0.0, BODY_CENTER_Y, FLOOR_Z),
    )
    cut_box(case, 0.0, 0.0, INNER_FLOOR_Z + (PCB_TOP_Z - INNER_FLOOR_Z) / 2.0 + 0.6, MAIN_INNER_W, MAIN_INNER_L, BOTTOM_H)
    cut_box(
        case,
        0.0,
        SPK_CENTER_Y,
        SPK_FLOOR_Z + SPK_POCKET_T / 2.0 + 0.8,
        SPK_POCKET_W,
        SPK_POCKET_L,
        SPK_POCKET_T + 2.0,
    )
    cut_box(case, 18.0, BAT_CENTER_Y - BAT_POCKET_L / 2.0 + 4.0, INNER_FLOOR_Z + 3.0, 10.0, 12.0, 6.0)
    cut_box(case, -18.0, 44.4, -2.0, 4.0, 6.0, 6.0)
    cut_box(case, 0.0, -44.0, -1.8, 12.5, 8.0, 5.5)
    cut_box(case, 26.0, SD_Y, -0.9, 8.0, 15.5, 3.8)
    cut_cyl(case, 25.5, SD_Y, -0.5, 5.0, 8.0)
    buttons = [
        add_cylinder("BtnHole_0", (RESET_X, BTN_Y, FLOOR_Z + BOTTOM_H / 2.0), 1.6, BOTTOM_H + 4.0, coll),
        add_cylinder("BtnHole_1", (BOOT_X, BTN_Y, FLOOR_Z + BOTTOM_H / 2.0), 1.6, BOTTOM_H + 4.0, coll),
    ]
    apply_boolean(case, join_objects(buttons, "ButtonHoles"), "DIFFERENCE")
    add_standoffs(case, coll)
    add_through_bolts(case, coll)
    add_end_vents(case, coll)
    return case


def add_speaker_grill(case, coll):
    slots = []
    for i in range(7):
        x = -15.0 + i * 5.0
        slots.append(
            add_cube(
                f"Grill_{i}",
                (x, SPK_CENTER_Y, PCB_TOP_Z + TOP_H - 0.6),
                (2.6, 18.0, 4.0),
                coll,
            )
        )
    apply_boolean(case, join_objects(slots, "GrillSlots"), "DIFFERENCE")


def build_case_top(coll, mats):
    case = create_rounded_box(
        "Case_Top",
        OUTER_W,
        OUTER_L,
        TOP_H,
        CORNER_R,
        coll,
        mats["top"],
        (0.0, BODY_CENTER_Y, PCB_TOP_Z),
    )
    cut_box(case, 0.0, SCREEN_Y, 3.75, 50.8, 70.0, 4.4)
    cut_box(case, 0.0, ACTIVE_Y, 5.0, 44.5, 59.5, 6.0)
    cut_cyl(case, 15.0, 38.5, 4.1, 0.75, 8.0)
    cut_box(case, 0.0, SPK_CENTER_Y, PCB_TOP_Z + 1.9, SPK_POCKET_W, SPK_POCKET_L, 4.0)
    thru = []
    bores = []
    for i, (hx, hy) in enumerate(HOLES):
        thru.append(add_cylinder(f"TopHole_{i}", (hx, hy, PCB_TOP_Z + TOP_H / 2.0), 1.7, TOP_H + 2.0, coll))
        bores.append(add_cylinder(f"TopBore_{i}", (hx, hy, PCB_TOP_Z + TOP_H - 1.0), 3.1, 3.0, coll))
    apply_boolean(case, join_objects(thru, "TopHoles"), "DIFFERENCE")
    apply_boolean(case, join_objects(bores, "TopBores"), "DIFFERENCE")
    add_speaker_grill(case, coll)
    return case


def setup_studio(coll, scene):
    for name in ["Studio_KeyLight", "Studio_FillLight", "Studio_Camera"]:
        old = bpy.data.objects.get(name)
        if old:
            bpy.data.objects.remove(old, do_unlink=True)
    bpy.ops.object.light_add(type="AREA", location=(80.0, -110.0, 90.0))
    key = bpy.context.active_object
    key.name = "Studio_KeyLight"
    key.data.energy = 500.0
    key.data.size = 150.0
    link_to_collection(key, coll)
    bpy.ops.object.light_add(type="AREA", location=(-90.0, 70.0, 70.0))
    fill = bpy.context.active_object
    fill.name = "Studio_FillLight"
    fill.data.energy = 250.0
    fill.data.size = 200.0
    link_to_collection(fill, coll)
    bpy.ops.object.camera_add(
        location=(150.0, -170.0, 110.0),
        rotation=(math.radians(58.0), 0.0, math.radians(40.0)),
    )
    cam = bpy.context.active_object
    cam.name = "Studio_Camera"
    link_to_collection(cam, coll)
    scene.camera = cam
    world = scene.world or bpy.data.worlds.new("World")
    scene.world = world
    world.use_nodes = True
    bg = next((n for n in world.node_tree.nodes if n.type == "BACKGROUND"), None)
    if bg:
        bg.inputs["Color"].default_value = (0.85, 0.86, 0.88, 1.0)
        bg.inputs["Strength"].default_value = 1.0
    return cam


def export_stls(bottom, top, extras):
    os.makedirs(EXPORT_DIR, exist_ok=True)
    bpy.ops.object.select_all(action="DESELECT")
    bottom.select_set(True)
    bpy.context.view_layer.objects.active = bottom
    bottom_path = f"{EXPORT_DIR}/Case_Bottom.stl"
    bpy.ops.wm.stl_export(filepath=bottom_path, export_selected_objects=True, check_existing=False)
    bottom.select_set(False)
    top.select_set(True)
    bpy.context.view_layer.objects.active = top
    top_path = f"{EXPORT_DIR}/Case_Top.stl"
    bpy.ops.wm.stl_export(filepath=top_path, export_selected_objects=True, check_existing=False)
    top.select_set(False)
    for obj in [bottom, top, *extras]:
        obj.select_set(True)
    assembly_path = f"{EXPORT_DIR}/Full_Enclosure_Assembly.stl"
    bpy.ops.wm.stl_export(filepath=assembly_path, export_selected_objects=True, check_existing=False)
    bpy.ops.object.select_all(action="DESELECT")
    return {"bottom_stl": bottom_path, "top_stl": top_path, "assembly_stl": assembly_path}


def render_view(scene, filepath):
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = filepath
    scene.render.resolution_x = 1920
    scene.render.resolution_y = 1080
    if hasattr(scene, "eevee"):
        scene.eevee.taa_render_samples = 16
    bpy.ops.render.render(write_still=True)


def explode(parts, restore=False):
    offsets = {
        "Case_Top": (0.0, 0.0, 28.0),
        "Screen_Glass": (0.0, 0.0, 18.0),
        "Screen_Display": (0.0, 0.0, 18.0),
        "PCB_Board": (0.0, 0.0, 8.0),
        "Speaker_Module": (0.0, 18.0, -6.0),
        "Speaker_Cone": (0.0, 18.0, -6.0),
        "Battery_603048": (0.0, -16.0, -10.0),
        "Battery_PCM": (0.0, -16.0, -10.0),
        "Case_Bottom": (0.0, 0.0, -18.0),
    }
    sign = -1.0 if restore else 1.0
    for obj in parts:
        delta = offsets.get(obj.name)
        if delta:
            obj.location = (
                obj.location.x + sign * delta[0],
                obj.location.y + sign * delta[1],
                obj.location.z + sign * delta[2],
            )


def create_enclosure():
    colls = setup_scene()
    mats = make_materials()
    pcb, display = build_reference_board(colls["V2_Reference"], mats)
    battery, pcm, speaker, cone = build_battery_and_speaker(colls["V2_Reference"], mats)
    glass = bpy.data.objects["Screen_Glass"]
    bottom = build_case_bottom(colls["V2_Case_Bottom"], mats)
    top = build_case_top(colls["V2_Case_Top"], mats)
    scene = bpy.context.scene
    setup_studio(colls["V2_Studio"], scene)
    extras = [pcb, glass, display, battery, pcm, speaker, cone]
    exported = export_stls(bottom, top, extras)
    render_view(scene, RENDER_PATH)
    parts = [bottom, top, *extras]
    explode(parts)
    render_view(scene, EXPLODED_PATH)
    explode(parts, restore=True)
    bpy.ops.wm.save_as_mainfile(filepath=BLEND_PATH, copy=True, check_existing=False)
    return {
        "status": "success",
        "outer_mm": {"width": OUTER_W, "length": OUTER_L, "height": BOTTOM_H + TOP_H},
        "battery_pocket_mm": {"width": BAT_POCKET_W, "length": BAT_POCKET_L, "height": BAT_POCKET_T},
        "speaker_pocket_mm": {"width": SPK_POCKET_W, "length": SPK_POCKET_L, "height": SPK_POCKET_T},
        "objects": [obj.name for obj in bpy.data.objects if obj.name.startswith(("Case_", "Battery_", "Speaker_", "PCB_", "Screen_"))],
        "exported_files": {
            **exported,
            "hero_png": RENDER_PATH,
            "exploded_png": EXPLODED_PATH,
            "blend": BLEND_PATH,
        },
    }


result = create_enclosure()
