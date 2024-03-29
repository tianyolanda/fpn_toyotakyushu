# --------------------------------------------------------
# Tensorflow Faster R-CNN
# Licensed under The MIT License [see LICENSE for details]
# Written by Jiasen Lu, Jianwei Yang, based on code from Ross Girshick
# --------------------------------------------------------
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import _init_paths
import os
import sys
import numpy as np
import argparse
import pprint

import time
import cv2
import pickle
import torch
from torch.autograd import Variable
import torch.nn as nn
import torch.optim as optim
import torchvision.transforms as transforms
import torchvision.datasets as dset
from PIL import Image
from roi_data_layer.roidb import combined_roidb
from roi_data_layer.roibatchLoader import roibatchLoader
from model.utils.config import cfg, cfg_from_file, cfg_from_list, get_output_dir
from model.rpn.rpn_fpn import _RPN_FPN
from model.rpn.bbox_transform import clip_boxes
from model.nms.nms_wrapper import nms, soft_nms
from model.rpn.bbox_transform import bbox_transform_inv
from model.utils.net_utils import save_net, load_net, vis_detections
from model.utils.blob import im_list_to_blob
from model.fpn.resnet import resnet
from scipy.misc import imread

import pdb

def parse_args():
  """
  Parse input arguments
  """
  parser = argparse.ArgumentParser(description='demo a fpn network')
  
  parser.add_argument('--dataset', dest='dataset',
                      help='training dataset',
                      default='pascal_voc_0819', type=str)
  parser.add_argument('--video', dest='video',
                      help='video name',
                      default='raw_video20190728-wrodet-array.avi', type=str)                      
  parser.add_argument('--cfg', dest='cfg_file',
                      help='optional config file',
                      default='cfgs/res101.yml', type=str)
  parser.add_argument('--exp_name', dest='exp_name',
                      help='exp_name',
                      default='exp_name', type=str)                    
  parser.add_argument('--imdb', dest='imdb_name',
                      help='dataset to train on',
                      default='voc_2007_trainval', type=str)
  parser.add_argument('--imdbval', dest='imdbval_name',
                      help='dataset to validate on',
                      default='voc_2007_test', type=str)
  parser.add_argument('--net', dest='net',
                      help='res50, res101, res152',
                      default='res101', type=str)
  parser.add_argument('--vis', dest='vis',
                      help='visualization mode',
                      action='store_true')
  parser.add_argument('--set', dest='set_cfgs',
                      help='set config keys', default=None,
                      nargs=argparse.REMAINDER)
  parser.add_argument('--load_dir', dest='load_dir',
                      help='directory to load models', default="/home/toyota/download/FPN_Pytorch-master/weights",
                      nargs=argparse.REMAINDER)
  parser.add_argument('--image_dir', dest='image_dir',
                      help='directory to load images', default="/home/toyota/文档",
                      type=str)  
  parser.add_argument('--cuda', dest='cuda',
                      help='whether use CUDA',
                      action='store_true')                     
  parser.add_argument('--ngpu', dest='ngpu',
                      help='number of gpu',
                      default=1, type=int)
  parser.add_argument('--parallel_type', dest='parallel_type',
                      help='which part of model to parallel, 0: all, 1: model before roi pooling',
                      default=0, type=int)
  parser.add_argument('--checksession', dest='checksession',
                      help='checksession to load model',
                      default=1, type=int)
  parser.add_argument('--checkepoch', dest='checkepoch',
                      help='checkepoch to load network',
                      default=9, type=int)
  parser.add_argument('--checkpoint', dest='checkpoint',
                      help='checkpoint to load network',
                      default=18647, type=int)
  parser.add_argument('--webcam_num', dest='webcam_num',
                      help='webcam ID number',
                      default=1, type=int)
  parser.add_argument('--cag', dest='class_agnostic',
                      help='whether perform class_agnostic bbox regression',
                      action='store_true')
  args = parser.parse_args()
  return args
