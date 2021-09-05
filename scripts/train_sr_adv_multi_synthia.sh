python train_sr_multi_synthia.py \
        --snapshot-dir ./snapshots/batchsize2_1024x512_sr+adv_multi_classbalance10_kl1_0.2_kl2_1_lr2_drop0.2_seg0.5_synthia \
        --drop 0.2 \
        --warm-up 5000 \
        --batch-size 2 \
        --learning-rate 2e-4 \
        --crop-size 1024,512 \
        --lambda-seg 0.5 \
        --lambda-adv-target1 0.0002 \
        --lambda-adv-target2 0.001 \
        --lambda-kl-target1 0.2 \
        --lambda-kl-target2 1 \
        --norm-style gn \
        --class-balance \
        --only-hard-label -1 \
        --max-value 10 \
        --gpu-ids 0,1 \
        --often-balance \
        --use-se \