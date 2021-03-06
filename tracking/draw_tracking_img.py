import glob,pdb
import os
import sys
import json
import argparse
import logging
import time
import csv
import cv2
import pycocotools.coco as coco
import random
try:
    import numpy as np
except ImportError:
    raise RuntimeError('cannot import numpy, make sure numpy package is installed')

from carla_ros.utils import *
#from utils import *
import src.lib.utils.bbox_utils as bu
sys.path.append('/home/ubuntu/xwp/Xinshuo_pyToolbox')
from xinshuo_io import is_path_exists, mkdir_if_missing, load_list_from_folder, fileparts
from xinshuo_visualization import random_colors
max_color= 10
colors = random_colors(max_color)
def get_vehicle_list(cam_gt,cam_trans):
    #vehicles_loc_list_1 = []
    vehicles_list_v = []
    id_list = []
    for ann_ind, txt in enumerate(cam_gt):
        tmp = txt[:-1].split(' ')
        #cat_id = cat_ids[tmp[0]]
        truncated = int(float(tmp[1]))
        occluded = int(tmp[2])
        alpha = float(tmp[3])
        bbox = [float(tmp[4]), float(tmp[5]), float(tmp[6]), float(tmp[7])]
        dim = [float(tmp[8]), float(tmp[9]), float(tmp[10])]
        location = [float(tmp[11]), float(tmp[12]), float(tmp[13])]
        rotation_y = float(tmp[14])
        Id = int(tmp[16])
        score = float(tmp[15])

        cord_p = np.zeros((1,4))
        cord_p[0][0] = location[2]
        cord_p[0][1] = location[0]
        cord_p[0][2] = -location[1]
        cord_p[0][3] = 1
        # cord_p = np.zeros((1,4))
        # cord_p[0][0] = location[1]
        # cord_p[0][1] = location[1]
        # cord_p[0][2] = location[2]
        # cord_p[0][3] = 1

        #rotation_y = rotation_y * 180 /np.pi
        # cam_matrix = ClientSideBoundingBoxes.get_matrix(cam_trans)
        # cam_to_world = np.dot(cam_matrix,np.transpose(cord_p))
        # ry_cam2world = ry_filter_a(rotation_y - 90 + cam_trans.rotation.yaw ) * np.pi / 180
        #vehicles_loc_list_1.append(vehicle_matrix)
        #vehicles_list_1.append({'bbox':bbox,'dim':dim,'location':location,'rotation':rotation_y,'id':Id})
        #tv1 = CamVehicle(cam_to_world[1][0],-cam_to_world[2][0],cam_to_world[0][0],*dim,ry_filter(ry_cam2world),score=score)
        tv1 = CamVehicle(location[2],location[0],-location[1],*dim,ry_filter(rotation_y),score=score,cid=Id)
        vehicles_list_v.append(tv1)
        #id_list.append(Id)
    
    return vehicles_list_v#,id_list

def get_ids(file_name,id_list=None):
    if id_list == None:
        id_list = []
    anns = open(file_name, 'r')
    for ann_ind, txt in enumerate(anns):
        tmp = txt[:-1].split(' ')
        #cat_id = cat_ids[tmp[0]]
        truncated = int(float(tmp[1]))
        occluded = int(tmp[2])
        alpha = float(tmp[3])
        bbox = [float(tmp[4]), float(tmp[5]), float(tmp[6]), float(tmp[7])]
        dim = [float(tmp[8]), float(tmp[9]), float(tmp[10])]
        location = [float(tmp[11]), float(tmp[12]), float(tmp[13])]
        rotation_y = float(tmp[14])
        car_id = int(tmp[15])
        if car_id not in id_list:
            id_list.append(car_id)
    return id_list

def vehicle_world2sensor(vehicles,cam_trans,yaw):
    ret = []
    cam_trans = ClientSideBoundingBoxes.get_matrix(cam_trans)
    for car in vehicles:
        cord_p = np.zeros((1,4))
        cord_p[0][0] = car.x
        cord_p[0][1] = car.y
        cord_p[0][2] = car.z
        cord_p[0][3] = 1
        rotation_y = car.rotation_y * 180 / np.pi

        p_in_cam1 = np.dot(np.linalg.inv(cam_trans), np.transpose(cord_p))
        ry_world2cam1 = (rotation_y - yaw) * np.pi / 180
        if p_in_cam1[0][0] < 0.2:
            continue
        tv = CamVehicle(p_in_cam1[1][0],-p_in_cam1[2][0],p_in_cam1[0][0],car.height,car.width,car.length,ry_world2cam1,cid=car.id)
        ret.append(tv)
    return ret


