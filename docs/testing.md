# Testing MEDBRIDGE on one Mac

This guide shows how to test both directions on one MacBook (built-in camera and microphone), with the
patient and doctor views side by side. Work through the sections in order. Write results in the sheet at the end.

## 0. Start

```bash
source .venv/bin/activate
python -m medbridge.server                # add METRICS_LOG=1 in front to record timings
python scripts/sign_reference.py && open data/sign_reference.html   # how to sign each word (practice first)
```

1. Open two Chrome windows and tile them: hold the green window button and choose **Tile Window to Left of Screen**.
   - Left: http://localhost:8000/patient
   - Right: http://localhost:8000/doctor
2. Wait about 20 s. The patient view shows **Ready** under the camera and **Listening to doctor** at the top.
   The doctor's System panel shows about **30 fps**.
3. **Framing.** Sit an arm's length from the MacBook, so you are visible from the waist up with face and both hands in frame.
   Use light from the front (no window behind you) and a plain background if possible.
4. **Rest position.** Between signs and sentences, put your hands in your lap, below the bottom of the camera image.
   Lowering your hands is how the app knows you have finished.
5. **One mic.** The MacBook mic hears everyone. The person playing the doctor speaks. The person signing stays silent.

## 1. Doctor → patient captions (no signing needed)

Read each line at a normal pace, then pause for 1 second.

1. Hi, I'm Doctor Lee. What brought you in today?
2. Are you experiencing chest pain?
3. On a scale of one to ten, how bad is the pain?
4. Do you have any allergies to medications, like penicillin?
5. Are you taking any medicine right now, such as aspirin or blood thinners?
6. We are going to take some blood and get a CT scan.
7. I'm going to give you ibuprofen for the pain.
8. Do you feel dizzy when you stand up?

Check:
- **Live captions:** the grey shimmering line updates while you speak. About 1 s after you stop, it becomes a large white final line.
- **Correction:** on the doctor view, click a caption and change one word (e.g. a drug name), then press Enter.
  The patient view shows **Corrected by doctor** with the changed word highlighted.
- **Pause:** press **Pause captions**, speak, and confirm that nothing appears. Then press **Resume captions**.

Record the number of lines with a wrong word, and any drug or medical term that was misheard.

## 2. Precise mode: one sign at a time (start here, most reliable)

On the patient view, choose **One sign at a time**. For each row:
- Sign one word, then put your hands in your lap.
- A chip appears. Then sign the next word.
- Press **Confirm & send**.
- **Retry** clears the draft. Tapping a chip shows the model's top 5 so you can pick the right one. **×** removes a chip.

Every sign below was recognized correctly on all held-out test videos of Deaf signers.
Use `data/sign_reference.html` to see exactly how each one is signed. That page shows the variant the model learned.

| # | Sign these, in order | Doctor should see (literal mode) |
|---|---|---|
| 1 | NO | No. |
| 2 | STOMACH · HURT | Stomach hurt. |
| 3 | HEADACHE | Headache. |
| 4 | ME · DIZZY | Me dizzy. |
| 5 | YESTERDAY · MORNING | Yesterday morning. |
| 6 | SIX (pain scale; also try THREE, FOUR, EIGHT, NINE) | Six. |
| 7 | PLEASE · HELP | Please help. |
| 8 | ME · BREATHE · NOT | Me breathe not. |
| 9 | CAR ACCIDENT (a single sign) | Car accident. |
| 10 | ME · PREGNANT | Me pregnant. |
| 11 | ME · SICK · TIRED | Me sick tired. |
| 12 | ME · DEAF · PLEASE · WRITE | Me deaf please write. |

- Set `GLOSS_TRANSLATOR=llm` in `.env` (with Claude credentials) to get rephrased sentences instead, for example
  row 2 becoming "My stomach hurts." The badge then says "rephrased by Claude".
- FIVE and TEN are not in the vocabulary.
- YES is only 2/3 reliable on test videos. Sign it clearly, or use the chip picker if it is missed.

**Per-sign accuracy:** sign each of 10 words five times. Count how often the first chip is right (top-1), and how often the
right word is in the chip's top-5 list.

## 3. Natural signing: whole sentences

