# Author: Xinshuo Weng
# email: xinshuo.weng@gmail.com

import numpy as np, copy
from numba import jit
from scipy.spatial import ConvexHull
from scipy.optimize import linear_sum_assignment
from carla_ros.utils import CamVehicle
import random

#@jit          
def poly_area(x,y):
	""" Ref: http://stackoverflow.com/questions/24467972/calculate-area-of-polygon-given-x-y-coordinates """
	return 0.5*np.abs(np.dot(x,np.roll(y,1))-np.dot(y,np.roll(x,1)))

#@jit         
def box3d_vol(corners):
	''' corners: (8,3) no assumption on axis direction '''
	a = np.sqrt(np.sum((corners[0,:] - corners[1,:])**2))
	b = np.sqrt(np.sum((corners[1,:] - corners[2,:])**2))
	c = np.sqrt(np.sum((corners[0,:] - corners[4,:])**2))
	return a*b*c

#@jit          
def convex_hull_intersection(p1, p2):
	""" Compute area of two convex hull's intersection area.
		p1,p2 are a list of (x,y) tuples of hull vertices.
		return a list of (x,y) for the intersection and its volume
	"""
	inter_p = polygon_clip(p1,p2)
	if inter_p is not None:
		hull_inter = ConvexHull(inter_p)
		return inter_p, hull_inter.volume
	else:
		return None, 0.0  

def polygon_clip(subjectPolygon, clipPolygon):
	""" Clip a polygon with another polygon.
	Ref: https://rosettacode.org/wiki/Sutherland-Hodgman_polygon_clipping#Python
	Args:
		subjectPolygon: a list of (x,y) 2d points, any polygon.
		clipPolygon: a list of (x,y) 2d points, has to be *convex*
	Note:
		**points have to be counter-clockwise ordered**
	Return:
		a list of (x,y) vertex point for the intersection polygon.
	"""
	def inside(p):
		return (cp2[0] - cp1[0]) * (p[1] - cp1[1]) > (cp2[1] - cp1[1]) * (p[0] - cp1[0])
 
	def computeIntersection():
		dc = [cp1[0] - cp2[0], cp1[1] - cp2[1]]
		dp = [s[0] - e[0], s[1] - e[1]]
		n1 = cp1[0] * cp2[1] - cp1[1] * cp2[0]
		n2 = s[0] * e[1] - s[1] * e[0] 
		n3 = 1.0 / (dc[0] * dp[1] - dc[1] * dp[0])
		return [(n1 * dp[0] - n2 * dc[0]) * n3, (n1 * dp[1] - n2 * dc[1]) * n3]
 
	outputList = subjectPolygon
	cp1 = clipPolygon[-1]
 
	for clipVertex in clipPolygon:
		cp2 = clipVertex
		inputList = outputList
		outputList = []
		s = inputList[-1]
 
		for subjectVertex in inputList:
			e = subjectVertex
			if inside(e):
				if not inside(s): outputList.append(computeIntersection())
				outputList.append(e)
			elif inside(s): outputList.append(computeIntersection())
			s = e
		cp1 = cp2
		if len(outputList) == 0: return None
	return (outputList)
def vehicle_mean_fusion(v1,v2):
	return CamVehicle((v1.x+v2.x)/2,(v1.y+v2.y)/2,(v1.z+v2.z)/2,(v1.height+v2.height)/2,(v1.width+v2.width)/2,(v1.length+v2.length)/2,(v1.rotation_y+v2.rotation_y)/2,cid=v1.id,score=(v1.score+v2.score)/2)


def box3d_matching(box3d1,box3d2,iou_threshold=0.01,fusion=None):
	'''
	Input:
		box3d1: Nx8x3
		box3d2: Nx8x3 (in the same camera cordinate)
		iou_threshold: float
	Output:
		fusedboxes: ndarray((box3d1_index,box3d2_index)) : Mx1x2
	'''
	ret = []
	iou_matrix = np.zeros((len(box3d1), len(box3d2)), dtype=np.float32)
	for i, box1 in enumerate(box3d1):
		for j, box2 in enumerate(box3d2):
			iou_matrix[i,j] = iou3d(box1,box2)[0]
			#iou_matrix[i,j] = greedy_3d(box1,box2)
	
	row_ind, col_ind = linear_sum_assignment(-iou_matrix)      # hougarian algorithm
	matched_indices = np.stack((row_ind, col_ind), axis=1)

	unmatched1 = []
	unmatched2 = []
	for d, det in enumerate(box3d1):
		if (d not in matched_indices[:, 0]): unmatched1.append(det)
	
	for d, det in enumerate(box3d2):
		if (d not in matched_indices[:, 1]): unmatched2.append(det)

	
	for m in matched_indices:
		if (iou_matrix[m[0], m[1]] < iou_threshold):
			ret.append(box3d1[m[0]])
			ret.append(box3d2[m[1]])
		else: ret.append(random.choice([box3d1[m[0]],box3d2[m[1]]]) if fusion == None else fusion(box3d1[m[0]],box3d2[m[1]]))

	return ret + unmatched1 + unmatched2

