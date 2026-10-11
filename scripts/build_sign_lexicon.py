"""Pre-build the signing cache for the doctor's likely words, so the patient's 3D signing starts
instantly instead of fetching each new sign during the conversation (~5 s per new sign).

  python scripts/build_sign_lexicon.py          # one-time, ~10-15 min, safe to stop and resume

Covers the doctor sentences in data/er_phrases.json plus common clinical words. Words without an
ASL Citizen sign are fetched from sign.mt (unless SIGN_MT=0).
"""
import csv
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from medbridge.text2sign import AslCitizenSigns, SignMT, build_lexicon, text_to_glosses  # noqa: E402

COMMON = """hello hi you your me my we doctor nurse hospital help pain hurt where when what how why who which feel
sick better worse now today yesterday tomorrow morning night day week hour minute time yes no not okay please
thank sorry understand sign deaf write read wait stay sit stand lie down breathe deep cough blood test scan medicine
pill shot needle water eat drink bathroom sleep tired dizzy vomit fever cold hot head stomach chest back arm leg
heart lungs eyes ear nose mouth throat skin bone allergic pregnant family wife husband mother father call phone
name age number one two three four five six seven eight nine ten more less little big small fast slow go come
give take show point tell ask need want have can will must again finish ready start stop safe okay fine good bad""".split()


def main():
    glosses = {r[2].strip() for r in list(csv.reader(open(ROOT / "data/aslc/ASL_Citizen/splits/train.csv")))[1:]}
    lex = build_lexicon(glosses)
    doctor = json.loads((ROOT / "data/er_phrases.json").read_text())["doctor"]
    pairs = {}
    for text in doctor + [" ".join(COMMON)]:
        for word, gloss in text_to_glosses(text, lex):
            pairs.setdefault(word, gloss)
    todo = sorted({g for g in pairs.values() if g and not (ROOT / f"data/signlex/aslc/{g}.npy").exists()})
    missing = sorted(w for w, g in pairs.items() if g is None)
    print(f"{len(pairs)} words: {len(todo)} signs to fetch from ASL Citizen, {len(missing)} words without a local sign")

    def fetch(chunk):
        signs = AslCitizenSigns(ROOT)  # one zip connection per worker
        for g in chunk:
            ok = signs.get(g) is not None
            print(f"  {'ok ' if ok else 'n/a'} {g}", flush=True)

    workers = 4
    with ThreadPoolExecutor(workers) as ex:
        list(ex.map(fetch, [todo[i::workers] for i in range(workers)]))
    if os.environ.get("SIGN_MT", "1") == "1":
        signmt = SignMT(ROOT)
        for w in missing:
            print(f"  {'ok ' if signmt.get(w) else 'n/a'} sign.mt: {w}", flush=True)
    print("done")


if __name__ == "__main__":
    main()