if __name__ == "__main__":
    argparser = argparse.ArgumentParser(description=__doc__)
    argparser.add_argument('-n',default='1',type=str,)
    args = argparser.parse_args()
    FILTER_GLOBAL = False
    NUM_CAM = 3
    cam_id_num = 9
    cam_id = 'cam{}'.format(cam_id_num)
    cam_yaw = -60
    #cam_yaw = -150
    #cam_yaw = 90
    #test_file_list = [30,31,32,33,34,35,36,51,52,53,54,55,56,57]
    test_file_list = [37]
    #test_file_list = list(range(30,58))
    test_file_num = 29
    test_file_name = '0000{:0>2d}.txt'.format(test_file_num)
    dataset_path = '/home/ubuntu/xwp/datasets/multi_view_dataset/new'
    cam_set = ['fuse_test/cam9+cam18+cam19/']
    print('processing: ',cam_set)
    camset_path = [ os.path.join(dataset_path,cam_name) for cam_name in cam_set
        #'/home/ubuntu/xwp/datasets/multi_view_dataset/new/cam1/label_test'
        # '',
        # ''
    ]
    cam_path = [os.path.join(path,'tracking_results/trk_withid/0000/') for path in camset_path]
    #cam_path = '/home/ubuntu/xwp/datasets/multi_view_dataset/new'

    cam_transform = {}
    sensors_definition_file = '/home/ubuntu/xwp/CenterNet/carla_ros/dataset.json'
    if not os.path.exists(sensors_definition_file):
        raise RuntimeError(
            "Could not read sensor-definition from {}".format(sensors_definition_file))
    with open(sensors_definition_file) as handle:
        json_actors = json.loads(handle.read())
    global_sensors = []
    for actor in json_actors["objects"]:
        global_sensors.append(actor)
    for sensor_spec in global_sensors:
        sensor_id = str(sensor_spec.pop("id"))
        spawn_point = sensor_spec.pop("spawn_point")
        point = Transform(location=Location(x=spawn_point.pop("x"), y=-spawn_point.pop("y"), z=spawn_point.pop("z")),
                rotation=Rotation(pitch=-spawn_point.pop("pitch", 0.0), yaw=-spawn_point.pop("yaw", 0.0), roll=spawn_point.pop("roll", 0.0)))
        cam_transform[sensor_id] = point
    # cam_transform = {
    #     'cam1': Transform(location=Location(x=-98, y=-130, z=4),rotation=Rotation(pitch=0, yaw=20, roll=0))
    #     # 'cam2': Transform(location=Location(x=1, y=-1, z=4),rotation=Rotation(pitch=-90, yaw=-180, roll=0)),
    #     # 'cam3': Transform(location=Location(x=1, y=-1, z=4),rotation=Rotation(pitch=-90, yaw=-180, roll=0))
    # }


    #outdir_path = '/home/ubuntu/xwp/datasets/multi_view_dataset/new/fuse_cam1'
    outdir_path = '/home/ubuntu/xwp/datasets/multi_view_dataset/new/fuse_test'
    if not os.path.exists(outdir_path):
        os.makedirs(outdir_path)

    #output_path = os.path.join(outdir_path,'label_fused')
    output_path = os.path.join(outdir_path,'label_test_trans')
    if not os.path.exists(output_path):
        os.makedirs(output_path)

    # if len(cam_path) != NUM_CAM:
    #     raise RuntimeError('expect {} cam path but got {}'.format(NUM_CAM,len(cam_path)))

    #detect_main_list = [test_file_name]
    detect_main_list = ['0000{:0>2d}.txt'.format(num) for num in test_file_list]
    to_fuse_detectlist = []
    # for cam in cam_set[1:]:
    #     to_fuse_detectlist.append('000045.txt')
    
    #result_path = '/home/ubuntu/xwp/datasets/multi_view_dataset/new//results'
    for k,pred in enumerate(detect_main_list):
        #print(i)
        anns = open(os.path.join(cam_path[0],pred),'r')
        #f = open(os.path.join(output_path,pred),'w')
        vehicles = get_vehicle_list(anns,cam_transform[cam_id])
        #box_main_list = [v.compute_box_3d() for v in vehicles]

        # for i in range(1,NUM_CAM):
        #     # if pred not in to_fuse_detectlist[i-1]:
        #     #     raise RuntimeError('{} not in {}'.format(pred,cam_path[i]))
        #     anns2 = open(os.path.join(cam_path[i],pred))
        #     vehicles2 = get_vehicle_list(anns2,cam_transform['cam9'])
            #box_to_fuse_list = [v.compute_box_3d() for v in vehicels2]
            #vehicles = bu.vehicle3d_matching(vehicles,vehicles2,iou_threshold=0.001,fusion=bu.vehicle_mean_fusion)
            #vehicles = bu.vehicle3d_matching(vehicles,vehicles2,iou_threshold=0.1,fusion=None)
            #vehicles = bu.vehicle3d_matching(vehicles,vehicles2,iou_threshold=0.1)
            # for cid in id_list2:
            #     if cid not in id_list:
            #         id_list.append(cid)
        v_list = vehicle_world2sensor(vehicles,cam_transform[cam_id],cam_yaw)
        box3d_list = [car.compute_box_3d() for car in v_list]
        id_list = [car.id for car in v_list]
        color_list = [tuple([int(tmp * 255) for tmp in colors[obj.id % max_color]]) for obj in v_list]
        
        #print(box3d_list)
        bird_view = add_bird_view(box3d_list)
        #cv2.imshow('bird',bird_view)
        image = cv2.imread('/home/ubuntu/xwp/datasets/multi_view_dataset/new/cam_sample/image_2/0{:0>2d}9{:0>2d}.png'.format(int(cam_id_num)-1,test_file_list[k]+1))
        calib = read_clib('/home/ubuntu/xwp/datasets/multi_view_dataset/new/cam1/calib/000000.txt')
        img_size = np.asarray([960,540],dtype=np.int)
        for i,(box3d,oid) in enumerate(zip(box3d_list,id_list)):
            #print(box_3d)
            color = tuple([int(tmp * 255) for tmp in colors[oid % max_color]])
            box_2d = project_to_image(box3d, calib)
            bbox = (np.min(box_2d[:,0]), np.min(box_2d[:,1]), np.max(box_2d[:,0]), np.max(box_2d[:,1]))
            if bbox[0]<0 and bbox[1] < 0 and bbox[2] > img_size[0] and bbox[3] > img_size[1]:
                continue

            bbox_crop = tuple(max(0, b) for b in bbox)
            bbox_crop = (min(img_size[0], bbox_crop[0]),
                        min(img_size[0], bbox_crop[1]),
                        min(img_size[0], bbox_crop[2]),
                        min(img_size[1], bbox_crop[3]))
            # Detect if a cropped box is empty.
            if bbox_crop[0] >= bbox_crop[2] or bbox_crop[1] >= bbox_crop[3]:
                continue
            #box_2d[:,1] = -box_2d[:,1]
            #print(box_2d)
            image = draw_box_3d(image,box_2d,color)
            text = 'ID: %d' % oid
            image = cv2.putText(image, text, (int(box_2d[4, 0]), int(box_2d[4, 1]) - 8), cv2.FONT_HERSHEY_TRIPLEX, 0.5, color=color)
        filepath = '/home/ubuntu/xwp/imgs/tracking/{}-{}.png'.format(cam_id,37)
        #cv2.imshow('img',image)
        #print('write to:',filepath)
        cv2.imwrite(filepath, image)
        #print(color_list)

        #cv2.waitKey()

        # for car in vehicles:
        #     f.write('{} 0.0 0 0 0 0 0 0'.format('Car'))
        #     f.write(' {:.4f} {:.4f} {:.4f} {:.4f} {:.4f} {:.4f} {} {}'.format(car.height,car.width,car.length,car.z,car.x,-car.y,car.rotation_y,car.score))
        #     f.write('\n')
        # f.close()
    
    # if FILTER_GLOBAL:

    #     #TODO 读取融合的相机的label_2，获取id，根据id将global中的标签过滤出来保存在融合文件夹下
    #     global_label_dir = '/home/ubuntu/xwp/datasets/multi_view_dataset/crowd_test2/global_label_2'
    #     ann_list = os.listdir(global_label_dir)
    #     #global_label_filter_dir = os.path.join(outdir_path,'global_filtered')
    #     global_label_filter_dir = os.path.join(outdir_path,'global_filtered')
    #     if not os.path.exists(global_label_filter_dir):
    #         os.makedirs(global_label_filter_dir)
    #     for label_file in ann_list:
    #         ann_path = os.path.join(global_label_dir , '{}'.format(label_file))
    #         id_list = []
    #         for cam in cam_set:
    #             single_cam_label = os.path.join(cam_path,(cam[3:]+'0001')+'.txt')
    #             id_list = get_ids(single_cam_label,id_list)

    #         out_path = os.path.join(global_label_filter_dir , '{}'.format(label_file))
    #         f = open(out_path, 'w')
    #         anns = open(ann_path, 'r')
    #         for ann_ind, txt in enumerate(anns):
    #             tmp = txt[:-1].split(' ')
    #             #cat_id = cat_ids[tmp[0]]
    #             truncated = int(float(tmp[1]))
    #             occluded = int(tmp[2])
    #             alpha = float(tmp[3])
    #             bbox = [float(tmp[4]), float(tmp[5]), float(tmp[6]), float(tmp[7])]
    #             dim = [float(tmp[8]), float(tmp[9]), float(tmp[10])]
    #             location = [float(tmp[11]), float(tmp[12]), float(tmp[13])]
    #             rotation_y = float(tmp[14])
    #             car_id = int(tmp[15])
    #             #box_3d = compute_box_3d(dim, location, rotation_y)
    #             #box_2d = project_to_image(box_3d, calib)
    #             #bbox = (np.min(box_2d[:,0]), np.min(box_2d[:,1]), np.max(box_2d[:,0]), np.max(box_2d[:,1]))

    #             if car_id in id_list:
    #                 txt="{} {} {} {} {} {} {} {} {:.4f} {:.4f} {:.4f} {:.4f} {:.4f} {:.4f} {} {}\n".format('Car', truncated, occluded, alpha, bbox[0], bbox[1], bbox[2], bbox[3], dim[0], dim[1],
    #                                     dim[2],location[0], location[1], location[2],  ry_filter(rotation_y),car_id)
    #                 f.write(txt)
    #             #f.write('\n')
    #         f.close()
