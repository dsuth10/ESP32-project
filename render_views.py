import bpy
import math
import os

workspace_dir = "C:/Users/dsuth/Documents/Code Projects/ESP32 project"
scene = bpy.context.scene

# Ensure world background is a pleasant light studio grey
world = scene.world
if world and world.use_nodes:
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs['Color'].default_value = (0.85, 0.86, 0.88, 1.0)
        bg.inputs['Strength'].default_value = 1.0

# Boost lights
key = bpy.data.objects.get("Studio_KeyLight")
if key:
    key.data.energy = 500.0
    key.data.size = 150.0

fill = bpy.data.objects.get("Studio_FillLight")
if fill:
    fill.data.energy = 250.0
    fill.data.size = 200.0

cam = bpy.data.objects.get("Studio_Camera")
if not cam:
    bpy.ops.object.camera_add(location=(120.0, -140.0, 110.0))
    cam = bpy.context.active_object
    cam.name = "Studio_Camera"
    bpy.context.scene.camera = cam

# 1. Front-Top Hero View
cam.location = (110.0, -130.0, 95.0)
cam.rotation_euler = (math.radians(58), 0, math.radians(40))
scene.render.filepath = f"{workspace_dir}/docs/dimensions/render_hero_front.png"
bpy.ops.render.render(write_still=True)

# 2. Bottom-Rear View showing USB-C and Button Access Ports
cam.location = (-110.0, -130.0, -90.0)
cam.rotation_euler = (math.radians(125), 0, math.radians(-140))
scene.render.filepath = f"{workspace_dir}/docs/dimensions/render_bottom_ports.png"
bpy.ops.render.render(write_still=True)

# 3. MicroSD slot side view
cam.location = (140.0, 30.0, 35.0)
cam.rotation_euler = (math.radians(78), 0, math.radians(78))
scene.render.filepath = f"{workspace_dir}/docs/dimensions/render_sd_slot.png"
bpy.ops.render.render(write_still=True)

print("Rendered all multi-angle views successfully.")
