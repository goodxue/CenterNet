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

from utils import *
import src.lib.utils.bbox_utils as bu

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
        Id = int(tmp[15])

        cord_p = np.zeros((1,4))
        cord_p[0][0] = location[2]
        cord_p[0][1] = location[0]
        cord_p[0][2] = -location[1]
        cord_p[0][3] = 1

        rotation_y = rotation_y * 180 /np.pi
        cam_matrix = ClientSideBoundingBoxes.get_matrix(cam_trans)
        cam_to_world = np.dot(cam_matrix,np.transpose(cord_p))
        ry_cam2world = (rotation_y - 90 + cam_trans.rotation.yaw ) * np.pi / 180
        #vehicles_loc_list_1.append(vehicle_matrix)
        #vehicles_list_1.append({'bbox':bbox,'dim':dim,'location':location,'rotation':rotation_y,'id':Id})
        tv1 = CamVehicle(cam_to_world[1][0],-cam_to_world[2][0],cam_to_world[0][0],*dim,ry_cam2world,Id)
        vehicles_list_v.append(tv1)
        #id_list.append(Id)
    
    return vehicles_list_v#,id_list
    


if __name__ == "__main__":
    FILTER_GLOBAL = True
    NUM_CAM = 1
    cam_path = [
        '/home/ubuntu/xwp/datasets/multi_view_dataset/new/cam1/label_test'
        # '',
        # ''
    ]
    cam_transform = {
        'cam1': Transform(location=Location(x=-98, y=-130, z=4),rotation=Rotation(pitch=0, yaw=20, roll=0))
        # 'cam2': Transform(location=Location(x=1, y=-1, z=4),rotation=Rotation(pitch=-90, yaw=-180, roll=0)),
        # 'cam3': Transform(location=Location(x=1, y=-1, z=4),rotation=Rotation(pitch=-90, yaw=-180, roll=0))
    }
    outdir_path = '/home/ubuntu/xwp/datasets/multi_view_dataset/new/fuse_cam1'
    if not os.path.exists(outdir_path):
        os.makedirs(outdir_path)

    output_path = os.path.join(outdir_path,'label_trans')
    if not os.path.exists(output_path):
        os.makedirs(output_path)

    if len(cam_path) != NUM_CAM:
        raise RuntimeError('expect {} cam path but got {}'.format(NUM_CAM,len(cam_path)))

    detect_main_list = os.listdir(cam_path[0])
    to_fuse_detectlist = []
    for i in range(1,NUM_CAM):
        to_fuse_detectlist.append(os.listdir(cam_path[i]))
    
    for pred in detect_main_list:
        anns = open(os.path.join(cam_path[0],pred),'r')
        f = open(os.path.join(output_path,pred),'w')
        vehicles = get_vehicle_list(anns,cam_transform['cam1'])
        #box_main_list = [v.compute_box_3d() for v in vehicles]

        for i in range(1,NUM_CAM):
            if pred not in to_fuse_detectlist[i-1]:
                raise RuntimeError('{} not in {}'.format(pred,cam_path[i]))
            anns2 = open(os.path.join(cam_path[i],pred))
            vehicles2 = get_vehicle_list(anns2,cam_transform[i])
            #box_to_fuse_list = [v.compute_box_3d() for v in vehicels2]
            vehicles = bu.vehicle3d_matching(vehicles,vehicles2,iou_threshold=0.1,fusion=bu.vehicle_mean_fusion)
            # for cid in id_list2:
            #     if cid not in id_list:
            #         id_list.append(cid)

        for car in vehicles:
            f.write('{} 0.0 0 0 0 0 0 0'.format('Car'))
            f.write(' {:.4f} {:.4f} {:.4f} {:.4f} {:.4f} {:.4f} {} {}'.format(car.height,car.width,car.length,car.z,car.x,-car.y,car.rotation_y,car.id))
            f.write('\n')
        f.close()
    
    if FILTER_GLOBAL:
        #TODO 读取融合的相机的label_2，获取id，根据id将global中的标签过滤出来保存在融合文件夹下
        global_label_dir = '/home/ubuntu/xwp/datasets/multi_view_dataset/new/global_label_new'
        ann_list = os.listdir(ann_dir)
        global_label_filter_dir = os.path.join(outdir_path,'global_filtered')
        for label_file in ann_list:
            ann_path = os.path.join(global_label_dir , '{}'.format(label_file))
            out_path = output_dir + '{}'.format(label_file)
            f = open(global_label_filter_dir, 'w')
            anns = open(ann_path, 'r')
            for ann_ind, txt in enumerate(anns):
                tmp = txt[:-1].split(' ')
                cat_id = cat_ids[tmp[0]]
                truncated = int(float(tmp[1]))
                occluded = int(tmp[2])
                alpha = float(tmp[3])
                bbox = [float(tmp[4]), float(tmp[5]), float(tmp[6]), float(tmp[7])]
                dim = [float(tmp[8]), float(tmp[9]), float(tmp[10])]
                location = [float(tmp[11]), float(tmp[12]), float(tmp[13])]
                rotation_y = float(tmp[14])
                car_id = int(tmp[15])
                #box_3d = compute_box_3d(dim, location, rotation_y)
                #box_2d = project_to_image(box_3d, calib)
                #bbox = (np.min(box_2d[:,0]), np.min(box_2d[:,1]), np.max(box_2d[:,0]), np.max(box_2d[:,1]))

                if car_id in id_list:
                    txt="{} {} {} {} {} {} {} {} {:.4f} {:.4f} {:.4f} {:.4f} {:.4f} {:.4f} {} {}\n".format('Car', truncated, occluded, alpha, bbox[0], bbox[1], bbox[2], bbox[3], dim[0], dim[1],
                                        dim[2],location[0], location[1], location[2],  rotation,car_id)
                    f.write(txt)
                #f.write('\n')
            f.close()