def vehicle3d_matching(v1,v2,iou_threshold=0.01,fusion=vehicle_mean_fusion):
	'''
	Input:
		box3d1: Nx8x3
		box3d2: Nx8x3 (in the same camera cordinate)
		iou_threshold: float
	Output:
		fusedboxes: ndarray((box3d1_index,box3d2_index)) : Mx1x2
	'''
	box3d1 = [v.compute_box_3d() for v in v1]
	box3d2 = [v.compute_box_3d() for v in v2]
	ret = []
	iou_matrix = np.zeros((len(box3d1), len(box3d2)), dtype=np.float32)
	for i, box1 in enumerate(box3d1):
		for j, box2 in enumerate(box3d2):
			iou_matrix[i,j] = iou3d(box1,box2)[0]
	
	row_ind, col_ind = linear_sum_assignment(-iou_matrix)      # hougarian algorithm
	matched_indices = np.stack((row_ind, col_ind), axis=1)

	unmatched1 = []
	unmatched2 = []
	for d, det in enumerate(v1):
		if (d not in matched_indices[:, 0]): unmatched1.append(det)
	
	for d, det in enumerate(v2):
		if (d not in matched_indices[:, 1]): unmatched2.append(det)

	
	for m in matched_indices:
		if (iou_matrix[m[0], m[1]] < iou_threshold):
			ret.append(v1[m[0]])
			ret.append(v2[m[1]])
		else: ret.append(random.choice([v1[m[0]],v2[m[1]]]) if fusion == None else fusion(v1[m[0]],v2[m[1]]))

	return ret + unmatched1 + unmatched2

def box_mean_fusion(box3d1,box3d2):
	return (box3d1+box3d2)/2


def box3d_matching_index(box3d1,box3d2,iou_threshold=0.01,fusion=None):
	'''
	Input:
		box3d1: Nx8x3
		box3d2: Nx8x3 (in the same camera cordinate)
		iou_threshold: float
	Output:
		fusedboxes: ndarray((box3d1_index,box3d2_index)) : Mx1x2
	'''
	ret = []
	iou_matrix = np.zeros((len(box3d1), len(box3d2)), dtype=np.float32)
	for i, box1 in enumerate(box3d1):
		for j, box2 in enumerate(box3d2):
			iou_matrix[i,j] = iou3d(box1,box2)[0]
	
	row_ind, col_ind = linear_sum_assignment(-iou_matrix)      # hougarian algorithm
	matched_indices = np.stack((row_ind, col_ind), axis=1)

	unmatched1 = []
	unmatched2 = []
	for d, det in enumerate(box3d1):
		if (d not in matched_indices[:, 0]): unmatched1.append(d)
	
	for d, det in enumerate(box3d2):
		if (d not in matched_indices[:, 1]): unmatched2.append(d)

	
	for m in matched_indices:
		if (iou_matrix[m[0], m[1]] < iou_threshold):
			unmatched1.append(m[0])
			unmatched2.append(m[1])
		else: ret.append(m)
	
	if (len(ret) == 0): 
		ret = np.empty((0, 2),dtype=int)
	else: ret = np.concatenate(ret, axis=0)

	return ret , np.array(unmatched1) , np.array(unmatched2)


def iou3d(corners1, corners2):
	''' Compute 3D bounding box IoU, only working for object parallel to ground
	Input:
	    corners1: numpy array (8,3), assume up direction is negative Y
	    corners2: numpy array (8,3), assume up direction is negative Y
	Output:
	    iou: 3D bounding box IoU
	    iou_2d: bird's eye view 2D bounding box IoU
	todo (rqi): add more description on corner points' orders.
	'''
	# corner points are in counter clockwise order
	rect1 = [(corners1[i,0], corners1[i,2]) for i in range(3,-1,-1)]
	rect2 = [(corners2[i,0], corners2[i,2]) for i in range(3,-1,-1)] 
	area1 = poly_area(np.array(rect1)[:,0], np.array(rect1)[:,1])
	area2 = poly_area(np.array(rect2)[:,0], np.array(rect2)[:,1])

	# inter_area = shapely_polygon_intersection(rect1, rect2)
	_, inter_area = convex_hull_intersection(rect1, rect2)

	# try:
	#   _, inter_area = convex_hull_intersection(rect1, rect2)
	# except ValueError:
	#   inter_area = 0
	# except scipy.spatial.qhull.QhullError:
	#   inter_area = 0

	iou_2d = inter_area/(area1+area2-inter_area)
	ymax = min(corners1[0,1], corners2[0,1])
	ymin = max(corners1[4,1], corners2[4,1])
	inter_vol = inter_area * max(0.0, ymax-ymin)
	vol1 = box3d_vol(corners1)
	vol2 = box3d_vol(corners2)
	iou = inter_vol / (vol1 + vol2 - inter_vol)
	return iou, iou_2d

