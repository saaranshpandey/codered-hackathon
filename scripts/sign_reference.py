"""Build data/sign_reference.html: how to sign each precise-mode word, shown by Deaf signers from the
held-out ASL Citizen test set (the exact sign variants the model was trained on), with the model's
measured accuracy on those clips. Local practice aid only; the page and videos stay in data/ (gitignored).

Needs the clips/poses cached by scripts/eval_islr.py.  Usage: python scripts/sign_reference.py && open data/sign_reference.html
"""
import csv
import html
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from medbridge.islr import load_gloss_list, load_stgcn, preprocess, topk  # noqa: E402

SPLITS = ROOT / "data/aslc/ASL_Citizen/splits"


def main():
    glosses = load_gloss_list(SPLITS / "train.csv")
    vocab = json.loads((ROOT / "data/medical_vocab.json").read_text())
    model = load_stgcn(ROOT / "data/models/aslc_stgcn/ASL_citizen_stgcn_weights.pt", len(glosses))

    clips = defaultdict(list)
    for row in list(csv.reader(open(SPLITS / "test.csv")))[1:]:
        g = row[2].strip()
        if g in vocab and (ROOT / "data/eval/aslc" / row[1]).exists() and (ROOT / "data/eval/aslc_poses" / (row[1] + ".npy")).exists():
            clips[vocab[g]].append((g, row[1]))

    cards = []
    for label in dict.fromkeys(vocab.values()):
        items = clips.get(label, [])
        hits = 0
        for _, f in items:
            with torch.no_grad():
                logits = model(preprocess(np.load(ROOT / "data/eval/aslc_poses" / (f + ".npy"))))[0]
            hits += topk(logits, glosses, vocab, k=1)[0]["label"] == label
        cards.append((hits / len(items) if items else -1, label, items, hits))
    cards.sort(key=lambda c: (-c[0], c[1]))

    def card(acc, label, items, hits):
        word = label.split(" / ")[0]
        vids = "".join(f'<video src="eval/aslc/{html.escape(f)}" muted loop playsinline preload="metadata" '
                       f'onmouseover="this.play()" onmouseout="this.pause()" controls></video>' for _, f in items[:2])
        score = f"{hits}/{len(items)} held-out clips correct" if items else "no reference clip downloaded"
        tone = "good" if acc >= 0.99 else "ok" if acc >= 0.6 else "weak"
        return (f'<article class="{tone}"><header><h2>{html.escape(label)}</h2><span>{score}</span></header>'
                f'<div class="vids">{vids}</div><footer>{html.escape(" · ".join(sorted({g for g, _ in items})))}'
                f' · <a href="https://www.signingsavvy.com/search/{html.escape(word)}" target="_blank">Signing Savvy</a></footer></article>')

    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Medbridge · Sign reference</title>
<style>
body{{margin:0;background:#0e0f0c;color:#f2eee6;font:16px/1.4 -apple-system,system-ui,sans-serif;padding:32px}}
h1{{font:400 40px Georgia,serif;margin:0 0 6px}} p.lead{{color:#f2eee699;max-width:820px}}
main{{display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:16px;margin-top:24px}}
article{{background:#171813;border:1px solid #f2eee61a;border-radius:20px;padding:14px}}
article.good{{border-color:#3ddc9766}} article.weak{{border-color:#ffb02066}}
header{{display:flex;justify-content:space-between;align-items:baseline}} h2{{margin:0 0 8px;font-size:22px}}
header span,footer{{font:12px ui-monospace,monospace;color:#f2eee680}} footer a{{color:#f2eee6}}
.vids{{display:grid;grid-template-columns:1fr 1fr;gap:8px}} video{{width:100%;border-radius:12px;background:#000}}
</style></head><body>
<h1>Signs Medbridge can recognize (one sign at a time)</h1>
<p class="lead">Each card shows Deaf signers from the held-out ASL Citizen test set performing the exact sign the model learned.
Green = the model got every held-out clip right; amber = less than 60%. Start testing with the green ones.
Sign one word, lower your hands, then sign the next. Hover a video to play it.</p>
<main>{"".join(card(*c) for c in cards)}</main></body></html>"""
    out = ROOT / "data/sign_reference.html"
    out.write_text(page)
    good = sum(1 for c in cards if c[0] >= 0.99)
    print(f"wrote {out}  ({len(cards)} signs, {good} with every held-out clip correct)")


if __name__ == "__main__":
    main()
