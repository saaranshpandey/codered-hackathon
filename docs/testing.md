# Testing MEDBRIDGE on one Mac

This guide shows how to test both directions on one MacBook (built-in camera and microphone), with the
patient and doctor views side by side. Work through the sections in order. Write results in the sheet at the end.

**Natural signing is switched off for now.** The patient view has no mode switch and always uses one sign at a time.
Skip section 3 and the natural-signing rows in sections 4 to 6.

**The sign chips are switched off for now.** Each recognized sign goes straight into "Your message to the doctor".
Where the steps below mention a chip, look at that message instead. To fix a wrong word, press **Edit**, or **Retry**
to start again.

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

## Quick first test (2 minutes, precise mode)

Use this to check that recognition works before trying anything else. Open
`data/sign_reference.html` to watch each sign first.

1. On the patient view, choose **One sign at a time**.
2. **Framing.** Lean back or tilt the screen so the camera sees you from the belt up. STOMACH is signed at belly height,
   and a sign outside the frame cannot be recognized.
3. Put both hands in your lap, below the bottom of the image. The status under the camera says **Ready**.
4. Sign **NO**:
   - Raise one hand to chest height. Hold your index and middle fingers out together, with the thumb under them.
   - Snap the two fingers down onto the thumb twice, like a small mouth closing.
   - Put both hands back in your lap and keep them there for 1 second.
   - The ring turns orange while you sign, then amber, and a chip **no** appears.
5. Sign **STOMACH**: hold a flat hand with the palm toward your body and pat your belly twice. Then hands back in your lap.
6. Sign **HURT**: point both index fingers at each other in front of your chest and jab them toward each other twice
   without touching. Then hands back in your lap.
7. The draft now reads **"No stomach hurt."** Press × on the **no** chip to remove it, so it reads **"Stomach hurt."**
   Then press **Confirm & send**.
   - The doctor window shows it with **✓ Confirmed by patient**.
   - If a chip is wrong, tap it and pick the right sign from the top-5 list.

Tips:
- Sign each word **once**, slowly and clearly, facing the camera.
- Always go back to your lap between words. Without that pause, two signs merge into one clip.

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

**Signing cougar.** After each final caption, the cougar mascot above the captions signs the doctor's words. Its paws,
arms, head, mouth and eyebrows follow the Deaf signers' recorded motion.
- The first time a new word is used it takes a few seconds ("Preparing signs…"). After that it is cached.
- The word being signed is shown in orange in the caption below. A word with no sign is never highlighted: the mascot
  holds still for it.
- Use **Replay** and **0.6×** to watch again slowly.
- This is word-by-word signing, not ASL grammar. The captions are the reference.

## 2. Precise mode: one sign at a time (start here, most reliable)

On the patient view, choose **One sign at a time**. For each row:
- Sign one word, then put your hands in your lap.
- A chip appears. Then sign the next word.
- Press **Confirm & send**.
- **Retry** clears the draft. Tapping a chip shows the model's top 5 so you can pick the right one. **×** removes a chip.
- The **Sign recognition On / Off** switch under the camera stops sign recognition, so stray movements are not added
  to your message. Words already added stay until you **Edit** them out or press **Retry**.

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
- Tap **Start signing** (or press Space). A 3-2-1 countdown appears over the camera.
- Sign the whole sentence at a normal pace, then tap **Done** (or press Space).
- Nothing ends the recording automatically except a 30-second limit. Low signs like STOMACH no longer stop it early.
- Three English candidates appear. Pick the right one if any, then confirm, **Edit**, or **Retry**.

**What you get:** the three **closest ER phrases** from `data/er_phrases.json`, ranked by the model, plus its own
**free translation** as a fourth option. On held-out Deaf signers, the right phrase came first 53% of the time and was
in the top 3 66% of the time. A phrase that is not in the list can never be returned. Add the phrases you need to the list.

**Why there is a phrase list: free translation is mostly wrong for ER phrases, even with perfect signing.**
This model was trained on fluent signers in news and instructional videos. It rarely saw body parts or symptoms.
When we fed it held-out videos of *Deaf signers* performing these signs, it got only HELLO right:

| Signed | Model's top output |
|---|---|
| HELLO | "Hello!" ✓ |
| STOMACH HURT | "He was heartbroken." |
| HELLO STOMACH HURT | "Hello, this is my baby who is in pain." |
| MY HEAD HURT | "I grew up in a home that had pain." |
| ME DIZZY | "I will become sick." |

On news-style sentences it does much better. For example, it translated "Will this movie beat any of the top 3 movies?"
as "Well, would that movie beat any of the three movies?"

Use the phrase list for ER replies, and one sign at a time when none of the three phrases is right.
A **Low confidence** banner means the model itself rates the result as weak.

ASL word order differs from English, so sign the gloss column.
- For signs that are not on the reference page, look them up at `https://www.signingsavvy.com/search/<word>`.

| # | Meaning | Sign (ASL gloss order) |
|---|---|---|
| 1 | My stomach hurts. | MY STOMACH HURT |
| 2 | My head hurts. | MY HEAD HURT |
| 3 | I can't breathe. | ME BREATHE CAN'T |
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
| 15 | I don't understand. | ME UNDERSTAND NOT |
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

## If a sign is recognized as the wrong word

Run `python scripts/debug_sign.py --expect HURT` (use the word you meant) and sign it once after the countdown.
- The script prints the model's top 5.
- It compares your hand tracking, spacing, height and sideways movement with Deaf signers' reference clips of the
  word you meant and of the word the model picked. The differences show what to change.
- Only landmark coordinates are saved, to `data/debug/`. No video is saved.

## If something is off

| Symptom | Try |
|---|---|
| The camera ring never turns orange | More light on your hands. Move back so both hands are fully in frame. |
| Natural signing stops too early or too late | It records only between **Start signing** and **Done** (or Space). |
| Precise mode makes a chip on every small movement | Keep your hands in your lap between signs. |
| Captions show the signer's own voice | One mic hears everyone. The signer stays silent. |
| fps well below 30 | Close other heavy apps and keep the Mac plugged in. |