On the patient view, choose **Natural signing**.
- Sign the whole sentence at a normal pace, then rest your hands in your lap for about 1 second.
- If the sentence does not end, press **Done signing**.
- Three English candidates appear. Pick the right one if any, then confirm, **Edit**, or **Retry**.

**Expectations.** This model was trained on fluent signers in news and instructional videos, not on ER sentences.
- It will often be wrong, especially for short phrases or novice signing.
- A **Low confidence** banner means the model itself rates the result as weak.
- Record honestly what happens. That is the result.

ASL word order differs from English, so sign the gloss column.
- For signs that are not on the reference page, look them up at `https://www.signingsavvy.com/search/<word>`.

| # | Meaning | Sign (ASL gloss order) |
|---|---|---|
| 1 | My stomach hurts. | MY STOMACH HURT |
| 2 | My head hurts. | MY HEAD HURT |
| 3 | I can't breathe well. | ME BREATHE CAN'T |
| 4 | The pain started yesterday. | YESTERDAY PAIN START |
| 5 | I feel dizzy. | ME FEEL DIZZY |
| 6 | I vomited this morning. | MORNING ME VOMIT |
| 7 | I am allergic to medicine. | ME ALLERGY MEDICINE |
| 8 | The pain is worse now. | NOW PAIN WORSE |
| 9 | I fell down. | ME FALL |
| 10 | I was in a car accident. | ME CAR ACCIDENT |
| 11 | I am pregnant. | ME PREGNANT |
| 12 | I need the bathroom. | ME NEED BATHROOM |
| 13 | I am cold. | ME COLD |
| 14 | Please call my wife. | PLEASE CALL MY WIFE |
| 15 | I don't understand, please write it down. | ME UNDERSTAND NOT, PLEASE WRITE |
| 16 | I am deaf. | ME DEAF |
| 17 | My heart hurts. | MY HEART HURT |
| 18 | Thank you. | THANK-YOU |
| 19 | Yes. | YES |
| 20 | No. | NO |

For each sentence, record one of:
- **top-1:** the first candidate has the right meaning;
- **top-3:** one of the three has it;
- **miss.**

Also note whether **Low confidence** was shown. Comparing misses with low-confidence flags tells you whether the flag is useful.

## 4. False recognition (2 minutes per mode)

Sit in frame for 2 minutes without signing:
- talk with your hands;
- scratch your face;
- adjust your hair or glasses;
- drink some water.

Count the outputs that appear **without** a "Low confidence" banner (natural) or a "Not sure — pick" chip (precise).
Those are false recognitions. Nothing reaches the doctor unless you press **Confirm & send**.

## 5. Full exchange (both windows)

| # | Doctor says | Patient replies | Mode |
|---|---|---|---|
| 1 | "Hi, what brought you in today?" | MY STOMACH HURT | natural (switch to precise if it misses) |
| 2 | "When did it start?" | YESTERDAY · MORNING | precise |
| 3 | "How bad is it, one to ten?" | SIX | precise |
| 4 | "Are you allergic to any medicine?" | NO | precise |
| 5 | "Do you feel dizzy?" | ME · DIZZY | precise |

An exchange is successful when the doctor view shows the right meaning with **✓ Confirmed by patient**, and no
typing was needed. The doctor's System panel shows translation and recognition latency for each reply.

## 6. Results sheet

| Test | Result |
|---|---|
| Captions: lines with a wrong word (of 8) | |
| Captions: misheard medical terms | |
| Precise: top-1 / top-5 over 10 signs × 5 tries | / |
| Natural: top-1 / top-3 / miss (of 20) | / / |
| Natural: misses that were flagged low confidence | |
| False recognitions per 2 min (natural / precise) | / |
| Full exchanges successful (of 5) | |
| Typical latency: caption, sentence, sign (System panel) | |

## If something is off

| Symptom | Try |
|---|---|
| The camera ring never turns orange | More light on your hands. Move back so both hands are fully in frame. |
| A sentence never ends | Put your hands fully below the bottom of the image, or press **Done signing**. Raise `REST_LINE` in `.env` (e.g. 0.9) if your lap is visible in the frame. |
| Precise mode makes a chip on every small movement | Keep your hands in your lap between signs. |
| Captions show the signer's own voice | One mic hears everyone. The signer stays silent. |
| fps well below 30 | Close other heavy apps and keep the Mac plugged in. |
