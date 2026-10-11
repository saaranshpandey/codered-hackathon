"""Pose preprocessing for Uni-Sign (pose-only).

load_part_kp and crop_scale are copied from Uni-Sign datasets.py
(https://github.com/ZechengLi19/Uni-Sign) so inputs match what the checkpoint was trained on.
Input keypoints are rtmlib Wholebody (COCO-WholeBody, 133 points) divided by (W, H).
"""
import copy

import numpy as np
import torch


def load_part_kp(skeletons, confs):
    thr = 0.3
    kps_with_scores = {}
    scale = None

    for part in ['body', 'left', 'right', 'face_all']:
        kps = []
        confidences = []

        for skeleton, conf in zip(skeletons, confs):
            skeleton = skeleton[0]
            conf = conf[0]

            if part == 'body':
                hand_kp2d = skeleton[[0] + [i for i in range(3, 11)], :]
                confidence = conf[[0] + [i for i in range(3, 11)]]
            elif part == 'left':
                hand_kp2d = skeleton[91:112, :]
                hand_kp2d = hand_kp2d - hand_kp2d[0, :]
                confidence = conf[91:112]
            elif part == 'right':
                hand_kp2d = skeleton[112:133, :]
                hand_kp2d = hand_kp2d - hand_kp2d[0, :]
                confidence = conf[112:133]
            elif part == 'face_all':
                hand_kp2d = skeleton[[i for i in list(range(23, 23 + 17))[::2]] + [i for i in range(83, 83 + 8)] + [53], :]
                hand_kp2d = hand_kp2d - hand_kp2d[-1, :]
                confidence = conf[[i for i in list(range(23, 23 + 17))[::2]] + [i for i in range(83, 83 + 8)] + [53]]
            else:
                raise NotImplementedError

            kps.append(hand_kp2d)
            confidences.append(confidence)

        kps = np.stack(kps, axis=0)
        confidences = np.stack(confidences, axis=0)

        if part == 'body':
            result, scale, _ = crop_scale(np.concatenate([kps, confidences[..., None]], axis=-1), thr)
        else:
            assert not scale is None
            result = np.concatenate([kps, confidences[..., None]], axis=-1)
            if scale == 0:
                result = np.zeros(result.shape)
            else:
                result[..., :2] = (result[..., :2]) / scale
                result = np.clip(result, -1, 1)
                # mask useless kp
                result[result[..., 2] <= thr] = 0

        kps_with_scores[part] = torch.tensor(result)

    return kps_with_scores


def crop_scale(motion, thr):
    '''
        Motion: [(M), T, 17, 3].
        Normalize to [-1, 1]
    '''
    result = copy.deepcopy(motion)
    valid_coords = motion[motion[..., 2] > thr][:, :2]
    if len(valid_coords) < 4:
        return np.zeros(motion.shape), 0, None
    xmin = min(valid_coords[:, 0])
    xmax = max(valid_coords[:, 0])
    ymin = min(valid_coords[:, 1])
    ymax = max(valid_coords[:, 1])
    ratio = 1
    scale = max(xmax - xmin, ymax - ymin) * ratio
    if scale == 0:
        return np.zeros(motion.shape), 0, None
    xs = (xmin + xmax - scale) / 2
    ys = (ymin + ymax - scale) / 2
    result[..., :2] = (motion[..., :2] - [xs, ys]) / scale
    result[..., :2] = (result[..., :2] - 0.5) * 2
    result = np.clip(result, -1, 1)
    # mask useless kp
    result[result[..., 2] <= thr] = 0
    return result, scale, [xs, ys]


def sample_indices(duration, max_length):
    """Frames to keep. Upstream draws a random sorted subset when too long; we space them
    evenly so live output is deterministic."""
    if duration <= max_length:
        return np.arange(duration)
    return np.linspace(0, duration - 1, max_length).round().astype(int)


def build_src_input(skeletons, confs, max_length=256):
    """Single-clip equivalent of Uni-Sign's S2T_Dataset_online.load_pose + collate_fn."""
    idx = sample_indices(len(confs), max_length)
    parts = load_part_kp([skeletons[i] for i in idx], [confs[i] for i in idx])
    src = {k: v[None].float() for k, v in parts.items()}
    src["attention_mask"] = torch.ones(1, len(idx), dtype=torch.long)
    return src
