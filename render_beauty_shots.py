import bpy
import math

workspace_dir = "C:/Users/dsuth/Documents/Code Projects/ESP32 project"
scene = bpy.context.scene

# Ensure world background is clean studio gradient/white
world = scene.world
if world and world.use_nodes:
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs['Color'].default_value = (0.90, 0.91, 0.93, 1.0)
        bg.inputs['Strength'].default_value = 1.0

# Setup a Target Empty at origin
target_empty = bpy.data.objects.get("Camera_Target")
if not target_empty:
    bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 0, 0))
    target_empty = bpy.context.active_object
    target_empty.name = "Camera_Target"

cam = bpy.data.objects.get("Studio_Camera")
if not cam:
    bpy.ops.object.camera_add(location=(100, -130, 90))
    cam = bpy.context.active_object
    cam.name = "Studio_Camera"
    bpy.context.scene.camera = cam

# Add or update Track To constraint
track_mod = cam.constraints.get("TrackToTarget")
if not track_mod:
    track_mod = cam.constraints.new(type='TRACK_TO')
    track_mod.name = "TrackToTarget"
track_mod.target = target_empty
track_mod.track_axis = 'TRACK_NEGATIVE_Z'
track_mod.up_axis = 'UP_Y'

# Setup 3-point studio lighting
key = bpy.data.objects.get("Studio_KeyLight")
if key:
    key.location = (80.0, -100.0, 100.0)
    key.data.energy = 800.0
    key.data.size = 150.0

fill = bpy.data.objects.get("Studio_FillLight")
if fill:
    fill.location = (-100.0, 50.0, 80.0)
    fill.data.energy = 400.0
    fill.data.size = 200.0

# Add Rim/Back Light for crisp rim reflections
rim = bpy.data.objects.get("Studio_RimLight")
if not rim:
    bpy.ops.object.light_add(type='AREA', location=(0.0, 120.0, -40.0))
    rim = bpy.context.active_object
    rim.name = "Studio_RimLight"
rim.data.energy = 500.0
rim.data.size = 180.0

# 1. Hero Front View
cam.location = (90.0, -115.0, 75.0)
scene.render.filepath = f"{workspace_dir}/docs/dimensions/render_hero_front.png"
bpy.ops.render.render(write_still=True)

# 2. Bottom View showing USB-C and Button Pinhole Access Ports
cam.location = (0.0, -110.0, -60.0)
scene.render.filepath = f"{workspace_dir}/docs/dimensions/render_bottom_ports.png"
bpy.ops.render.render(write_still=True)

# 3. MicroSD slot side view
cam.location = (115.0, 10.0, 30.0)
scene.render.filepath = f"{workspace_dir}/docs/dimensions/render_sd_slot.png"
bpy.ops.render.render(write_still=True)

# 4. Exploded View (Displace Top Bezel by +25mm, PCB & Screen by +12mm)
case_top = bpy.data.objects.get("Case_Top")
pcb = bpy.data.objects.get("PCB_Board")
glass = bpy.data.objects.get("Screen_Glass")
disp = bpy.data.objects.get("Screen_Display")
usbc = bpy.data.objects.get("USBC_Receptacle")
msd = bpy.data.objects.get("MicroSD_Socket")
b_rst = bpy.data.objects.get("Button_Reset")
b_boot = bpy.data.objects.get("Button_Boot")

if case_top:
    case_top.location.z += 25.0
for obj in [pcb, glass, disp, usbc, msd, b_rst, b_boot]:
    if obj:
        obj.location.z += 12.0

cam.location = (110.0, -120.0, 85.0)
scene.render.filepath = f"{workspace_dir}/docs/dimensions/render_exploded.png"
bpy.ops.render.render(write_still=True)

# Reset locations back to assembled state
if case_top:
    case_top.location.z -= 25.0
for obj in [pcb, glass, disp, usbc, msd, b_rst, b_boot]:
    if obj:
        obj.location.z -= 12.0

print("All beauty renders generated successfully.")
