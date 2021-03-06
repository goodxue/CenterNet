import os
import time
import glob
import numpy as np
import argparse
from detection_evaluation.nuscenes_eval_core import NuScenesEval
from detection_evaluation.label_parser import LabelParser
import co_utils as cu

def parse_args():
    parser = argparse.ArgumentParser(description='arg parser')
    # parser.add_argument('--pred_labels', type=str, required=True,
    #                     help='Prediction labels data path')
    # parser.add_argument('--gt_labels', type=str, required=True,
    #                     help='Ground Truth labels data path')
    parser.add_argument('--format', type=str, default='class truncated occluded alpha bbox_xmin bbox_ymin bbox_xmax bbox_ymax h w l x y z r score')
    args = parser.parse_args()
    return args


def main():
    args = parse_args()
    NuScenesEval(args.pred_labels, args.gt_labels, args.format)


if __name__ == '__main__':
    args = parse_args()
    file_parsing = LabelParser(args.format)
    FUSE_NUM = 2

    pred_files_list = []
    dataset_path = '/home/ubuntu/xwp/datasets/multi_view_dataset/new' #数据集根目录
    gt_global_label_dir = '/home/ubuntu/xwp/datasets/multi_view_dataset/new/global_label_new' #全部gt的世界坐标label文件夹
    camset_path = [ os.path.join(dataset_path,"cam{}".format(cam_num),'label_test_trans') for cam_num in range(1,35)] #每一个相机的test txt文件夹
    #gtset_path = [ os.path.join(dataset_path,"cam{}".format(cam_num),'global_filtered') for cam_num in range(1,35)] #每一个相机的test txt文件夹
    gtset_path = [os.path.join(dataset_path,'global_label_new')]

    cam_test_list = [] #所有相机单独检测的世界坐标 len=34,len(cam_test_list[0])=100 type(cam_test_list[0]) =np.ndarray shape = N*9(score) / N*8(gt)
    cam_gt_list = []
    load_start_time = time.time()
    for i,pred_path in enumerate(camset_path):
        pred_file_list = glob.glob(pred_path + "/*")
        pred_file_list.sort()
        if len(pred_file_list) != 100:
            print(len(pred_file_list))
            raise RuntimeError("can\'t read 100 files in cam{}. check the prediction file!".format(i+1))
        frame_test_list = []
        for pred_fn in pred_file_list:
            predictions = file_parsing.parse_label(pred_fn, prediction=True)
            frame_test_list.append(predictions[:,1:])
        cam_test_list.append(frame_test_list)
    # test sample 加载完成

    # #加载gt
    # cam_gt_list = []
    # gt_file_list = glob.glob(gt_global_label_dir + "/*")
    # gt_file_list.sort()
    # for gt_fn in gt_file_list:
    #     if int(gt_fn[-10:-4]) < 901:
    #         continue
    #     gts = file_parsing.parse_label(gt_fn, prediction=False)
    #     cam_gt_list.append(gts[:,1:])
    # #
    for i,gt_path in enumerate(gtset_path):
        gt_file_list = glob.glob(gt_path + "/*")
        gt_file_list.sort()
        frame_gt_list = []
        for gt_fn in gt_file_list:
            if int(gt_fn[-10:-4]) < 901:
                continue
            gts = file_parsing.parse_label(gt_fn, prediction=False)
            frame_gt_list.append(gts[:,1:])
        cam_gt_list.append(frame_gt_list)

    load_time = time.time() - load_start_time
    print("load time: ",load_time)

    #遍历融合
    from sko import SA

    def func_co(x):
        x.sort()
        Eval = NuScenesEval('', '', args.format)
        fused_data = cu.matching_and_fusion(cam_test_list[x[0]],cam_test_list[x[1]])
        fused_gt = cu.filt_gt_labels_tuple(cam_gt_list[x[0]],cam_gt_list[x[1]])
        mAP_temp = Eval.my_evaluate(fused_data,fused_gt)
        return 1- mAP_temp
    
    #fused_gt = cu.filt_gt_labels_tuple(*cam_gt_list)
    fused_gt = cam_gt_list[0]
    from sklearn.cluster import DBSCAN
    dbscan = DBSCAN(eps = 1.6,min_samples=1)

    def fuse_constellation(x):
        #根据x的维度进行融合
        x.sort()
        size_n = x.shape[0]
        #fused_data = cam_test_list[x[0]]
        #gt_list = []
        #gt_list.append(cam_gt_list[main_cam])
        new_cam_test = []
        for i in x:
            new_cam_test.append(cam_test_list[i])
        fused_data = cu.matching_and_fusion_tuple(*new_cam_test,dbscan=dbscan)
        # for i in x[1:]:
        #     fused_data = cu.matching_and_fusion(fused_data,cam_test_list[i]) #融合
            #gt_list.append(cam_gt_list[i])
        #fused_gt = cu.filt_gt_labels_tuple(*gt_list)
        Eval = NuScenesEval('', '', args.format)
        #print(fused_data == cam_test_list[x[0]])
        mAP_temp = Eval.my_evaluate(fused_data,fused_gt)
        return 1- mAP_temp
    
    # fused_data = cu.matching_and_fusion(cam_test_list[7],cam_test_list[23])
    # fused_data = cu.matching_and_fusion(fused_data,cam_test_list[27])
    # Eval = NuScenesEval('', '', args.format)
    # mAP_temp = Eval.my_evaluate(fused_data,fused_gt)
    # print(mAP_temp)
    
    

    filt_start_time1 = time.time()
    #x0 = SA.get_new_constellation(np.array([0,1,2,3,4,5,6,7,8,9,10]))
    # x0 = np.arange(0,34)
    # #x0 = np.array([0])
    # print(1-fuse_constellation(x0))
    # #sa = SA.SA_CO(func=fuse_constellation, x0=x0, T_max=1, T_min=0.1*(max(len(x0),5)-1), L=40, max_stay_counter=10)
    # #sa = SA.SA_CO(func=fuse_constellation, x0=x0, T_max=1, T_min=0.1*(min(len(x0),5)-1), L=100, max_stay_counter=10)
    # best_x, best_y = sa.run()
    # print('best_x:', best_x, 'best_y', 1-best_y)

    for i in range(9,28):
        filt_start_time = time.time()
        x0 = SA.get_new_constellation(np.arange(0,i))
        sa = SA.SA_CO(func=fuse_constellation, x0=x0, T_max=1, T_min=0.1*(min(len(x0),6)-1), L=30*(min(len(x0),16)-1), max_stay_counter=5)
        best_x, best_y = sa.run()
        print('best_x:', best_x, 'best_y', 1-best_y)
        filt_time = time.time() - filt_start_time
        print('finished!,used {} s'.format(filt_time))

    
    # filt_start_time = time.time()
    # ret = cu.filt_gt_labels(cam_gt_list[0],cam_gt_list[1])
    # filt_time = time.time() - filt_start_time
    # print("filt gt for 1 iter, time: ",filt_time)

    # max_map = 0
    # max_i,max_j = 0,0
    # for i in range(34):
    #     for j in range(i+1,34):
    #         fused_data = cu.matching_and_fusion(cam_test_list[i],cam_test_list[j]) #融合
    #         for k in range(j+1,34):
    #             Eval = NuScenesEval('', '', args.format)
    #             fused_data = cu.matching_and_fusion(fused_data,cam_test_list[k]) #融合
    #             fused_gt = cu.filt_gt_labels_tuple(cam_gt_list[i],cam_gt_list[j],cam_gt_list[k])
    #             #评估
    #             mAP_temp = Eval.my_evaluate(fused_data,fused_gt)
    #             if mAP_temp > max_map:
    #                 max_map = mAP_temp
    #                 max_i,max_j = i,j
    #                 print('temp max mAP: {}..........   time: ##   i: {}   j: {}  k:{} '.format(max_map,i,j,k))
    #             #print(mAP_temp)
    
    filt_time1 = time.time() - filt_start_time1
    print('finished!,used {} s'.format(filt_time1))


    

# 1.将所有test读取列表中
#循环2、3
# 2.融合
# 3.评估，迭代