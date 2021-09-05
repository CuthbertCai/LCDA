python train_ba_multi.py \
        --snapshot-dir ./snapshots/batchsize2_1024x512_ba_multi_lr2_drop0.2 \
        --drop 0.2 \
        --warm-up 5000 \
        --batch-size 2 \
        --learning-rate 2e-4 \
        --crop-size 1024,512 \
        --norm-style gn \
        --only-hard-label -1 \
        --gpu-ids 0,1 \
        --use-se \
