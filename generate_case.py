import bpy
import bmesh
import math
import os

def create_enclosure():
    # -------------------------------------------------------------
    # 1. SCENE SETUP & CLEANUP
    # -------------------------------------------------------------
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.length_unit = 'MILLIMETERS'
    scene.unit_settings.scale_length = 0.001

    # Remove existing objects from previous runs if any
    for obj_name in ["PCB_Board", "Screen_Glass", "Screen_Display", "Screen_Bezel_Border",
                     "USBC_Receptacle", "MicroSD_Socket", "Button_Reset", "Button_Boot",
                     "Case_Bottom", "Case_Top", "Studio_Camera", "Studio_KeyLight", "Studio_FillLight"]:
        if obj_name in bpy.data.objects:
            bpy.data.objects.remove(bpy.data.objects[obj_name], do_unlink=True)

    # Collections setup
    def get_or_create_collection(name):
        if name in bpy.data.collections:
            return bpy.data.collections[name]
        coll = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(coll)
        return coll

    ref_coll = get_or_create_collection("Reference_ESP32_Board")
    case_bottom_coll = get_or_create_collection("Case_Bottom")
    case_top_coll = get_or_create_collection("Case_Top")
    studio_coll = get_or_create_collection("Studio_Setup")

    def link_to_collection(obj, target_coll):
        for c in list(obj.users_collection):
            c.objects.unlink(obj)
        target_coll.objects.link(obj)

    # -------------------------------------------------------------
    # 2. MATERIAL DEFINITIONS
    # -------------------------------------------------------------
    def get_or_create_mat(name, color=(0.8, 0.8, 0.8, 1.0), roughness=0.3, metallic=0.0, emission=None):
        if name in bpy.data.materials:
            return bpy.data.materials[name]
        mat = bpy.data.materials.new(name=name)
        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        bsdf = nodes.get("Principled BSDF")
        if bsdf:
            bsdf.inputs['Base Color'].default_value = color
            bsdf.inputs['Roughness'].default_value = roughness
            bsdf.inputs['Metallic'].default_value = metallic
            if emission:
                bsdf.inputs['Emission Color'].default_value = emission
                bsdf.inputs['Emission Strength'].default_value = 2.0
        return mat

    mat_pcb = get_or_create_mat("Mat_PCB_DarkGreen", (0.02, 0.12, 0.04, 1.0), roughness=0.4, metallic=0.0)
    mat_metal = get_or_create_mat("Mat_Silver_Metal", (0.85, 0.85, 0.88, 1.0), roughness=0.2, metallic=0.9)
    mat_glass = get_or_create_mat("Mat_Touch_Glass", (0.1, 0.1, 0.12, 0.8), roughness=0.05, metallic=0.1)
    mat_screen_ui = get_or_create_mat("Mat_Display_UI", (0.05, 0.35, 0.8, 1.0), roughness=0.2, emission=(0.1, 0.5, 1.0, 1.0))
    mat_button = get_or_create_mat("Mat_Button_Actuator", (0.9, 0.2, 0.2, 1.0), roughness=0.3, metallic=0.2)
    mat_case_bottom = get_or_create_mat("Mat_Case_MatteDark", (0.12, 0.12, 0.13, 1.0), roughness=0.45, metallic=0.05)
    mat_case_top = get_or_create_mat("Mat_Case_SlateGrey", (0.18, 0.19, 0.21, 1.0), roughness=0.4, metallic=0.05)

    # -------------------------------------------------------------
    # 3. HELPER FUNCTIONS FOR MESH CREATION
    # -------------------------------------------------------------
    def create_rounded_box(name, width, length, height, radius, collection, material, location=(0,0,0)):
        """Creates a rounded rectangular cuboid with filleted vertical edges."""
        bm = bmesh.new()
        w2 = width / 2.0
        l2 = length / 2.0
        r = min(radius, w2, l2)
        segments = 8
        verts_2d = []

        corners = [
            (w2 - r, l2 - r, 0, math.pi / 2.0),
            (-w2 + r, l2 - r, math.pi / 2.0, math.pi),
            (-w2 + r, -l2 + r, math.pi, 3.0 * math.pi / 2.0),
            (w2 - r, -l2 + r, 3.0 * math.pi / 2.0, 2.0 * math.pi)
        ]
        for cx, cy, start_ang, end_ang in corners:
            for i in range(segments):
                ang = start_ang + (end_ang - start_ang) * (i / segments)
                x = cx + r * math.cos(ang)
                y = cy + r * math.sin(ang)
                verts_2d.append((x, y))

        bottom_verts = [bm.verts.new((x, y, 0.0)) for x, y in verts_2d]
        bottom_face = bm.faces.new(bottom_verts)

        geom = bmesh.ops.extrude_face_region(bm, geom=[bottom_face])
        verts_extruded = [v for v in geom['geom'] if isinstance(v, bmesh.types.BMVert)]
        bmesh.ops.translate(bm, vec=(0, 0, height), verts=verts_extruded)

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

    def apply_cylinder_hole(target_obj, x, y, z_start, z_end, radius, segments=24):
        """Boolean difference a cylinder hole at (x, y)."""
        bpy.ops.mesh.primitive_cylinder_add(
            vertices=segments,
            radius=radius,
            depth=abs(z_end - z_start) + 2.0,
            location=(x, y, (z_start + z_end) / 2.0)
        )
        cutter = bpy.context.active_object
        mod = target_obj.modifiers.new(name="Hole", type='BOOLEAN')
        mod.operation = 'DIFFERENCE'
        mod.object = cutter
        bpy.context.view_layer.objects.active = target_obj
        bpy.ops.object.modifier_apply(modifier=mod.name)
        bpy.data.objects.remove(cutter, do_unlink=True)

    def apply_box_cutter(target_obj, x, y, z, sx, sy, sz):
        """Boolean difference a cuboid cutout."""
        bpy.ops.mesh.primitive_cube_add(
            size=1.0,
            location=(x, y, z),
            scale=(sx, sy, sz)
        )
        cutter = bpy.context.active_object
        mod = target_obj.modifiers.new(name="BoxCut", type='BOOLEAN')
        mod.operation = 'DIFFERENCE'
        mod.object = cutter
        bpy.context.view_layer.objects.active = target_obj
        bpy.ops.object.modifier_apply(modifier=mod.name)
        bpy.data.objects.remove(cutter, do_unlink=True)

    # -------------------------------------------------------------
    # 4. CREATE REFERENCE ESP32 BOARD
    # -------------------------------------------------------------
    # PCB: 50.0 x 86.0 x 1.6 mm, R3.5 mm corners, Z from 0.0 to 1.6 mm
    pcb = create_rounded_box("PCB_Board", 50.0, 86.0, 1.6, 3.5, ref_coll, mat_pcb, location=(0, 0, 0))

    # Mounting holes on PCB: 4x Ø3.2 mm at (±21.0, ±39.0) mm
    holes = [(-21.0, 39.0), (21.0, 39.0), (-21.0, -39.0), (21.0, -39.0)]
    for hx, hy in holes:
        apply_cylinder_hole(pcb, hx, hy, -0.5, 2.5, 1.6)

    # Screen module: 50.0 x 69.2 mm, Z from 1.6 to 5.9 mm (total 4.3 mm tall)
    # Top offset = 8.22 mm -> Y center = 0.18 mm
    screen_glass = create_rounded_box("Screen_Glass", 50.0, 69.2, 4.3, 0.5, ref_coll, mat_glass, location=(0, 0.18, 1.6))

    # Active Area display plane: 43.2 x 57.6 mm at Z = 5.91 mm
    # Top offset = 11.12 mm -> Y center = 3.08 mm
    bpy.ops.mesh.primitive_plane_add(size=1.0, location=(0, 3.08, 5.91))
    screen_ui = bpy.context.active_object
    screen_ui.name = "Screen_Display"
    screen_ui.scale = (43.2, 57.6, 1.0)
    link_to_collection(screen_ui, ref_coll)
    screen_ui.data.materials.append(mat_screen_ui)

    # USB-C receptacle: centered at bottom (X=0, Y=-43.0, Z from -3.2 to 0.0)
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, -43.0, -1.6), scale=(9.0, 7.5, 3.2))
    usbc = bpy.context.active_object
    usbc.name = "USBC_Receptacle"
    link_to_collection(usbc, ref_coll)
    usbc.data.materials.append(mat_metal)

    # MicroSD card socket: at right edge (X=+25.0, Y=+7.97, Z from -1.8 to 0.0)
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(23.5, 7.97, -0.9), scale=(15.0, 14.5, 1.8))
    msd = bpy.context.active_object
    msd.name = "MicroSD_Socket"
    link_to_collection(msd, ref_coll)
    msd.data.materials.append(mat_metal)

    # Buttons: RESET (-11.56, -39.74) & BOOT (+11.57, -39.74) on bottom surface
    for b_name, bx in [("Button_Reset", -11.56), ("Button_Boot", 11.57)]:
        bpy.ops.mesh.primitive_cylinder_add(radius=1.2, depth=2.0, location=(bx, -39.74, -1.0))
        btn = bpy.context.active_object
        btn.name = b_name
        link_to_collection(btn, ref_coll)
        btn.data.materials.append(mat_button)

    # -------------------------------------------------------------
    # 5. CREATE CASE BOTTOM (TRAY)
    # -------------------------------------------------------------
    # Wall thickness = 2.0 mm, Internal XY clearance = 0.4 mm each side
    # PCB is 50.0 x 86.0 -> Inner cavity is 50.8 x 86.8 mm
    # Outer dimensions: 54.8 mm wide x 90.8 mm long
    # Floor: Z from -7.0 to -5.0 mm (2.0 mm thick)
    # Rim height: reaches Z = +1.6 mm (flush with PCB top face) -> Total height = 8.6 mm
    case_bottom = create_rounded_box("Case_Bottom", 54.8, 90.8, 8.6, 6.0, case_bottom_coll, mat_case_bottom, location=(0, 0, -7.0))

    # Hollow out the inside cavity: 50.8 x 86.8 x 7.0 mm (Z from -5.0 to +2.0)
    apply_box_cutter(case_bottom, 0, 0, -1.5, 50.8, 86.8, 7.5)

    # Add 4 Standoff Bosses: from Z = -5.0 to 0.0 mm (5.0 mm tall, Ø6.5 mm outer)
    for hx, hy in holes:
        bpy.ops.mesh.primitive_cylinder_add(
            vertices=24,
            radius=3.25,
            depth=5.0,
            location=(hx, hy, -2.5)
        )
        boss = bpy.context.active_object
        mod_u = case_bottom.modifiers.new(name="AddBoss", type='BOOLEAN')
        mod_u.operation = 'UNION'
        mod_u.object = boss
        bpy.context.view_layer.objects.active = case_bottom
        bpy.ops.object.modifier_apply(modifier=mod_u.name)
        bpy.data.objects.remove(boss, do_unlink=True)

        # Screw pilot hole: Ø2.5 mm into boss (Z from -5.0 to 0.5)
        apply_cylinder_hole(case_bottom, hx, hy, -5.0, 0.5, 1.25)

    # Port Cutout 1: USB-C Port
    # Centered at X=0, Y=-45.4 (through bottom wall), Z from -4.5 to +1.0
    # Width = 12.0 mm, Height = 6.0 mm, Depth = 10.0 mm
    apply_box_cutter(case_bottom, 0, -44.0, -1.8, 12.5, 8.0, 5.5)

    # Port Cutout 2: MicroSD Slot
    # At right wall: X=+25.0 to +28.0, Y=+7.97, Z=-0.9
    # Width along Y = 15.0 mm, Height along Z = 3.8 mm
    apply_box_cutter(case_bottom, 26.0, 7.97, -0.9, 8.0, 15.5, 3.8)
    # Ergonomic thumb/finger scoop for SD card removal
    apply_cylinder_hole(case_bottom, 25.5, 7.97, -3.0, 2.0, 5.0)

    # Port Cutouts 3 & 4: RESET & BOOT button pinhole/stylus access tunnels
    # Located at X=-11.56 and X=+11.57, through the bottom floor/wall (Z from -7.5 to -2.0)
    for bx in [-11.56, 11.57]:
        apply_cylinder_hole(case_bottom, bx, -39.74, -8.0, -1.0, 1.6)

    # -------------------------------------------------------------
    # 6. CREATE CASE TOP (BEZEL)
    # -------------------------------------------------------------
    # Outer dimensions match bottom: 54.8 x 90.8 mm
    # Sits above bottom rim: Z from +1.6 to +6.6 mm (5.0 mm tall, 2.0 mm top wall above glass at 5.9)
    case_top = create_rounded_box("Case_Top", 54.8, 90.8, 5.0, 6.0, case_top_coll, mat_case_top, location=(0, 0, 1.6))

    # Underside stepped recess for the 50.0 x 69.2 mm glass module
    # Glass sits at Y=0.18, Z from 1.6 to 5.9 mm (4.3 mm tall)
    apply_box_cutter(case_top, 0, 0.18, 3.75, 50.8, 70.0, 4.4)

    # Touch Screen Display Window (cut through top face): 44.5 x 59.5 mm at Y=3.08
    apply_box_cutter(case_top, 0, 3.08, 5.0, 44.5, 59.5, 6.0)

    # Microphone acoustic pinhole: Ø1.5 mm at X=+15.0, Y=+38.5
    apply_cylinder_hole(case_top, 15.0, 38.5, 1.0, 7.0, 0.75)

    # 4x Screw Counterbores on Top Bezel: matching mounting holes at (±21.0, ±39.0)
    for hx, hy in holes:
        # Through hole for M3 screw shank: Ø3.4 mm (Z from 1.0 to 7.0)
        apply_cylinder_hole(case_top, hx, hy, 1.0, 7.0, 1.7)
        # Counterbore for M3 screw head: Ø6.2 mm, depth 2.5 mm from top surface (Z from 4.5 to 7.0)
        apply_cylinder_hole(case_top, hx, hy, 4.5, 7.5, 3.1)

    # -------------------------------------------------------------
    # 7. STUDIO LIGHTING & CAMERA SETUP
    # -------------------------------------------------------------
    # Studio Key Light
    bpy.ops.object.light_add(type='AREA', location=(60.0, -80.0, 90.0))
    key_light = bpy.context.active_object
    key_light.name = "Studio_KeyLight"
    key_light.data.energy = 80.0
    key_light.data.size = 100.0
    link_to_collection(key_light, studio_coll)

    # Studio Fill Light
    bpy.ops.object.light_add(type='AREA', location=(-80.0, 60.0, 70.0))
    fill_light = bpy.context.active_object
    fill_light.name = "Studio_FillLight"
    fill_light.data.energy = 40.0
    fill_light.data.size = 120.0
    link_to_collection(fill_light, studio_coll)

    # Studio Camera
    bpy.ops.object.camera_add(location=(120.0, -140.0, 110.0), rotation=(math.radians(60), 0, math.radians(40)))
    cam = bpy.context.active_object
    cam.name = "Studio_Camera"
    link_to_collection(cam, studio_coll)
    bpy.context.scene.camera = cam

    # -------------------------------------------------------------
    # 8. EXPORT 3D PRINTABLE STL FILES
    # -------------------------------------------------------------
    workspace_dir = "C:/Users/dsuth/Documents/Code Projects/ESP32 project"
    export_dir = f"{workspace_dir}/docs/dimensions/case_stl"
    os.makedirs(export_dir, exist_ok=True)

    # Deselect all
    bpy.ops.object.select_all(action='DESELECT')

    # Export Bottom Shell
    case_bottom.select_set(True)
    bpy.context.view_layer.objects.active = case_bottom
    bottom_stl_path = f"{export_dir}/Case_Bottom.stl"
    bpy.ops.wm.stl_export(filepath=bottom_stl_path, export_selected_objects=True)
    case_bottom.select_set(False)

    # Export Top Shell
    case_top.select_set(True)
    bpy.context.view_layer.objects.active = case_top
    top_stl_path = f"{export_dir}/Case_Top.stl"
    bpy.ops.wm.stl_export(filepath=top_stl_path, export_selected_objects=True)
    case_top.select_set(False)

    # Export Full Assembly
    case_bottom.select_set(True)
    case_top.select_set(True)
    pcb.select_set(True)
    screen_glass.select_set(True)
    screen_ui.select_set(True)
    usbc.select_set(True)
    msd.select_set(True)
    assembly_stl_path = f"{export_dir}/Full_Enclosure_Assembly.stl"
    bpy.ops.wm.stl_export(filepath=assembly_stl_path, export_selected_objects=True)

    # Render high-res viewport preview
    render_path = f"{workspace_dir}/docs/dimensions/enclosure_render.png"
    scene.render.image_settings.file_format = 'PNG'
    scene.render.filepath = render_path
    scene.render.resolution_x = 1920
    scene.render.resolution_y = 1080
    if hasattr(scene, 'eevee'):
        scene.eevee.taa_render_samples = 16
    bpy.ops.render.render(write_still=True)

    return {
        "status": "success",
        "objects_created": [o.name for o in bpy.data.objects],
        "exported_files": {
            "bottom_stl": bottom_stl_path,
            "top_stl": top_stl_path,
            "assembly_stl": assembly_stl_path,
            "render_png": render_path
        }
    }

result = create_enclosure()
