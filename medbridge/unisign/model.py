"""Uni-Sign, pose-only inference subset.

Trimmed from Uni-Sign models.py (https://github.com/ZechengLi19/Uni-Sign, ICLR 2025):
the RGB branch, deformable attention and training loss are removed. Module names are kept
so the released checkpoints load with strict=True.
"""
import torch
from torch import nn
from transformers import MT5Config, MT5ForConditionalGeneration, T5Tokenizer

from .stgcn_layers import Graph, get_stgcn_chain

MODES = ['body', 'left', 'right', 'face_all']


class UniSignPose(nn.Module):
    def __init__(self, mt5_path, lang, hidden_dim=256):
        super().__init__()
        self.lang = lang
        self.graph, A = {}, []
        self.proj_linear = nn.ModuleDict()
        for mode in MODES:
            self.graph[mode] = Graph(layout=f'{mode}', strategy='distance', max_hop=1)
            A.append(torch.tensor(self.graph[mode].A, dtype=torch.float32, requires_grad=False))
            self.proj_linear[mode] = nn.Linear(3, 64)

        self.gcn_modules = nn.ModuleDict()
        self.fusion_gcn_modules = nn.ModuleDict()
        spatial_kernel_size = A[0].size(0)
        for index, mode in enumerate(MODES):
            self.gcn_modules[mode], final_dim = get_stgcn_chain(64, 'spatial', (1, spatial_kernel_size), A[index].clone(), True)
            self.fusion_gcn_modules[mode], _ = get_stgcn_chain(final_dim, 'temporal', (5, spatial_kernel_size), A[index].clone(), True)

        self.gcn_modules['left'] = self.gcn_modules['right']
        self.fusion_gcn_modules['left'] = self.fusion_gcn_modules['right']
        self.proj_linear['left'] = self.proj_linear['right']

        self.part_para = nn.Parameter(torch.zeros(hidden_dim * len(MODES)))
        self.pose_proj = nn.Linear(256 * 4, 768)

        # Weights come from the Uni-Sign checkpoint, so build mT5 from its config only.
        self.mt5_model = MT5ForConditionalGeneration(MT5Config.from_pretrained(mt5_path))
        self.mt5_tokenizer = T5Tokenizer.from_pretrained(mt5_path, legacy=False)

    def encode(self, src_input):
        features = []
        body_feat = None
        for part in MODES:
            proj_feat = self.proj_linear[part](src_input[part]).permute(0, 3, 1, 2)  # B,C,T,V
            gcn_feat = self.gcn_modules[part](proj_feat)
            if part == 'body':
                body_feat = gcn_feat
            elif part == 'left':
                gcn_feat = gcn_feat + body_feat[..., -2][..., None].detach()
            elif part == 'right':
                gcn_feat = gcn_feat + body_feat[..., -1][..., None].detach()
            elif part == 'face_all':
                gcn_feat = gcn_feat + body_feat[..., 0][..., None].detach()
            gcn_feat = self.fusion_gcn_modules[part](gcn_feat)  # B,C,T,V
            features.append(gcn_feat.mean(-1).transpose(1, 2))  # B,T,C

        inputs_embeds = torch.cat(features, dim=-1) + self.part_para
        inputs_embeds = self.pose_proj(inputs_embeds)

        prefix_token = self.mt5_tokenizer(
            [f"Translate sign language video to {self.lang}: "] * inputs_embeds.shape[0],
            padding="longest", truncation=True, return_tensors="pt",
        ).to(inputs_embeds.device)
        prefix_embeds = self.mt5_model.encoder.embed_tokens(prefix_token['input_ids'])
        inputs_embeds = torch.cat([prefix_embeds, inputs_embeds], dim=1)
        attention_mask = torch.cat([prefix_token['attention_mask'], src_input['attention_mask']], dim=1)
        return inputs_embeds, attention_mask

    @torch.no_grad()
    def translate(self, src_input, num_beams=4, num_return=3, max_new_tokens=100):
        """Returns [(text, sequence_score)] best-first; scores are length-normalised log-probs."""
        inputs_embeds, attention_mask = self.encode(src_input)
        out = self.mt5_model.generate(
            inputs_embeds=inputs_embeds, attention_mask=attention_mask,
            max_new_tokens=max_new_tokens, num_beams=num_beams, num_return_sequences=num_return,
            output_scores=True, return_dict_in_generate=True,
        )
        texts = self.mt5_tokenizer.batch_decode(out.sequences, skip_special_tokens=True)
        return list(zip(texts, out.sequences_scores.float().tolist()))


def load_unisign(ckpt_path, lang="English", device="cpu", dtype=torch.float32, mt5_path="google/mt5-base"):
    model = UniSignPose(mt5_path, lang)
    state_dict = torch.load(ckpt_path, map_location='cpu')['model']
    report = model.load_state_dict(state_dict, strict=False)
    model.eval().to(device=device, dtype=dtype)
    return model, report
