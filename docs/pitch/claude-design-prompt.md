Build a premium pitch deck for **Signwave** to the standard of a Y Combinator seed / Demo Day deck.
Format: 16:9, 1920 × 1080. 12 core slides plus 4 appendix slides. Every slide has speaker notes.
Use the attached files: the logo marks, theme.css / index.css / ui.tsx (design tokens, fonts, wordmark, icons),
README.md (facts and measured numbers) and the product screenshots.
**Name:** the product is now called **Signwave**. The code, README and screenshots still say "Medbridge", the old name.
Use "Signwave" everywhere in the deck.

---

## 1. Audience, goal, standard

- **Audience:** YC-style investors and hackathon judges, with technical and clinical backgrounds. They judge each slide in seconds.
- **Goal:** in about 3 minutes, they understand the problem, believe the product works (it is live and measured), and see why now.
- **Standard:** YC deck principles (Kevin Hale, "How to Design a Better Pitch Deck"): **legible, simple, obvious.**
  - One idea per slide. A judge must get each slide in 3 seconds.
  - **Headline test:** every headline is a full, plain sentence. Reading only the headlines, in order, tells the whole story.
  - The deck must work presented live and as a send-ahead PDF read without a speaker.
- **Visual-to-text ratio: 70 : 30 on every slide.**
  - At least 70% of the content area is visual: product screenshots, diagrams, charts, big numbers drawn as data graphics.
  - At most 30% is text. Headline at most 10 words. Body text at most 25 words per slide (footnotes and labels excluded).
  - Detail goes into the speaker notes, not onto the slide.

## 2. What Signwave is (use only these facts; do not add capabilities)

**One-liner:** Signwave lets a Deaf patient and an ER doctor talk from the first minute, live, on one laptop.

- **Doctor → patient.** The doctor speaks. The patient reads large live captions and watches a 3D cartoon cougar
  sign the words, word by word. The cougar's motion comes from recordings of Deaf signers. The word being signed is
  highlighted in the caption. The doctor can correct any caption or type a message.
- **Patient → doctor.** The patient signs one sign at a time to a webcam. The app shows the 5 closest signs. The
  patient picks, confirms and sends. A weak match shows "Not sure — pick" instead of a guess. The doctor sees only
  messages the patient confirmed, marked "✓ Confirmed by patient", and can play them aloud in a natural voice.
  The patient can also type.
- **Optional rephrasing:** Claude turns the confirmed signs into a sentence. Example: STOMACH · HURT → "My stomach hurts."
- **Private by design.** Everything runs live on one MacBook. Nothing is pre-recorded. The doctor's laptop only opens a
  web page. Audio and video stay in memory and are never saved. Speech recognition runs on the laptop by default.
- **Full-sentence signing** is built and measured but switched off until it is more accurate. Show it only as "next".
- **Position:** a research prototype, not a certified medical interpreter. Signwave is the bridge **until** the
  interpreter arrives, not a replacement for one.

**The one idea to remember:** *The doctor sees only what the patient approved.* Sign recognition makes mistakes, so
Signwave puts the patient in control of every word and shows confidence honestly.

## 3. Slide plan