try:
    xrange  # Python 2
except NameError:
    xrange = range  # Python 3
lr = cfg.TRAIN.LEARNING_RATE
momentum = cfg.TRAIN.MOMENTUM
weight_decay = cfg.TRAIN.WEIGHT_DECAY

def _get_image_blob(im):
  """Converts an image into a network input.
  Arguments:
    im (ndarray): a color image in BGR order
  Returns:
    blob (ndarray): a data blob holding an image pyramid
    im_scale_factors (list): list of image scales (relative to im) used
      in the image pyramid
  """
  im_orig = im.astype(np.float32, copy=True)  
  im_orig -= cfg.PIXEL_MEANS

  im_shape = im_orig.shape
  im_size_min = np.min(im_shape[0:2])
  im_size_max = np.max(im_shape[0:2])

  processed_ims = []
  im_scale_factors = []

  for target_size in cfg.TEST.SCALES:
    im_scale = float(target_size) / float(im_size_min)
    # Prevent the biggest axis from being more than MAX_SIZE
    if np.round(im_scale * im_size_max) > cfg.TEST.MAX_SIZE:
      im_scale = float(cfg.TEST.MAX_SIZE) / float(im_size_max)
    im = cv2.resize(im_orig, None, None, fx=im_scale, fy=im_scale,
            interpolation=cv2.INTER_LINEAR)
    im_scale_factors.append(im_scale)
    processed_ims.append(im)

  # Create a blob to hold the input images
  blob = im_list_to_blob(processed_ims)

  return blob, np.array(im_scale_factors)

