# Author: Xinshuo Weng
# email: xinshuo.weng@gmail.com

import os, numpy as np, sys, cv2
from PIL import Image
sys.path.append('/home/ubuntu/xwp/Xinshuo_pyToolbox')
from xinshuo_io import is_path_exists, mkdir_if_missing, load_list_from_folder, fileparts
from xinshuo_visualization import random_colors
from AB3DMOT_libs.kitti_utils import read_label, compute_box_3d, draw_projected_box3d, Calibration
import carla_ros.utils as cu
import json

max_color = 30
colors = random_colors(max_color)       # Generate random colors
type_whitelist = ['Car', 'Pedestrian', 'Cyclist']
score_threshold = -10000
width = 1242
height = 374
seq_list = ['0000', '0003']
def read_clib(calib_path):
    f = open(calib_path, 'r')
    for i, line in enumerate(f):
        if i == 0:
            calib = np.array(line[:-1].split(' ')[1:], dtype=np.float32)
            calib = calib.reshape(3, 3)
            return calib

def vis(cam_transform, data_root, result_root):
	def show_image_with_boxes(img, objects_res, object_gt, calib, save_path, height_threshold=0):
		img2 = np.copy(img) 

		for obj in objects_res:
			box3d_pts_2d, _ = compute_box_3d(obj, calib.P)
			color_tmp = tuple([int(tmp * 255) for tmp in colors[obj.id % max_color]])
			img2 = draw_projected_box3d(img2, box3d_pts_2d, color=color_tmp)
			text = 'ID: %d' % obj.id
			if box3d_pts_2d is not None:
				img2 = cv2.putText(img2, text, (int(box3d_pts_2d[4, 0]), int(box3d_pts_2d[4, 1]) - 8), cv2.FONT_HERSHEY_TRIPLEX, 0.5, color=color_tmp) 
		
		img = Image.fromarray(img2)
		img = img.resize((width, height))
		img = img.convert('RGB')
		img.save(save_path)
	
	for seq in seq_list:
		#image_dir = os.path.join(data_root, 'image_02/%s' % seq)
		#calib_file = os.path.join(data_root, 'calib/%s.txt' % seq)
		#result_dir = os.path.join(result_root, '%s/trk_withid/%s' % (result_sha, seq))
		#save_3d_bbox_dir = os.path.join(result_dir, '../../trk_image_vis/%s' % seq); mkdir_if_missing(save_3d_bbox_dir)
		image_dir = '/home/ubuntu/xwp/datasets/multi_view_dataset/new/cam_sample/image_2'
		result_dir = '/home/ubuntu/xwp/datasets/multi_view_dataset/new/fuse_test/cam9+cam21/tracking_results/trk_withid/0000'
		calib_file = '/home/ubuntu/xwp/datasets/multi_view_dataset/346/calib/000000.txt'
		save_3d_bbox_dir = '/home/ubuntu/xwp/datasets/multi_view_dataset/new/fuse_test/cam9+cam21/trk_image_vis'
		mkdir_if_missing(save_3d_bbox_dir)

		# load the list
		images_list, num_images = load_list_from_folder(image_dir)
		print('number of images to visualize is %d' % num_images)
		cam_id = 'cam9'
		start_count = 8945
		end_count = 8950
		min_index = 8900
		for count in range(start_count, end_count):
			image_tmp = images_list[count]
			if not is_path_exists(image_tmp): 
				count += 1
				continue
			image_index = int(fileparts(image_tmp)[1])
			image_tmp = np.array(Image.open(image_tmp))
			img_height, img_width, img_channel = image_tmp.shape

			result_tmp = os.path.join(result_dir, '%06d.txt'%(image_index-min_index))		# load the result
			if not is_path_exists(result_tmp): object_res = []
			else: object_res = read_label(result_tmp)
			print('processing index: %d, %d/%d, results from %s' % (image_index, count+1, num_images, result_tmp))
			calib_tmp = Calibration(calib_file)			# load the calibration

			object_res_filtered = []
			cam_trans = cam_transform[cam_id]
			for object_tmp in object_res:
				if object_tmp.type not in type_whitelist: continue
				if hasattr(object_tmp, 'score'):
					if object_tmp.score < score_threshold: continue
				center = object_tmp.t
				#transform
				cord_p = np.zeros((1,4))
				cord_p[0][0] = object_tmp.t[2]
				cord_p[0][1] = object_tmp.t[0]
				cord_p[0][2] = -object_tmp.t[1]
				cord_p[0][3] = 1
				rotation_y = object_tmp.ry * 180 /np.pi
				cam_matrix = cu.ClientSideBoundingBoxes.get_matrix(cam_trans)
				cam_to_world = np.dot(cam_matrix,np.transpose(cord_p))
				ry_cam2world = cu.ry_filter_a(rotation_y - 90 + cam_trans.rotation.yaw ) * np.pi / 180
				object_tmp.t = [cam_to_world[1][0],-cam_to_world[2][0],cam_to_world[0][0]]
				object_tmp.ry = cu.ry_filter(ry_cam2world)
				#end
				object_res_filtered.append(object_tmp)

			num_instances = len(object_res_filtered)
			save_image_with_3dbbox_gt_path = os.path.join(save_3d_bbox_dir, '%06d.jpg' % (image_index))
			show_image_with_boxes(image_tmp, object_res_filtered, [], calib_tmp, save_path=save_image_with_3dbbox_gt_path)
			print('number of objects to plot is %d' % (num_instances))
			count += 1

if __name__ == "__main__":
	# if len(sys.argv) != 2:
	# 	print('Usage: python visualization.py result_sha(e.g., pointrcnn_Car_test_thres)')
	# 	sys.exit(1)

	# result_root = './results'
	# result_sha = sys.argv[1]
	# if 'val' in result_sha: data_root = './data/KITTI/resources/training'
	# elif 'test' in result_sha: data_root = './data/KITTI/resources/testing'
	# else:
	# 	print("wrong split!")
	# 	sys.exit(1)
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
			point = cu.Transform(location=cu.Location(x=spawn_point.pop("x"), y=-spawn_point.pop("y"), z=spawn_point.pop("z")),
				rotation=cu.Rotation(pitch=-spawn_point.pop("pitch", 0.0), yaw=-spawn_point.pop("yaw", 0.0), roll=spawn_point.pop("roll", 0.0)))
			cam_transform[sensor_id] = point

	vis(cam_transform, 0, 0)