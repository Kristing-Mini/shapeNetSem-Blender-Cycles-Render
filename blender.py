
# blender --background --python blender.py -- --views=6 --output_folder=/tmp --obj_file= path of the dir where objs are

import argparse, sys, os
import bpy
import glob
from math import radians
import numpy as np
import math, random
import time
import copy
from multiprocessing.dummy import Pool
import mathutils


parser = argparse.ArgumentParser(description='Renders given obj file by rotation a camera around it.')
parser.add_argument('--views', type=int, default=6,
                    help='number of views to be rendered')
parser.add_argument('--obj_file', type=str,
                    help='Path to the obj file to be rendered.')
parser.add_argument('--output_folder', type=str, default='./blender_img',
                    help='The path the output will be dumped to.')
parser.add_argument('--format', type=str, default='PNG',
                    help='Format of files generated. Either PNG or OPEN_EXR')

argv = sys.argv[sys.argv.index("--") + 1:]
args = parser.parse_args(argv)
print('args', args)

########################### Settings ####################################
## set the unit meter
bpy.context.scene.unit_settings.system = 'METRIC'
scene = bpy.context.scene
scene.render.resolution_x = 1024
scene.render.resolution_y = 1024
scene.render.alpha_mode = 'TRANSPARENT'
scene.render.resolution_percentage = 50   # the final render result of picture
scene.render.image_settings.file_format = 'PNG'  # set output format to .png

########################## World Setting && Light################################
###### Light type // Location// Rotation // shadow_method//energy//color ########
world = bpy.data.worlds['World']
world.horizon_color = (1,1,1)

lamp = bpy.data.lamps['Lamp']
# <Vector (4.0762, 1.0055, 5.9039)>
lamp.shadow_method = 'NOSHADOW'
lamp.use_specular = False
lamp.shadow_soft_size = 0.1
lamp.energy = 5
bpy.ops.object.lamp_add(type='SUN')
sun = bpy.context.scene.objects['Sun']
sun.rotation_euler[0] = radians(180)
bpy.data.lamps['Sun'].energy = 0.5
bpy.context.scene.objects['Sun'].select = False

###################### Set up rendering of rgb depth map. mask nodes#####################
bpy.context.scene.use_nodes = True
tree = bpy.context.scene.node_tree
links = tree.links
for n in tree.nodes:
    tree.nodes.remove(n)

render_layers = tree.nodes.new('CompositorNodeRLayers')
ID_mask = tree.nodes.new('CompositorNodeIDMask')
mask_output = tree.nodes.new(type="CompositorNodeOutputFile")
depth_file_output = tree.nodes.new(type="CompositorNodeOutputFile")
links.new(render_layers.outputs['Alpha'], ID_mask.inputs[0])
links.new(ID_mask.outputs['Alpha'], mask_output.inputs['Image'])
links.new(render_layers.outputs['Depth'], depth_file_output.inputs[0])
ID_mask.index = 1

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


def generate_img(object_path,num,filename):
    start = time.time()
    for m in bpy.data.materials:
        m.user_clear()
        bpy.data.materials.remove(m)
    for select_object in bpy.context.scene.objects:
        print(select_object.name)
        if select_object.name in ['Camera', 'Lamp', 'Empty','Sun']:
            print('get',select_object.name)
            continue
        print(select_object.name)
        select_object.select = True
        bpy.ops.object.delete()
    # Import new object
    for select_object in bpy.context.scene.objects:
        print(select_object.name,'get2')
    bpy.ops.import_scene.obj(filepath=object_path)
    for select_object in bpy.context.scene.objects:
        print(select_object.name)
        if select_object.name in ['Camera', 'Lamp', 'Empty','Sun']:
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
        bpy.context.object.modifiers['Displace'].strength = 1e-05
        bpy.ops.object.modifier_apply(apply_as='DATA', modifier='Displace')
        select_object.rotation_euler[0] = radians(0)

        material_num = len(select_object.material_slots)
        for i in range(0, material_num):
            temp_material = select_object.material_slots[i].material
            temp_material.alpha = 1

        distance_unit = max(select_object.dimensions) * 2

    ##file
    obj_name = os.path.split(object_path)[1].split('.')[0]
    fp = os.path.join(args.output_folder, obj_name)

    for output_node in [depth_file_output,mask_output]:
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
    y = np.sqrt((distance_unit) ** 2 * 1/ 2)
    z = np.sqrt((distance_unit) ** 2 * 1/ 2)
    camera.location = (x, y, z)
    for i in range(0, args.views):
        print("Rotation {}, {}".format((stepsize * i), radians(stepsize * i)))
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
    print('*****************time*************', end_time - start,filename,num)


def read_info(files_path):
    files = glob.glob(files_path + '/*.obj')
    num = 0
    print(files_path,len(files))
    for sub_file in files:
        num += 1
        filename, file_ext = os.path.splitext(sub_file)
        filename = os.path.basename(filename)
        if filename in render_list:
            ### objName
            generate_img(sub_file,num,filename)

files_path = args.obj_file
read_info(files_path)


bpy.ops.wm.quit_blender()
