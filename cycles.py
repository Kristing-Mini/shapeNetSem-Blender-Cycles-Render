
# blender --background --python mytest.py -- --views 10 --rotation w x y z --output_folder /tmp /path/to/my.obj

# batch
# find ~/desktop/test_model -name \*.obj -exec
# blender  --python final_generate_img.py -- --views 2 --rotation 1 0 0 0 --scale 0.15 --output_folder ./finaltesttest  {} \;

import argparse, sys, os
import bpy
import glob
from math import radians
import numpy as np
import math, random
import time
import copy
import mathutils


parser = argparse.ArgumentParser(description='Renders given obj file by rotation a camera around it.')
parser.add_argument('--views', type=int, default=2,
                    help='number of views to be rendered')
parser.add_argument('--chose_one', type=int, default=1,
                    help='number of gpu')
parser.add_argument('--chose_second', type=int, default=2,
                    help='number of gpu')
parser.add_argument('--obj_file', type=str,
                    help='Path to the obj file to be rendered.')
parser.add_argument('--output_folder', type=str, default='/tmp',
                    help='The path the output will be dumped to.')
parser.add_argument('--format', type=str, default='PNG',
                    help='Format of files generated. Either PNG or OPEN_EXR')


########################### Settings ####################################
argv = sys.argv[sys.argv.index("--") + 1:]
args = parser.parse_args(argv)
print('args', args)


bpy.context.scene.unit_settings.system = 'METRIC'
bpy.context.scene.cycles.samples = 60
scene = bpy.context.scene
scene.render.resolution_x = 512
scene.render.resolution_y = 512
scene.render.tile_x = 256
scene.render.tile_y = 256
scene.cycles.max_bounces = 10
scene.render.resolution_percentage = 100
scene.render.alpha_mode = 'TRANSPARENT'
scene.render.image_settings.file_format = 'PNG'  # set output format to .png


########################## World #####################################
bpy.context.scene.world.use_nodes = True
node_tree = bpy.context.scene.world.node_tree
nodes = node_tree.nodes
links = node_tree.links
while(nodes):
    nodes.remove(nodes[0])

output = nodes.new("ShaderNodeOutputWorld")
background = nodes.new("ShaderNodeBackground")
links.new(background.outputs[0],output.inputs['Surface'])
background.inputs[0].default_value = (1, 1, 1, 1)

############################### Light #######################################
lamp = bpy.data.lamps['Lamp']
# <Vector (4.0762, 1.0055, 5.9039)>
lamp = bpy.data.lamps['Lamp']
lamp.use_nodes = True
node_tree = lamp.node_tree
nodes = node_tree.nodes
links = node_tree.links
while(nodes):
    nodes.remove(nodes[0])

lamp_output = nodes.new("ShaderNodeOutputLamp")
lamp_emis = nodes.new("ShaderNodeEmission")
links.new(lamp_emis.outputs[0],lamp_output.inputs['Surface'])
lamp_emis.inputs[0].default_value = (1, 1, 1, 1)
lamp_emis.inputs['Strength'].default_value = 100

bpy.ops.object.lamp_add(type='SUN')
sun = bpy.context.scene.objects['Sun']
sun.rotation_euler[0] = radians(180)
bpy.data.lamps['Sun'].energy = 0.5
bpy.context.scene.objects['Sun'].select = False

###################### Set up rendering of depth map. mask nodes#############################
bpy.context.scene.use_nodes = True
tree = bpy.context.scene.node_tree
links = tree.links
# Add passes for additionally dumping albedo and normals.
bpy.context.scene.render.layers["RenderLayer"].use_pass_color = True
bpy.context.scene.render.layers["RenderLayer"].use_pass_object_index = True
bpy.context.scene.render.image_settings.file_format = 'PNG'
bpy.context.scene.render.image_settings.color_depth = '8'
bpy.context.scene.render.image_settings.compression = 100
bpy.context.scene.cycles.blur_glossy = 0.5

for n in tree.nodes:
    tree.nodes.remove(n)

