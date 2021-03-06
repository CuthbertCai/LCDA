import argparse
import scipy
from scipy import ndimage
import numpy as np
import sys
from packaging import version
from multiprocessing import Pool
import torch
from torch.autograd import Variable
import torchvision.models as models
import torch.nn.functional as F
from torch.utils import data, model_zoo
from model.deeplab import Res_Deeplab
from model.deeplab_multi import DeeplabMulti
from model.deeplab_vgg import DeeplabVGG
from model.deeplab_single import DeeplabSingle
from dataset.cityscapes_dataset import cityscapesDataSet
from collections import OrderedDict
import os
from PIL import Image
from utils.tool import fliplr
import matplotlib.pyplot as plt
import torch.nn as nn
import yaml
import time

torch.backends.cudnn.benchmark = True

IMG_MEAN = np.array((104.00698793, 116.66876762, 122.67891434), dtype=np.float32)

DATA_DIRECTORY = './data/Cityscapes/data'
DATA_LIST_PATH = './dataset/cityscapes_list/val.txt'
SAVE_PATH = './result/cityscapes'

IGNORE_LABEL = 255
NUM_CLASSES = 19
NUM_STEPS = 500  # Number of images in the validation set.
RESTORE_FROM = 'http://vllab.ucmerced.edu/ytsai/CVPR18/GTA2Cityscapes_multi-ed35151c.pth'
RESTORE_FROM_VGG = 'http://vllab.ucmerced.edu/ytsai/CVPR18/GTA2Cityscapes_vgg-ac4ac9f6.pth'
RESTORE_FROM_ORC = 'http://vllab1.ucmerced.edu/~whung/adaptSeg/cityscapes_oracle-b7b9934.pth'
SET = 'val'

EPSILON = 1.0

MODEL = 'DeeplabMulti'
ARCH='resnet101'

palette = [128, 64, 128, 244, 35, 232, 70, 70, 70, 102, 102, 156, 190, 153, 153, 153, 153, 153, 250, 170, 30,
           220, 220, 0, 107, 142, 35, 152, 251, 152, 70, 130, 180, 220, 20, 60, 255, 0, 0, 0, 0, 142, 0, 0, 70,
           0, 60, 100, 0, 80, 100, 0, 0, 230, 119, 11, 32]
zero_pad = 256 * 3 - len(palette)
for i in range(zero_pad):
    palette.append(0)


def sample_unit_vec(shape, n):
    mean = torch.zeros(shape)
    std = torch.ones(shape)
    dis = torch.distributions.Normal(mean, std)
    samples = dis.sample_n(n)
    samples = samples.view(n, -1)
    samples_norm = torch.norm(samples, 2, 1).view(n, 1)
    samples = samples / samples_norm
    return samples.view(n, *shape)


def colorize_mask(mask):
    # mask: numpy array of the mask
    new_mask = Image.fromarray(mask.astype(np.uint8)).convert('P')
    new_mask.putpalette(palette)

    return new_mask


def get_arguments():
    """Parse all the arguments provided from the CLI.

    Returns:
      A list of parsed arguments.
    """
    parser = argparse.ArgumentParser(description="DeepLab-ResNet Network")
    parser.add_argument("--model", type=str, default=MODEL,
                        help="Model Choice (DeeplabMulti/DeeplabVGG/Oracle/DeepLabSingle).")
    parser.add_argument("--arch", type=str, default=ARCH,
                        help="available options: resnet101, resnet50")
    parser.add_argument("--data-dir", type=str, default=DATA_DIRECTORY,
                        help="Path to the directory containing the Cityscapes dataset.")
    parser.add_argument("--data-list", type=str, default=DATA_LIST_PATH,
                        help="Path to the file listing the images in the dataset.")
    parser.add_argument("--ignore-label", type=int, default=IGNORE_LABEL,
                        help="The index of the label to ignore during the training.")
    parser.add_argument("--num-classes", type=int, default=NUM_CLASSES,
                        help="Number of classes to predict (including background).")
    parser.add_argument("--restore-from", type=str, default=RESTORE_FROM,
                        help="Where restore model parameters from.")
    parser.add_argument("--gpu", type=int, default=0,
                        help="choose gpu device.")
    parser.add_argument("--batchsize", type=int, default=16,
                        help="choose gpu device.")
    parser.add_argument("--set", type=str, default=SET,
                        help="choose evaluation set.")
    parser.add_argument("--save", type=str, default=SAVE_PATH,
                        help="Path to save result.")
    parser.add_argument("--epsilon", type=float, default=EPSILON,
                        help="Hyper-parameter for noise")
    return parser.parse_args()


