"""Precise mode: isolated sign recognition with the ASL Citizen ST-GCN (Microsoft, MIT).

Preprocessing is a line-for-line port of ASLCitizen.__getitem__ in
https://github.com/microsoft/ASL-citizen-code/blob/main/ST-GCN/asl_citizen_dataset_pose.py
"""
import csv

import numpy as np
import torch

from medbridge.stgcn.fc import FC
from medbridge.stgcn.network import Network
from medbridge.stgcn.st_gcn import STGCN

MAX_FRAMES = 128
KEYPOINTS = [0, 2, 5, 11, 12, 13, 14, 33, 37, 38, 41, 42, 45, 46, 49, 50, 53, 54,
             58, 59, 62, 63, 66, 67, 70, 71, 74]
GRAPH_ARGS = {'num_nodes': 27, 'center': 0,
              'inward_edges': [[2, 0], [1, 0], [0, 3], [0, 4], [3, 5],
                               [4, 6], [5, 7], [6, 17], [7, 8], [7, 9],
                               [9, 10], [7, 11], [11, 12], [7, 13], [13, 14],
                               [7, 15], [15, 16], [17, 18], [17, 19], [19, 20],
                               [17, 21], [21, 22], [17, 23], [23, 24], [17, 25], [25, 26]]}


def load_gloss_list(train_csv):
    """Class index order used in training: sorted unique glosses of the training split."""
    with open(train_csv) as f:
        rows = list(csv.reader(f))[1:]
    return sorted({r[2].strip() for r in rows})


def holistic_to_array(results):
    """MediaPipe Holistic result -> (543, 2) in the training layout:
    pose 0-32, right hand 33-53, left hand 54-74, face 75-542; missing parts stay 0."""
    out = np.zeros((543, 2))
    for start, lms in ((0, results.pose_landmarks), (33, results.right_hand_landmarks),
                       (54, results.left_hand_landmarks), (75, results.face_landmarks)):
        if lms:
            out[start:start + len(lms.landmark)] = [(p.x, p.y) for p in lms.landmark]
    return out


def downsample(frames, max_frames):
    length = frames.shape[0]
    increment = max_frames / length
    if increment > 1.0:
        increment = 1.0
    curr_increment = 0
    curr_frame = 0
    new_frames = []
    for f in frames:
        curr_increment += increment
        if curr_increment > curr_frame:
            curr_frame += 1
            new_frames.append(f)
    if len(new_frames) > max_frames:
        new_frames = new_frames[:max_frames]
    return np.array(new_frames)


def preprocess(data0):
    """(T, >=75, 2) pose array -> (1, 2, 128, 27) model input."""
    length = data0.shape[0]
    if length > MAX_FRAMES:
        data0 = downsample(data0, MAX_FRAMES)
    if length < MAX_FRAMES:
        data0 = np.pad(data0, ((0, MAX_FRAMES - length), (0, 0), (0, 0)))

    # normalize keypoints using distance between shoulders as reference
    # (averaged over all 128 frames, padding included, exactly as in training)
    shoulder_l = data0[:, 11, :]
    shoulder_r = data0[:, 12, :]
    center = ((shoulder_r + shoulder_l) / 2).sum(0) / shoulder_l.shape[0]
    mean_dist = np.mean(np.sqrt(((shoulder_l - shoulder_r) ** 2).sum(-1)))
    if mean_dist != 0:
        data0 = (data0 - center) * (1.0 / mean_dist)

    data0 = data0[:, 0:75, :]
    data = np.concatenate([data0[:, 0:33], data0[:, 54:], data0[:, 33:54]], axis=1)
    data = data[:, KEYPOINTS, :]
    return torch.from_numpy(np.transpose(data, (2, 0, 1))).float()[None]


def load_stgcn(weights, n_classes):
    model = Network(encoder=STGCN(in_channels=2, graph_args=GRAPH_ARGS, edge_importance_weighting=True),
                    decoder=FC(n_features=256, num_class=n_classes, dropout_ratio=0.05))
    model.load_state_dict(torch.load(weights, map_location="cpu"), strict=True)
    return model.float().eval()


def topk(logits, glosses, vocab=None, k=5):
    """Ranked predictions. With a vocab {gloss: label}, other glosses are masked out,
    softmax is renormalised over the vocab, and variants sharing a label are summed."""
    if vocab is None:
        p = torch.softmax(logits, -1)
        idx = torch.argsort(p, descending=True)[:k]
        return [{"label": glosses[i], "glosses": [glosses[i]], "p": float(p[i])} for i in idx]

    pos = [i for i, g in enumerate(glosses) if g in vocab]
    p = torch.softmax(logits[pos], -1)
    merged = {}
    for i, pi in zip(pos, p.tolist()):
        m = merged.setdefault(vocab[glosses[i]], {"label": vocab[glosses[i]], "glosses": [], "p": 0.0})
        m["glosses"].append(glosses[i])
        m["p"] += pi
    return sorted(merged.values(), key=lambda m: -m["p"])[:k]