def box3d_matching_greedy(box3d1,box3d2,iou_threshold=0.01,fusion=None):
	'''
	Input:
		box3d1: Nx8x3
		box3d2: Nx8x3 (in the same camera cordinate)
		iou_threshold: float
	Output:
		fusedboxes: ndarray((box3d1_index,box3d2_index)) : Mx1x2
	'''
	ret = []
	iou_matrix = np.zeros((len(box3d1), len(box3d2)), dtype=np.float32)
	for i, box1 in enumerate(box3d1):
		for j, box2 in enumerate(box3d2):
			iou_matrix[i,j] = iou3d(box1,box2)[0]
			#iou_matrix[i,j] = greedy_3d(box1,box2)
	
	row_ind, col_ind = linear_sum_assignment(-iou_matrix)      # hougarian algorithm
	matched_indices = np.stack((row_ind, col_ind), axis=1)

	unmatched1 = []
	unmatched2 = []
	for d, det in enumerate(box3d1):
		if (d not in matched_indices[:, 0]): unmatched1.append(det)
	
	for d, det in enumerate(box3d2):
		if (d not in matched_indices[:, 1]): unmatched2.append(det)

	
	for m in matched_indices:
		if (iou_matrix[m[0], m[1]] < iou_threshold):
			ret.append(box3d1[m[0]])
			ret.append(box3d2[m[1]])
		else: ret.append(random.choice([box3d1[m[0]],box3d2[m[1]]]) if fusion == None else fusion(box3d1[m[0]],box3d2[m[1]]))

	return ret + unmatched1 + unmatched2

def greedy_3d(corners1,corners2):
	x1 = (corners1[0][0] + corners1[2][0])/2
	x2 = (corners2[0][0] + corners2[2][0])/2
	z1 = (corners1[0][2] + corners1[2][2])/2
	z2 = (corners2[0][2] + corners2[2][2])/2
	
	return (x1 - x2)**2 + (z1 - z2)**2

#@jit         
def roty(t):
	''' Rotation about the y-axis. '''
	c = np.cos(t)
	s = np.sin(t)
	return np.array([[c,  0,  s],
                     [0,  1,  0],
                     [-s, 0,  c]])
     
def convert_3dbox_to_8corner(bbox3d_input):
	''' Takes an object's 3D box with the representation of [x,y,z,theta,l,w,h] and 
	    convert it to the 8 corners of the 3D box
	    
	    Returns:
	        corners_3d: (8,3) array in in rect camera coord
	'''
	# compute rotational matrix around yaw axis
	bbox3d = copy.copy(bbox3d_input)

	R = roty(bbox3d[3])    

	# 3d bounding box dimensions
	l = bbox3d[4]
	w = bbox3d[5]
	h = bbox3d[6]

	# 3d bounding box corners
	x_corners = [l/2,l/2,-l/2,-l/2,l/2,l/2,-l/2,-l/2]
	y_corners = [0,0,0,0,-h,-h,-h,-h]
	z_corners = [w/2,-w/2,-w/2,w/2,w/2,-w/2,-w/2,w/2]

	# rotate and translate 3d bounding box
	corners_3d = np.dot(R, np.vstack([x_corners,y_corners,z_corners]))
	#print corners_3d.shape
	corners_3d[0,:] = corners_3d[0,:] + bbox3d[0]
	corners_3d[1,:] = corners_3d[1,:] + bbox3d[1]
	corners_3d[2,:] = corners_3d[2,:] + bbox3d[2]

	return np.transpose(corners_3d)



if __name__ == "__main__":
	import time
	box_term1 = [3,4,5,0,2,2,3]
	box_term2 = [3,4,6,0,2,2,3]
	start = time.time()
	box3d1 = convert_3dbox_to_8corner(box_term1)
	box3d2 = convert_3dbox_to_8corner(box_term2)
	end = time.time()
	print("1   :",iou3d(box3d1,box3d1))
	print("3/4 :",iou3d(box3d1,box3d2))
	print("time:",end-start)