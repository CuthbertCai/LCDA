python train_ba_multi_synthia.py \
        --snapshot-dir ./snapshots/batchsize2_1024x512_ba_multi_classbalance10_lr2_drop0.2_synthia \
        --drop 0.2 \
        --warm-up 5000 \
        --batch-size 2 \
        --learning-rate 2e-4 \
        --crop-size 1024,512 \
        --norm-style gn \
        --only-hard-label -1 \
        --gpu-ids 0,1 \
        --use-se \