if __name__ == '__main__':

  args = parse_args()

  print('Called with args:')
  print(args)

  if args.cfg_file is not None:
    cfg_from_file(args.cfg_file)
  if args.set_cfgs is not None:
    cfg_from_list(args.set_cfgs)

  cfg.USE_GPU_NMS = args.cuda

  print('Using config:')
  pprint.pprint(cfg)
  np.random.seed(cfg.RNG_SEED)

  # train set
  # -- Note: Use validation set and disable the flipped to enable faster loading.

  
  # input_dir = "/home/toyota/download/FPN_Pytorch-master/weights/res101/pascal_voc_0819/08010719"
  input_dir = args.load_dir + "/" + args.net + "/" + args.dataset + "/" + args.exp_name
  print(input_dir)
  if not os.path.exists(input_dir):
    raise Exception('There is no input directory for loading network')
  load_name = os.path.join(input_dir,
    'fpn_{}_{}_{}.pth'.format(args.checksession, args.checkepoch, args.checkpoint))

  #classes = np.asarray(['__background__',  # always index 0
    #                'aeroplane', 'bicycle', 'bird', 'boat',
    #               'bus', 'car', 'cat', 'cow','dog', 'horse',
      #              'motorbike', 'person','sheep', 'train',
      #             'umbrellaman', 'cone'])
  classes = np.asarray(['__background__',  # always index 0
                        'car','person','bicycle','cone']) 
  if args.net == 'res101':
      fpn = resnet(classes, 101, pretrained=False,class_agnostic = args.class_agnostic)
  elif args.net == 'res50':
      fpn = resnet(classes, 50, pretrained=False)
  elif args.net == 'res152':
      fpn = resnet(classes, 152, pretrained=False)
  else:
      print("network is not defined")
    #  pdb.set_trace()

  fpn.create_architecture()

  print("load checkpoint %s" % (load_name))
  if args.cuda > 0:
    checkpoint = torch.load(load_name)
  
  checkpoint = torch.load(load_name)
  fpn.load_state_dict(checkpoint['model'])
  if 'pooling_mode' in checkpoint.keys():
    cfg.POOLING_MODE = checkpoint['pooling_mode']
  print('load model successfully!')

  # pdb.set_trace()

  print("load checkpoint %s" % (load_name))

  # initilize the tensor holder here.
  im_data = torch.FloatTensor(1)
  im_info = torch.FloatTensor(1)
  num_boxes = torch.LongTensor(1)
  gt_boxes = torch.FloatTensor(1)

  # ship to cuda
  if args.cuda > 0:
    im_data = im_data.cuda()
    im_info = im_info.cuda()
    num_boxes = num_boxes.cuda()
    gt_boxes = gt_boxes.cuda()

  # make variable
  with torch.no_grad():
    im_data = Variable(im_data)
    im_info = Variable(im_info)
    num_boxes = Variable(num_boxes)
    gt_boxes = Variable(gt_boxes)

  if args.cuda > 0:
    cfg.CUDA = True

  if args.cuda > 0:
    fpn.cuda()

  fpn.eval()  # To do the function/calculate of fpn string

  start = time.time()
  max_per_image = 100
  thresh = 0.05
  vis = True
  webcam_num = args.webcam_num
  # Set up webcam or get image directories
  if webcam_num >= 0 :
    #cap = cv2.VideoCapture(webcam_num)
    #cap = cv2.VideoCapture('/home/toyota/download/FPN_Pytorch-master-newdata/raw_video_20190324_data.avi')
    video_dir = '/home/toyota/download/FPN_Pytorch-master'
    video_path = video_dir + '/' + args.video
    cap = cv2.VideoCapture(video_path)

    num_images = 0
  else:
    imglist = os.listdir(args.image_dir)
    num_images = len(imglist)

  print('Loaded Photo: {} images.'.format(num_images))


  while (num_images >= 0):
        total_tic = time.time()
        if webcam_num == -1:
          num_images -= 1

        # Get image from the webcam
        if webcam_num >= 0:
          if not cap.isOpened():
            raise RuntimeError("Webcam could not open. Please check connection.")
          ret, frame = cap.read()
          im_in = np.array(frame)
        # Load the demo image
        else:
          im_file = os.path.join(args.image_dir, imglist[num_images])
          # im = cv2.imread(im_file)
          im_in = np.array(imread(im_file))
        if len(im_in.shape) == 2:
          im_in = im_in[:,:,np.newaxis]
          im_in = np.concatenate((im_in,im_in,im_in), axis=2)
        # rgb -> bgr
        im = im_in[:,:,::-1]

        blobs, im_scales = _get_image_blob(im)
        assert len(im_scales) == 1, "Only single-image batch implemented"
        im_blob = blobs
        im_info_np = np.array([[im_blob.shape[1], im_blob.shape[2], im_scales[0]]], dtype=np.float32)

        im_data_pt = torch.from_numpy(im_blob)
        im_data_pt = im_data_pt.permute(0, 3, 1, 2)
        im_info_pt = torch.from_numpy(im_info_np)

        im_data.data.resize_(im_data_pt.size()).copy_(im_data_pt)
        im_info.data.resize_(im_info_pt.size()).copy_(im_info_pt)
        gt_boxes.data.resize_(1, 1, 5).zero_()
        num_boxes.data.resize_(1).zero_()

        # pdb.set_trace()

        det_tic = time.time()
        rois, cls_prob, bbox_pred, \
            _, _, _, _, _=fpn(im_data, im_info, gt_boxes, num_boxes)

        scores = cls_prob.data
        boxes = rois.data[:, :, 1:5]
        #print(cfg.TEST.BBOX_REG)

        if cfg.TEST.BBOX_REG:
            # Apply bounding-box regression deltas
            box_deltas = bbox_pred.data
            #print(cfg.TRAIN.BBOX_NORMALIZE_TARGETS_PRECOMPUTED)
            if cfg.TRAIN.BBOX_NORMALIZE_TARGETS_PRECOMPUTED:
            # Optionally normalize targets by a precomputed mean and stdev
              if args.class_agnostic:
                  if args.cuda > 0:
                      box_deltas = box_deltas.view(-1, 4) * torch.FloatTensor(cfg.TRAIN.BBOX_NORMALIZE_STDS).cuda() \
                                + torch.FloatTensor(cfg.TRAIN.BBOX_NORMALIZE_MEANS).cuda()
                  else:
                      box_deltas = box_deltas.view(-1, 4) * torch.FloatTensor(cfg.TRAIN.BBOX_NORMALIZE_STDS) \
                                + torch.FloatTensor(cfg.TRAIN.BBOX_NORMALIZE_MEANS)

                  box_deltas = box_deltas.view(1, -1, 4)
              else:
                  if args.cuda > 0:
                      box_deltas = box_deltas.view(-1, 4) * torch.FloatTensor(cfg.TRAIN.BBOX_NORMALIZE_STDS).cuda() \
                                + torch.FloatTensor(cfg.TRAIN.BBOX_NORMALIZE_MEANS).cuda()
                  else:
                      box_deltas = box_deltas.view(-1, 4) * torch.FloatTensor(cfg.TRAIN.BBOX_NORMALIZE_STDS) \
                                + torch.FloatTensor(cfg.TRAIN.BBOX_NORMALIZE_MEANS)
                  box_deltas = box_deltas.view(1, -1, 4 * len(classes))
            pred_boxes = bbox_transform_inv(boxes, box_deltas, 1)
            pred_boxes = clip_boxes(pred_boxes, im_info.data, 1)
        else:
            # Simply repeat the boxes, once for each class
            pred_boxes = np.tile(boxes, (1, scores.shape[1]))
            pred_boxes = boxes
        pred_boxes /= im_scales[0]  #框乱飞源头

        scores = scores.squeeze()
        pred_boxes = pred_boxes.squeeze()
        det_toc = time.time()
        detect_time = det_toc - det_tic
        misc_tic = time.time()

        if vis:
            #im = cv2.imread(imdb.image_path_at(i))
            im2show = np.copy(im)
        for j in xrange(1, len(classes)):
            # inds = np.where(scores[:, j] > thresh)[0]
            inds = torch.nonzero(scores[:,j]>thresh).view(-1)
            # if there is det
            if inds.numel() > 0:
              cls_scores = scores[:,j][inds]
              _, order = torch.sort(cls_scores, 0, True)
              cls_boxes = pred_boxes[inds][:, j * 4:(j + 1) * 4]

              # cls_scores = scores[inds, j]
              # cls_boxes = pred_boxes[inds, :]
              cls_dets = torch.cat((cls_boxes, cls_scores.unsqueeze(1)),1)
              cls_dets = cls_dets[order]
              keep = nms(cls_dets, cfg.TEST.NMS)
              # cls_dets = cls_dets[keep, :]
              cls_dets = cls_dets[keep.view(-1).long()]

              if vis:
                  # im2show = vis_detections(im2show, classes[j], cls_dets)
                  im2show = vis_detections(im2show, classes[j], cls_dets.cpu().numpy(), 0.7)

        misc_toc = time.time()
        nms_time = misc_toc - misc_tic

        if webcam_num == -1:
            sys.stdout.write('im_detect: {:d}/{:d} {:.3f}s {:.3f}s   \r' \
                            .format(num_images + 1, len(imglist), detect_time, nms_time))
            sys.stdout.flush()

        if vis and webcam_num == -1:
            # cv2.imshow('test', im2show)
            # cv2.waitKey(0)
            result_path = os.path.join(args.image_dir, imglist[num_images][:-4] + "_det.jpg")
            cv2.imwrite(result_path, im2show)
        else:
            im2showRGB = cv2.cvtColor(im2show, cv2.COLOR_BGR2RGB)
            cv2.imshow("frame", im2showRGB)
            total_toc = time.time()
            total_time = total_toc - total_tic
            frame_rate = 1 / total_time
            print('Frame rate:', frame_rate)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
  if webcam_num >= 0:
      cap.release()
      cv2.destroyAllWindows()