render_layers = tree.nodes.new('CompositorNodeRLayers')
ID_mask = tree.nodes.new('CompositorNodeIDMask')
mask_output = tree.nodes.new(type="CompositorNodeOutputFile")
depth_file_output = tree.nodes.new(type="CompositorNodeOutputFile")
links.new(render_layers.outputs['IndexOB'], ID_mask.inputs[0])
links.new(ID_mask.outputs['Alpha'], mask_output.inputs['Image'])
links.new(render_layers.outputs['Depth'], depth_file_output.inputs[0])
ID_mask.index = 1
mask_output.format.color_mode = 'RGB'

depth_file_output.label = 'Depth Output'
depth_file_output.format.file_format = 'OPEN_EXR'
depth_file_output.format.color_depth = '32'
depth_file_output.format.compression = 100
mask_output.format.color_mode = 'BW'
mask_output.format.color_depth = '8'
mask_output.format.compression = 100


############################# Camera #############################################
def parent_obj_to_camera(b_camera):
    origin = (0, 0, 0)
    b_empty = bpy.data.objects.new("Empty", None)
    b_empty.location = origin
    b_camera.parent = b_empty  # setup parenting
    scn = bpy.context.scene
    scn.objects.link(b_empty)
    scn.objects.active = b_empty
    return b_empty


camera = bpy.context.scene.objects['Camera']
camera_constraint = camera.constraints.new(type='TRACK_TO')
camera_constraint.track_axis = 'TRACK_NEGATIVE_Z'
camera_constraint.up_axis = 'UP_Y'
camera.rotation_mode = 'XYZ'
b_empty = parent_obj_to_camera(camera)
camera_constraint.target = b_empty
camera.rotation_mode = 'QUATERNION'


########################## Texture change #############################################
def getTexture(getmaterial, addtexture):
    getmaterial.use_nodes = True
    nt = getmaterial.node_tree
    nodes = nt.nodes
    links = nt.links
    while (nodes):
        nodes.remove(nodes[0])
    texCor = nodes.new("ShaderNodeTexCoord")
    texture = nodes.new("ShaderNodeTexImage")
    diffuse = nodes.new("ShaderNodeBsdfDiffuse")
    transparent = nodes.new("ShaderNodeBsdfTransparent")
    mixShader = nodes.new("ShaderNodeMixShader")
    output = nodes.new("ShaderNodeOutputMaterial")
    texture.image = addtexture.texture.image
    transparent.inputs[0].default_value = (0, 0, 0, 1)
    links.new(texCor.outputs['UV'], texture.inputs['Vector'])
    links.new(texture.outputs['Color'], diffuse.inputs['Color'])
    links.new(texture.outputs['Alpha'], mixShader.inputs[0])
    links.new(diffuse.outputs['BSDF'], mixShader.inputs[2])
    links.new(transparent.outputs['BSDF'], mixShader.inputs[1])
    links.new(mixShader.outputs['Shader'], output.inputs['Surface'])

def cycle_use():
    bpy.context.scene.render.engine='CYCLES'
    prefs = bpy.context.user_preferences.addons['cycles'].preferences
    ######################## GPU chose##################################
    # bpy.context.scene.cycles.device = 'GPU'
    # bpy.context.user_preferences.addons['cycles'].preferences.compute_device_type = 'CUDA'
    # chose = 0
    # for d in prefs.devices:
    #     if chose==0 or chose == args.chose_one or chose == args.chose_second:
    #         d.use = True
    #     else:
    #         d.use =  False
    #     chose += 1
    

