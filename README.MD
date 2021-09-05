# Unsupervised Adaptive Semantic Segmentation with Local Lipschitz Constraint
[Unsupervised Adaptive Semantic Segmentation with Local Lipschitz Constraint][1]  
Guanyu Cai, Lianghua He

Pytorch implementation of our method for domain adaptation on semantic segmentation.  

## Requirement
`pip install requirements.txt`

## Data
Please refer to [Seg_Uncertainty][2]

## Train
*Please replace CHECKPOINT_PATH in scripts to your own path.*  

### Source-only model
`sh scripts/train_ba_multi_gta.sh` for GTA5 dataset  
`sh scripts/train_ba_multi_synthia.sh` for SYNTHIA dataset  

### LCDA model
`sh scripts/train_sr_multi_gta.sh` for GTA5 dataset  
`sh scripts/train_sr_multi_synthia.sh` for SYNTHIA dataset  

### LCDA+Adv model
`sh scripts/train_sr_adv_multi_gta.sh` for GTA5 dataset  
`sh scripts/train_sr_adv_multi_synthia.sh` for SYNTHIA dataset  

### LCDA+Adv+LCRF model
`sh scripts/generate_cityscapes_plabel.sh` to generate pseudo labels of Cityscapes  
`sh scripts/train_sr_ft_multi.sh`  


## Test
*Please replace CHECKPOINT_PATH in test.sh to your own path.*  
`sh scripts/test.sh`  

## Acknowledgment
This repo is borrowed from  
[Seg_Uncertainty][2]  
[AdaptSeg][3]  
[SRDA][4]  

## Citation
```

```

[1]:https://arxiv.org/pdf/2105.12939.pdf
[2]:https://github.com/layumi/Seg-Uncertainty
[3]:https://github.com/wasidennis/AdaptSegNet
[4]:https://github.com/CuthbertCai/SRDA