For each slide: **Headline** (the sentence on the slide) · **Visual** (70%+) · **Text** (30% or less) · **Notes** (speaker notes, 2–4 sentences, about 15 s).
Text in [SQUARE BRACKETS] is a placeholder. Style every placeholder in amber (#FFB020) so we can find and replace it.

### Core

1. **Title**
   - Visual: full-bleed Ink background. Large wordmark (logo mark + "Sign*wave*"). Right half: the signing cougar [SCREENSHOT: cougar-closeup.png] on the Stage colour.
   - Text: the one-liner. Small eyebrow: "[TEAM NAMES] · [EVENT, e.g. CodeRED 2026]".
   - Notes: say the one-liner, then "Let us show you why this matters."

2. **Headline: "In the ER, most Deaf patients cannot talk to the staff."**
   - Visual: giant "28.8%" next to a 10 × 10 dot grid, 29 dots in Cougar red, the rest Bone at 15%.
   - Text: "of Deaf and hard-of-hearing patients can communicate on their own with ER staff." Two small number chips:
     "+30 min longer ER stay for Deaf ASL users, at the same acuity" and "41% of Deaf patients satisfied with video remote interpreting".
   - Footnote: Tannenbaum-Baruchi et al., Acad Emerg Med 2025 (n = 288) · James et al., Acad Emerg Med 2022 · Kushalnagar et al., JMIR Rehabil Assist Technol 2019 (n = 555).
   - Notes: open with the patient's words from the 2025 study: "Why are there no interpreters in hospitals?!" Then: 65% of these patients report communication difficulty in the ER, and only 16% of health care workers had any training for it. Today the patient relies on lip-reading, paper notes and a long wait.

3. **Headline: "Signwave gives both sides a voice from minute one."**
   - Visual: hero split screen. Left half dark (patient world): a large caption "What brought you in today?" with one word on the orange marker, and the cougar signing. Right half light (doctor world): a message card "✓ Confirmed by patient — My stomach hurts." A thin red arc (the logo's bridge) connects the halves.
   - Text: headline only, plus "Speech → captions + signing. Signing → confirmed text + voice."
   - Notes: two directions, one laptop, live.

4. **Headline: "Two directions, one laptop, under a second."**
   - Visual: a two-lane flow diagram, lanes separated by the red arc.
     - Top lane (doctor → patient): Voice → speech-to-text → live caption → cougar signs it, from Deaf signers' motion.
     - Bottom lane (patient → doctor): Webcam → hand and body tracking → top-5 signs → patient confirms → text + spoken voice.
   - Use the attached line icons (mic, hand, check, speaker, send). No stock icons, no clip art.
   - Notes: the doctor needs no app, only a web page. Audio and video never leave memory.

5. **Headline: "Built for the people in the room."** (live demo here; this slide is the backup)
   - Visual: two framed screenshots side by side: [SCREENSHOT: patient-view.png] (dark) and [SCREENSHOT: doctor-view.png] (light). Add 3–4 thin callout lines per screenshot.
     - Patient callouts: "Huge live captions", "Word being signed", "Top-5 sign picker", "Confirm & send".
     - Doctor callouts: "Only confirmed messages", "Click a caption to correct it", "Type to the patient", "Play aloud".
   - Notes: walk the demo exchange: Doctor: "On a scale of one to ten, how bad is the pain?" → patient signs SEVEN → confirms → doctor sees "✓ Confirmed by patient".

6. **Headline: "The doctor sees only what the patient approved."** (our insight)
   - Visual: a 4-step horizontal sequence with small UI crops: patient signs → 5 candidates (one shows "Not sure — pick" in amber) → patient taps the right one → doctor card "✓ Confirmed by patient". Use [SCREENSHOT: patient-confirm.png] for the middle step.
   - Text: "AI makes mistakes. The patient catches them, not the doctor."
   - Notes: unconfirmed AI output never reaches the doctor. Weak matches say so. The doctor can fix any caption. This is what makes AI usable in an ER.

7. **Headline: "It works today, measured on Deaf signers it never saw."** (traction)
   - Visual: 4 big-number tiles in a row (number in Instrument Serif, label in IBM Plex Mono):
     - **86%** first-guess accuracy on ER signs (98.5% in the top 5)
     - **129** ER signs: yes/no, pain scale, body parts, symptoms, medicine
     - **1.5%** word error rate on doctor speech, with 100% of medical terms right
     - **30 fps** live tracking on a MacBook, under 1 s from speech to caption
   - Footnote: Held-out test data, our live pipeline code. Signs: 339 held-out clips of the first 103 ER signs. On all 2,731 signs: 60.7% top-1, above the published 59.5%. Speech: 20 ER sentences × 4 synthetic voices. Caption: 358 ms compute + 600 ms end-of-speech wait.
   - Notes: [BUILT IN N HOURS]. Every number comes from our own evaluation scripts, not from the papers.

8. **Headline: "Sign AI just became real, but not for the ER."** (why now)
   - Visual: a horizontal timeline, 2023 → 2026, with a red "Now" marker at Oct 2026:
     - 2023 · ASL Citizen: open dataset from 52 Deaf signers (Microsoft, NeurIPS)
     - May 2024 · ACA §1557 final rule: providers must ensure effective communication; quality standards for video interpreting
     - 2025 · Uni-Sign (ICLR): best open continuous sign model. Google announces SignGemma (still unreleased)
     - 2026 · JAMA Netw Open trial: video interpreting alone does not fix Deaf patient communication
     - Aug 2026 · Google DeepMind ships SL2T sign-to-text on Pixel 11: one-way, consumer, no clinical workflow
   - Small side panel: "General video AI still fails at ASL: BLEU 1.4 (Gemini 2.5 Pro), 0.1 (GPT-5) on How2Sign. [SOURCE]"
   - Notes: the models are finally good enough and run on a laptop. Hospitals are under pressure to communicate. Nobody has built the clinical, two-way, patient-verified product.

9. **Headline: "Every ER in the US needs this on day one."** (market)
   - Visual: a bottom-up market diagram: **155M** US ER visits per year → **[N] US emergency departments** × **[$ PER ED PER YEAR]** = **[$ MARKET]**. Show the sourced numbers solid and the placeholders in amber.
   - Side note: "250,000–500,000 ASL users in the US (dated estimate)."
   - Expansion row of small chips: urgent care · EMS · pharmacy · inpatient · other sign languages.
   - Footnote: CDC NHAMCS 2022 · Mitchell et al., Sign Language Studies 2006 · [SOURCE FOR ED COUNT AND PRICE].
   - Notes: do not invent market numbers. Keep the placeholders visible until we add sourced figures.

10. **Headline: "Nothing else is two-way, instant and patient-verified."** (competition)
    - Visual: a comparison table with check, partial and cross marks. Rows: On-site interpreter · Video remote interpreting · Paper notes / lip-reading · Google SL2T (Pixel 11) · General video AI · **Signwave** (highlighted row).
      Columns: Available in minute one · Signs back to the patient · Patient approves each message · Built for the ER · Private (on device).
    - Be fair. The on-site interpreter is the gold standard for quality; say so in the notes. Do not claim a competitor lacks something it has.
    - Notes: we complement interpreters. We cover the gap before they arrive and the moments they are not there.

11. **Headline: "Next: full sentences, more signs, a hospital pilot."** (business model + roadmap)
    - Visual, left: a 3-step roadmap track: Today (129 signs, one at a time) → Next (full-sentence signing, right phrase already in the top 3 66% of the time; bigger vocabulary; fingerspelling) → Pilot (partner ED, Deaf advisory board, certified interpreters reviewing safety).
    - Visual, right: business model as one simple card, labelled "Hypothesis": per-ED annual licence on a hospital laptop or tablet + webcam. Buyer: language access / patient experience. [PRICE]
    - Notes: we will build this with Deaf patients and interpreters, not around them.

12. **Headline: "Every word the doctor sees, the patient approved."** (team + ask + close)
    - Visual: team photos in a row [TEAM PHOTOS] with name, role and one credential each [TEAM DETAILS]. Wordmark and a QR code to [DEMO / REPO LINK].
    - Text: "[ASK, e.g. a pilot ED partner, Deaf community advisors, $X pre-seed]". "Thank you."
    - Notes: restate the one-liner and the ask.

### Appendix (for Q&A)

- **A1. Honest limits and safety.** Not a certified medical interpreter. Recognizes only signs in its vocabulary. Cannot reliably read fingerspelling. No diagnosis or clinical decision support. Every patient message is confirmed by the patient.
- **A2. Architecture and privacy.** Diagram: camera → pose tracking → sign model (ASL Citizen ST-GCN) → candidates; microphone → voice detection → Whisper (on device) → captions → sign lookup (Deaf signers' motion) → cougar. All on one MacBook. Optional cloud calls, each one off by default or opt-in: ElevenLabs (speech-to-text and the patient's voice), sign.mt (only words missing from the local sign dictionary), Claude (rephrasing sign labels).
- **A3. How we measured.** A clean table of the README "Measured results" numbers with test set, size and the published comparison.
- **A4. References.** Full citations (below), small type, two columns.

## 4. Design system (from the app's default "classic" theme)

**Concept:** the deck crosses the bridge. Dark slides are the patient's world (the patient screen is dark). Light slides
are the doctor's world (the clinician screen is light). Cougar red is the bridge between them. Alternate dark and light
with intent: problem and patient slides dark; product, data and business slides light. Look: premium, hospital-grade, calm.
**Not** "AI startup".

**Colour**

| Role | Hex | Use |
|---|---|---|
| Ink | `#0E0F0C` | dark slide background |
| Ink raised | `#171813` | cards and panels on dark |
| Stage | `#17140F` | behind the cougar |
| Bone | `#F2EEE6` | text on dark; secondary text = Bone at 55% |
| Paper | `#F4F1EA` | light slide background |
| Paper raised | `#FBFAF6` | cards on light |
| Graphite | `#14150F` | text on light; secondary text = Graphite at 55% |
| Cougar red | `#C8102E` | the only accent: logo arc, key numbers, highlighted row, primary button, "Confirmed" mark |
| On red | `#FFF7F2` | text on red |
| Blush | `#F7E4E2` | patient message bubbles on light slides |
| Signal orange | `#D9480F` | marker behind the word being signed; use once or twice in the deck |
| Amber | `#FFB020` | "Not sure", warnings, and placeholders only |
| Hairline | Bone or Graphite at 10% | 1 px dividers and card borders |

- Contrast: red on Paper passes AA for any size. Red on Ink is only 3.3 : 1, so on dark slides use red only for large display numbers (60 px+) and graphics, never small text.
- One accent per slide. No gradients except the subtle film grain.
- Mascot colours, only for tiny accents if needed: fur `#C98F55`, cream `#F4E4C9`, markings `#3B2416`, iris gold `#E0A82E`.

**Type** (all on Google Fonts)

- Display: **Instrument Serif** 400, tracking −1%. Headlines 72–96 px. Big numbers 180–240 px. Italicize one key word per headline at most, as in the wordmark "Sign*wave*".
- Body: **Atkinson Hyperlegible Next** 400 / 700, 28–32 px. (A typeface designed for low-vision readers. It fits an accessibility product.)
- Labels and data: **IBM Plex Mono** 400 / 500. Eyebrow labels 18–20 px, UPPERCASE, letter-spacing 0.14em, 55% opacity. Footnotes 16–18 px.
- Minimum text size 16 px (footnotes); everything else 24 px or more.

**Layout**

- 12-column grid, 120 px outer margins, 24 px gutters, 8 px spacing unit. Left-aligned text. Generous empty space.
- Slide number bottom right in Plex Mono; small logo mark bottom left; nothing else in the margins.
- Corners: buttons and chips 6 px (squared, not pills). Cards and screenshot frames 16–24 px.
- Screenshots: 1 px hairline frame, 16 px radius. Soft shadow on light slides only. Never stretch or recolour them.

**Motifs from the product**

- The **logo mark**: a red arc (the bridge) over five pillars. Reuse a thin red arc to link the dark and light halves (slides 3, 4).
- **Status line:** an 8 px dot + an uppercase mono label, e.g. "● LISTENING TO DOCTOR".
- **Waveform:** 36 thin rounded bars, opacity fading from 35% to 100% left to right.
- **Caption marker:** a Signal-orange block behind one word of a large caption.
- **Film grain** on dark slides: fractal noise at about 4.5% opacity.
- **Icons:** the line icons in ui.tsx (24 px grid, 1.8 px stroke, round caps and joins). Make any new icon in the same style.

**Data visuals:** big-number tiles, dot grids, one-line timelines, and simple tables. No pie charts, no 3D charts, no gridline clutter. Label data directly; no legends. Show the source under every number.

## 5. Writing rules

- Write "Deaf" with a capital D. Never "hearing-impaired", "deaf-mute" or "suffers from deafness".
- Plain, confident, short sentences. No "AI-powered", "revolutionary", "breaking barriers", "seamless", "game-changing".
- Never invent numbers, quotes, customers, partners, logos or testimonials. If something is missing, use a [PLACEHOLDER].
- Every statistic has a short source footnote on the same slide.
- Do not draw the cougar. Use crops of the provided screenshots. Do not recreate the University of Houston logo.
- No stock photos of doctors or hospitals. No purple or blue gradients, glassmorphism, glowing blobs, sparkle icons or emoji.

## 6. Quality check before you finish

- [ ] Each slide: visual area 70%+, body text 25 words or fewer, headline 10 words or fewer.
- [ ] Headline test: the 12 headlines alone tell the story.
- [ ] Every number has a source; every placeholder is amber.
- [ ] Text contrast WCAG AA; nothing below 16 px; meaning never shown by colour alone (use ✓ and labels too).
- [ ] Same margins, grid, type sizes and slide-number position on every slide.
- [ ] Speaker notes on every slide; core slides total about 3 minutes.
- [ ] Exports cleanly to PDF.

## 7. References (for A4 and the footnotes)

1. Tannenbaum-Baruchi C, Feder-Bubis P, Aharonson-Daniel L. Communication barriers to optimal access to emergency rooms according to deaf and hard-of-hearing patients and health care workers: a mixed-methods study. *Acad Emerg Med.* 2025;32(3):246–259. doi:10.1111/acem.15037
2. James TG, et al. Emergency department condition acuity, length of stay, and revisits among deaf and hard-of-hearing patients: a retrospective chart review. *Acad Emerg Med.* 2022. doi:10.1111/acem.14573
3. James TG, Coady KA, Stacciarini JR, et al. "They're not willing to accommodate Deaf patients": communication experiences of Deaf American Sign Language users in the emergency department. *Qual Health Res.* 2022.
4. Kushalnagar P, Paludneviciene R, Kushalnagar R. Video remote interpreting technology in health care: cross-sectional study of Deaf patients' experiences. *JMIR Rehabil Assist Technol.* 2019;6(1):e13233.
5. Rivas Velarde M, et al. Video remote sign language interpreting and health communication for Deaf patients: a randomized clinical trial. *JAMA Netw Open.* 2026. doi:10.1001/jamanetworkopen.2025.57189
6. Centers for Disease Control and Prevention, NCHS. National Hospital Ambulatory Medical Care Survey: 2022 emergency department summary (155 million visits).
7. Mitchell RE, Young TA, Bachleda B, Karchmer MA. How many people use ASL in the United States? Why estimates need updating. *Sign Lang Stud.* 2006;6(3):306–335.
8. US Department of Health and Human Services. Nondiscrimination in Health Programs and Activities (ACA §1557), final rule. *Federal Register*, May 6, 2024.
9. Google DeepMind. Putting sign language AI into users' hands (SL2T). Aug 12, 2026.
10. Desai A, et al. ASL Citizen: a community-sourced dataset for advancing isolated sign language recognition. NeurIPS 2023 Datasets & Benchmarks.
11. Li Z, et al. Uni-Sign: toward unified sign language understanding at scale. ICLR 2025.