def generate_img(object_path, num, filename):
    start = time.time()
    for m in bpy.data.materials:
        m.user_clear()
        bpy.data.materials.remove(m)
    for select_object in bpy.context.scene.objects:
        if select_object.name in ['Camera', 'Lamp', 'Plane', 'Empty','Sun']:
            continue
        select_object.select = True
        bpy.ops.object.delete()
    bpy.context.scene.render.engine = 'BLENDER_RENDER'
    # Import new object
    bpy.ops.import_scene.obj(filepath=object_path)
    cycle_use()
    for select_object in bpy.context.scene.objects:
        if select_object.name in ['Camera', 'Lamp', 'Plane', 'Empty','Sun']:
            continue
        select_object.pass_index = 1
        bpy.context.scene.objects.active = select_object
        select_object.select = True
        bpy.context.scene.objects['Camera'].data.dof_object = select_object
        bpy.ops.mesh.customdata_custom_splitnormals_clear()

        ##normalization
        v_min = []
        v_max = []
        for i in range(3):
            v_min.append(min([vertex.co[i] for vertex in select_object.data.vertices]))
            v_max.append(max([vertex.co[i] for vertex in select_object.data.vertices]))

        v_min = mathutils.Vector(v_min)
        v_max = mathutils.Vector(v_max)
        scale = max(v_max - v_min)
        v_shift = (v_max - v_min) / 2 / scale

        for v in select_object.data.vertices:
            v.co -= v_min
            v.co /= scale
            v.co -= v_shift
            v.co *= 2

        bpy.ops.object.modifier_add(type='DISPLACE')
        bpy.context.object.modifiers['Displace'].strength = 1e-04
        bpy.ops.object.modifier_apply(apply_as='DATA', modifier='Displace')
        select_object.rotation_euler[0] = radians(0)

        material_num = len(select_object.material_slots)
        for i in range(0, material_num):
            temp_material = select_object.material_slots[i].material
            texture_num = len(temp_material.texture_slots)
            for j in range(0, texture_num):
                if temp_material.texture_slots[j]:
                    getTexture(temp_material, temp_material.texture_slots[j])
                else:
                    temp_material.use_nodes = True
        distance_unit = max(select_object.dimensions) * 2


    ###############################Camera###############################
    obj_name = os.path.split(object_path)[1].split('.')[0]
    fp = os.path.join(args.output_folder, obj_name)

    for output_node in [depth_file_output, mask_output]:
        output_node.base_path = ''

    leng = 2
    stepsize = 360.0 / args.views
    camera.location = (0, 0, distance_unit)
    camera.rotation_euler = (0, 0, 0)
    camera_info_id = 'dist_{0:02d}'.format(int(leng))
    scene.render.filepath = fp + '/' + camera_info_id
    depth_file_output.file_slots[0].path = scene.render.filepath + "_depth"
    mask_output.file_slots[0].path = scene.render.filepath + "_mask"
    bpy.ops.render.render(write_still=True)

    x = 0
    y = np.sqrt((distance_unit) ** 2 * 1 / 2)
    z = np.sqrt((distance_unit) ** 2 * 1 / 2)
    camera.location = (x, y, z)
    for i in range(0, args.views):
        print("Rotation {}, {}".format((stepsize * i), radians(stepsize * i)), 'num', num)
        camera_info_id = 'dist_{0:02d}'.format(int(leng)) + '_agl_{0:03d}'.format(int(i * stepsize))
        scene.render.filepath = fp + '/' + camera_info_id
        depth_file_output.file_slots[0].path = scene.render.filepath + "_depth"
        mask_output.file_slots[0].path = scene.render.filepath + "_mask"
        bpy.ops.render.render(write_still=True)  # render still
        x = camera.location[0]
        y = camera.location[1]
        theta = radians(stepsize)
        final_x = x * math.cos(theta) - y * math.sin(theta)
        final_y = x * math.sin(theta) + y * math.cos(theta)
        camera.location[0] = final_x
        camera.location[1] = final_y


    end_time = time.time()
    print('*****************time*************', end_time - start)


def read_info(files_path):
    print('begin rendering')
    files = glob.glob(files_path + '/*.obj')
    num = 0
    for sub_file in files:
        num += 1
        filename, file_ext = os.path.splitext(sub_file)
        filename = os.path.basename(filename)
        generate_img(sub_file, num, filename)

files_path = args.obj_file
read_info(files_path)


bpy.ops.wm.quit_blender()