def save(output_name):
    output, name = output_name
    output_col = colorize_mask(output)
    output = Image.fromarray(output)

    output.save('%s' % (name))
    output_col.save('%s_color.png' % (name.split('.jpg')[0]))
    return


def save_heatmap(output_name):
    output, name = output_name
    fig = plt.figure()
    plt.axis('off')
    heatmap = plt.imshow(output, cmap='viridis')
    # fig.colorbar(heatmap)
    fig.savefig('%s_heatmap.png' % (name.split('.jpg')[0]))
    return


def save_scoremap(output_name):
    output, name = output_name
    fig = plt.figure()
    plt.axis('off')
    heatmap = plt.imshow(output, cmap='viridis')
    # fig.colorbar(heatmap)
    fig.savefig('%s_scoremap.png' % (name.split('.jpg')[0]))
    return


def main():
    """Create the model and start the evaluation process."""
    args = get_arguments()

    config_path = os.path.join(os.path.dirname(args.restore_from), 'opts.yaml')
    with open(config_path, 'r') as stream:
        config = yaml.load(stream)

    args.model = config['model']
    print('ModelType:%s' % args.model)
    print('NormType:%s' % config['norm_style'])
    gpu0 = args.gpu
    batchsize = args.batchsize

    if not os.path.exists(args.save):
        os.makedirs(args.save)

    if args.model == 'DeepLab':
        model = DeeplabMulti(num_classes=args.num_classes, use_se=config['use_se'], train_bn=False,
                             norm_style=config['norm_style'])
    elif args.model == 'DeepLabMulti':
        model = DeeplabMulti(num_classes=args.num_classes, use_se=config['use_se'], train_bn=False,
                             norm_style=config['norm_style'], arch=args.arch)
    elif args.model == 'Oracle':
        model = Res_Deeplab(num_classes=args.num_classes)
        if args.restore_from == RESTORE_FROM:
            args.restore_from = RESTORE_FROM_ORC
    elif args.model == 'DeeplabVGG':
        model = DeeplabVGG(num_classes=args.num_classes)
        if args.restore_from == RESTORE_FROM:
            args.restore_from = RESTORE_FROM_VGG
    elif args.model == 'DeepLabSingle':
        model = DeeplabSingle(num_classes=args.num_classes, use_se=config['use_se'],
                              train_bn=False, norm_style=config['norm_style'])
    else:
        raise Exception('Please choose right model.')

    if args.restore_from[:4] == 'http':
        saved_state_dict = model_zoo.load_url(args.restore_from)
    else:
        saved_state_dict = torch.load(args.restore_from)

    try:
        model.load_state_dict(saved_state_dict)
    except:
        model = torch.nn.DataParallel(model)
        model.load_state_dict(saved_state_dict)
        if args.model == 'DeepLabSingle':
            model = model.module
    model.eval()
    model.cuda(gpu0)


    testloader = data.DataLoader(
        cityscapesDataSet(args.data_dir, args.data_list, crop_size=(512, 1024), resize_size=(1024, 512), mean=IMG_MEAN,
                          scale=False, mirror=False, set=args.set),
        batch_size=batchsize, shuffle=False, pin_memory=True, num_workers=4)

    scale = 1.25
    testloader2 = data.DataLoader(
        cityscapesDataSet(args.data_dir, args.data_list, crop_size=(round(512 * scale), round(1024 * scale)),
                          resize_size=(round(1024 * scale), round(512 * scale)), mean=IMG_MEAN, scale=False,
                          mirror=False, set=args.set),
        batch_size=batchsize, shuffle=False, pin_memory=True, num_workers=4)
    scale = 0.9
    testloader3 = data.DataLoader(
        cityscapesDataSet(args.data_dir, args.data_list, crop_size=(round(512 * scale), round(1024 * scale)),
                          resize_size=(round(1024 * scale), round(512 * scale)), mean=IMG_MEAN, scale=False,
                          mirror=False, set=args.set),
        batch_size=batchsize, shuffle=False, pin_memory=True, num_workers=4)

    if version.parse(torch.__version__) >= version.parse('0.4.0'):
        interp = nn.Upsample(size=(1024, 2048), mode='bilinear', align_corners=True)
    else:
        interp = nn.Upsample(size=(1024, 2048), mode='bilinear')

    sm = torch.nn.Softmax(dim=1)
    log_sm = torch.nn.LogSoftmax(dim=1)
    kl_distance = nn.KLDivLoss(reduction='none')

    for index, img_data in enumerate(zip(testloader, testloader2, testloader3)):
        batch, batch2, batch3 = img_data
        image, _, _, name = batch
        image2, _, _, name2 = batch2
        # image3, _, _, name3 = batch3

        inputs = image.cuda(gpu0)
        inputs2 = image2.cuda(gpu0)
        # inputs3 = Variable(image3).cuda()
        print('\r>>>>Extracting feature...%03d/%03d' % (index * batchsize, NUM_STEPS), end='')
        if args.model == 'DeepLab':
            with torch.no_grad():
                output1, output2 = model(inputs)
                output_batch = interp(sm(0.5 * output1 + output2))
                heatmap_output1, heatmap_output2 = output1, output2
                # output_batch = interp(sm(output1))
                # output_batch = interp(sm(output2))
                output1, output2 = model(fliplr(inputs))
                output1, output2 = fliplr(output1), fliplr(output2)
                output_batch += interp(sm(0.5 * output1 + output2))
                heatmap_output1, heatmap_output2 = heatmap_output1 + output1, heatmap_output2 + output2
                # output_batch += interp(sm(output1))
                # output_batch += interp(sm(output2))
                del output1, output2, inputs

                output1, output2 = model(inputs2)
                output_batch += interp(sm(0.5 * output1 + output2))
                # output_batch += interp(sm(output1))
                # output_batch += interp(sm(output2))
                output1, output2 = model(fliplr(inputs2))
                output1, output2 = fliplr(output1), fliplr(output2)
                output_batch += interp(sm(0.5 * output1 + output2))
                # output_batch += interp(sm(output1))
                # output_batch += interp(sm(output2))
                del output1, output2, inputs2
                output_batch = output_batch.cpu().data.numpy()
                heatmap_batch = torch.sum(kl_distance(log_sm(heatmap_output1), sm(heatmap_output2)), dim=1)
                heatmap_batch = torch.log(1 + 10 * heatmap_batch)  # for visualization
                heatmap_batch = heatmap_batch.cpu().data.numpy()

                # output1, output2 = model(inputs3)
                # output_batch += interp(sm(0.5* output1 + output2)).cpu().data.numpy()
                # output1, output2 = model(fliplr(inputs3))
                # output1, output2 = fliplr(output1), fliplr(output2)
                # output_batch += interp(sm(0.5 * output1 + output2)).cpu().data.numpy()
                # del output1, output2, inputs3
        elif args.model == 'DeepLabMulti':
            with torch.no_grad():
                output1, output2 = model(inputs)
                # noise1 = sample_unit_vec(output1.shape[1:], output1.shape[0])
                noise = sample_unit_vec(output2.shape[1:], output2.shape[0])
                if torch.cuda.is_available():
                    noise = noise.cuda()
                output2_n = output2 + args.epsilon * noise
                # output2 = interp(sm(output2))
                output_batch = interp(sm(0.5 * output1 + output2))
                output_noise = interp(sm(output2_n))
                output2 = interp(sm(output2))
                heatmap_batch = torch.sum(kl_distance(log_sm(output_noise), sm(output2)), dim=1)
                heatmap_batch = (heatmap_batch - torch.min(heatmap_batch)) / (torch.max(heatmap_batch) - torch.min(heatmap_batch))
                output_diff = torch.abs(torch.argmax(output_noise, dim=1) - torch.argmax(output2, dim=1))
                heatmap_batch = output_diff * heatmap_batch

                weights = torch.ones(1, 1, 15, 15).type_as(heatmap_batch)
                padding = 7
                heatmap_batch = torch.nn.functional.conv2d(heatmap_batch.unsqueeze(1), weights, padding=padding)
                heatmap_batch = torch.nn.functional.conv2d(heatmap_batch, weights, padding=padding).squeeze()

                # heatmap_batch = 1e8 * heatmap_batch.data.cpu().numpy()
                # heatmap_batch = heatmap_batch.data.cpu().numpy()
                # thres = np.percentile(heatmap_batch[:], 95, axis=0)
                # heatmap_batch[heatmap_batch < thres] = 0
                # heatmap_batch = torch.nn.functional.sigmoid(heatmap_batch)
                # heatmap_batch = torch.nn.functional.sigmoid(heatmap_batch)
                # print(heatmap_batch[0])
                # heatmap_batch = torch.log(1 + heatmap_batch)
                # del output1, output2, output_noise
                del output1, output2

                output1, output2 = model(fliplr(inputs))
                output1, output2 = fliplr(output1), fliplr(output2)
                output_batch += interp(sm(0.5 * output1 + output2))

                del output1, output2, inputs

                output1, output2 = model(inputs2)
                output_batch += interp(sm(0.5 * output1 + output2))
                output1, output2 = model(fliplr(inputs2))
                output1, output2 = fliplr(output1), fliplr(output2)
                output_batch += interp(sm(0.5 * output1 + output2))

                del output1, output2, inputs2

                # heatmap_batch = torch.sum(torch.ones_like(output_batch), dim=1).cpu().data.numpy()
                output_batch = output_batch.cpu().data.numpy()
                # heatmap_batch = torch.log(1 + 100 * heatmap_batch)
                heatmap_batch = heatmap_batch.cpu().data.numpy()

        elif args.model == 'DeepLabSingle':
            with torch.no_grad():
                output = model.extractor(inputs)
                # noise = sample_unit_vec(output.shape[1:], output.shape[0])
                # if torch.cuda.is_available():
                #     noise = noise.cuda()
                # output_n = output + args.epsilon * noise
                output = model.classifier(output)
                # output_n = model.classifier(output_n)
                # output_noise = interp(sm(output_n))
                output_batch = interp(sm(output))

                # heatmap_batch = torch.sum(kl_distance(log_sm(output_noise), sm(output)), dim=1)
                # heatmap_batch = (heatmap_batch - torch.min(heatmap_batch)) / (torch.max(heatmap_batch) - torch.min(heatmap_batch))
                # del output, output_n
                del output

                output = model(fliplr(inputs))
                output = fliplr(output)
                output_batch += interp(sm(output))

                del output, inputs

                output = model(inputs2)
                output_batch += interp(sm(output))
                del output
                output = model(fliplr(inputs2))
                output = fliplr(output)
                output_batch += interp(sm(output))

                # del output, inputs2

                heatmap_batch = torch.sum(torch.ones_like(output_batch), dim=1).cpu().data.numpy()
                output_batch = output_batch.cpu().data.numpy()
                # heatmap_batch = torch.log(1 + 100 * heatmap_batch)
                # heatmap_batch = heatmap_batch.cpu().data.numpy()
        elif args.model == 'DeeplabVGG' or args.model == 'Oracle':
            output_batch = model(Variable(image).cuda())
            output_batch = interp(output_batch).cpu().data.numpy()

        output_batch = output_batch.transpose(0, 2, 3, 1)
        scoremap_batch = np.asarray(np.max(output_batch, axis=3))
        output_batch = np.asarray(np.argmax(output_batch, axis=3), dtype=np.uint8)
        output_iterator = []
        heatmap_iterator = []
        scoremap_iterator = []

        for i in range(output_batch.shape[0]):
            output_iterator.append(output_batch[i, :, :])
            heatmap_iterator.append(heatmap_batch[i, :, :] / np.max(heatmap_batch[i, :, :]))
            scoremap_iterator.append(1 - scoremap_batch[i, :, :] / np.max(scoremap_batch[i, :, :]))
            name_tmp = name[i].split('/')[-1]
            name[i] = '%s/%s' % (args.save, name_tmp)
        with Pool(4) as p:
            p.map(save, zip(output_iterator, name))
            p.map(save_heatmap, zip(heatmap_iterator, name))
            p.map(save_scoremap, zip(scoremap_iterator, name))

        del output_batch

    return args.save


if __name__ == '__main__':
    tt = time.time()
    with torch.no_grad():
        save_path = main()
    print('Time used: {} sec'.format(time.time() - tt))
    os.system('python compute_iou.py ./data/Cityscapes/data/gtFine/val %s' % save_path)
