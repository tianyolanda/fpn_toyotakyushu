# fpn-pytorch1.0
## Introduction
This repo mainly based on [jwyang/fpn.pytorch](https://github.com/jwyang/fpn.pytorch) and [jwyang/faster-rcnn.pytorch](https://github.com/jwyang/faster-rcnn.pytorch/tree/pytorch-1.0). I combine some code to let it ables to work in pytorch1.0 framework and get a more 75.8mAP(higher than faster rcnn & fpn0.4 repo) when training pascal voc 2007. 

Iherent from them, this repo support multi GPU training, GPU version NMS and ROI Align pooling. Thanks a lot for jwyang. More usage introduction can be found in the upper two repo.

# Demo Result 
![](https://github.com/tianyolanda/fpn-pytorch1.0/blob/master/images/000002_det.jpg)
![](https://github.com/tianyolanda/fpn-pytorch1.0/blob/master/images/000013_det.jpg)
![](https://github.com/tianyolanda/fpn-pytorch1.0/blob/master/images/000020_det.jpg)
![](https://github.com/tianyolanda/fpn-pytorch1.0/blob/master/images/2007_000243_det.jpg) 
![](https://github.com/tianyolanda/fpn-pytorch1.0/blob/master/images/2007_000061_det.jpg)
![](https://github.com/tianyolanda/fpn-pytorch1.0/blob/master/images/2007_000175_det.jpg)
![](https://github.com/tianyolanda/fpn-pytorch1.0/blob/master/images/2011_005266_det.jpg)
![](https://github.com/tianyolanda/fpn-pytorch1.0/blob/master/images/2011_005252_det.jpg)

# Benchmarking

I benchmark this code thoroughly on pascal voc2007 (voc0712 is on the way). Below are the results:

1). PASCAL VOC 2007 (Train/Test: 07trainval/07test, scale=600, ROI Align， 

model    | GPUs | Batch Size | lr        | lr_decay | max_epoch     |  Speed/epoch | Memory/GPU | mAP 
---------|-----------|----|-----------|-----|-----|-------|--------|--------
Res-101    | 1  RTX 2080  | 1 | 1e-3 | 5  | 12  |  \ | \ | 75.8 


## Preparation

clone the code

```
git clone https://github.com/tianyolanda/fpn-pytorch1.0.git
```

Then, create a folder:

```
cd fpn-pytorch1.0 
mkdir data
mkdir logs
```

### prerequisites
The environment I run this code is under:
- Python 3.7
- Pytorch 1.0
- CUDA 10.0

visdom are support for visilization of loss curve

### Data Preparation
* VOC2007 or VOC07+12: Please follow the instructions in [py-faster-rcnn](https://github.com/rbgirshick/py-faster-rcnn#beyond-the-demo-installation-for-training-and-testing-models) to prepare VOC datasets. Actually, you can refer to any others. After downloading the data, creat softlinks in the folder data/.

* COCO dataset is not supported in this repo yet

### Pretrained Model
Pretrained Model we need for FPN is ResNet101.

Download from here [jwyang/faster-rcnn.pytorch](https://github.com/jwyang/faster-rcnn.pytorch#pretrained-model)

Download it and put it into the data/pretrained_model/.

### Compilation
Install all the python dependencies using pip:
```
pip install -r requirements.txt

```

Compile the cuda dependencies using following simple commands:
```
cd lib
python setup.py build develop
```
It will compile all the modules you need, including NMS, ROI_Align. Please check to compiled with coorsponding python version.

## Usage

train voc2007:

```
CUDA_VISIBLE_DEVICES=0 python trainval_net.py --dataset pascal_voc --cuda
```

test voc2007:

```
CUDA_VISIBLE_DEVICES=0 python test_net.py --dataset pascal_voc --checksession 1 --checkepoch 12 --checkpoint 10021 --cuda
```

train voc07+12:

```
CUDA_VISIBLE_DEVICES=0 python trainval_net.py --dataset pascal_voc_0712 --cuda
```

# Use trained FPN model 
## Download
Here I provide my trained FPN model(trained on pascal voc 2007, can detect 20 kinds of objects), you can simply test it without training. 

Download the model from [baiduyun](https://pan.baidu.com/s/1QIKIPkFTdMS0_SX1yFvKug)

## usage 
put the trained FPN model in /fpn-pytorch1.0/models/res101/pascal_voc/fpn_1_12_10021.pth

## check demo image detection result
Put images to be detected in /fpn-pytorch1.0/images/ 

Then run demo.py
```
CUDA_VISIBLE_DEVICES=0 python demo.py --dataset pascal_voc --checkepoch 12 --cuda
```

# TODO List
- [ ] Train and test on VOC0712
- [ ] Train and test on COCO
- [ ] Support softNMS
- [ ] Support DetNet




