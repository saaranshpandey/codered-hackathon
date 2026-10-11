# Devpost submission: SignWave

Paste each part into the matching Devpost field.

---

## Project name

SignWave

## Elevator pitch

A Deaf patient and an ER doctor can talk from the first minute. The doctor speaks and a 3D cougar signs it. The patient signs back and approves every word before the doctor sees it.

---

## About the project

## Inspiration

Imagine walking into an emergency room in pain, and nobody there speaks your language. For a lot of Deaf patients, that is just a normal ER visit.

A 2025 study in Academic Emergency Medicine looked at Deaf and hard of hearing patients. Only about 29% of them could communicate on their own with ER staff. Deaf ASL users also stay around 30 minutes longer in the ER than other patients who are just as sick. Hospitals do have video interpreting. But it takes time to set up, and in one survey only 41% of Deaf patients were satisfied with it.

We kept thinking about those first few minutes, before an interpreter shows up. We didn't want to replace interpreters. We wanted something that works right away, while everyone waits.

## What it does

SignWave runs on one MacBook and works in both directions.

When the doctor talks, the patient sees big live captions. Above them, a cartoon cougar in a UH jersey signs the doctor's words, one word at a time. The word being signed lights up in the caption. If a caption is wrong, the doctor can click it and fix it, or just type.

When the patient signs, the app reads one sign at a time from the webcam. The patient lowers their hands between signs, and the words build up into a message. They can edit it or start over. Nothing goes to the doctor until the patient taps Confirm & send. On the doctor's screen, the message shows up marked as confirmed by the patient. The doctor can also play it out loud in a natural voice.

That last part matters most to us. Sign recognition makes mistakes. The doctor can't check ASL, but the patient can. So the patient approves every word.

The doctor doesn't install anything. They just open a web page, on the same laptop or on their own.

## How we built it

The backend is Python with FastAPI. It owns the camera and the mic, and it pushes everything to two web pages over websockets. The frontend is React, with Three.js for the 3D cougar.

For the doctor's speech, we use ElevenLabs. Silero VAD listens on the laptop and cuts the audio into sentences. Each finished sentence goes to ElevenLabs Scribe v2 for the caption, along with a list of ER terms so it gets drug names right. When the patient sends a message, ElevenLabs Flash v2.5 reads it out loud to the doctor.

For the patient's signing, MediaPipe tracks the hands, face and body. Each sign goes into the model from Microsoft's ASL Citizen project. It was trained on webcam videos from 52 Deaf and hard of hearing signers, and it knows 2,731 signs. We narrowed it down to 129 signs that matter in an ER: yes, no, the pain scale, body parts, symptoms, family and medicine. That made it a lot more accurate.

The cougar was the fun part. We didn't animate anything by hand, and nothing is generated. For each word, we pull a real video of a Deaf signer from ASL Citizen. MediaPipe tracks 178 points on the body, face and hands in every frame. Then we pose the cougar directly on those points. Each finger is a small cylinder between two tracked joints, so the handshape is the signer's own. The jaw, eyebrows and eyelids follow the signer's face too. We blend each sign into the next so the motion flows, and we cache the results so common words play right away. Words that aren't in the dataset, like most drug names, come from the open sign.mt project, which usually fingerspells them.

Claude can turn the signs into a proper sentence if you switch it on. STOMACH HURT becomes "My stomach hurts." The patient still sees that sentence before sending it.

## Challenges we ran into

Full sentence translation was our big heartbreak. We got a sentence level research model running live, and it did fine on news clips. Then we gave it videos of Deaf signers signing STOMACH HURT, and it said "He was heartbroken." It had barely seen any medical signing. Even when we gave it a list of ER phrases to choose from, it picked the right one first only 53% of the time. So we switched it off and went with one sign at a time, which gets it right 86% of the time. Shipping the less flashy version was the right call.

Turning the doctor's words into signing was slow at first. Four new words took over 30 seconds. Part of that was a bug. Our clip quality check counted the resting frames before and after each sign, so almost every clip failed and we processed two more. We fixed the check, fetched signs in parallel, and started fetching while the doctor was still talking. Now four new words take about 4.5 seconds, and words we've seen before start right away.

The room itself was a challenge. It's loud and full of people talking. We found that the voice detector treats faint speech from across the room as speech. Captions stayed open for several seconds and picked up other people's words. So we added a loudness gate. Quiet sound from farther away now counts as silence, and a caption closes about half a second after the doctor stops.

Small details mattered more than we expected. The sign model only works if its input is prepared exactly the way it was in training. That includes one step that honestly looks like a bug. We copied the original code line by line and wrote tests that compare our version against it.

## Accomplishments that we're proud of

A doctor asks "Are you in pain?" out loud. About a second later, the words are on the patient's screen and the cougar is signing them. The patient signs back STOMACH, then HURT, reads the message and taps send. The doctor sees "Stomach hurt." with a check mark showing the patient confirmed it. That whole loop works live on one MacBook, and getting it there is what we're proudest of.

We didn't want to lean on numbers from papers. So we tested our own pipeline on Deaf signers the model had never seen. On ER signs, its first guess is right 86% of the time, and the right sign is in its top five 98.5% of the time. On all 2,731 signs it scored 60.7%, a bit above the 59.5% in Microsoft's paper. That told us we had rebuilt their model correctly.

On the speech side, ElevenLabs Scribe got a 0.9% word error rate on our ER sentences, and it got every medical term right. Those were synthetic voices, so we expect a real, noisy ER to be harder.

We're proud of the cougar too. Every sign it makes is a real Deaf signer's recorded motion. We track that motion with MediaPipe and pose the cougar on it in Three.js, with no hand animation at all. Meanwhile, the camera side keeps up at 30 frames per second on a laptop.

And we kept it private. Audio and video stay in memory and are never saved, and the camera video never leaves the laptop.

## What we learned

General video AI can't read ASL yet. Published results put it around 1 BLEU on ASL, which is close to nothing. Models trained on Deaf signers are still the way to go.

A small system that is honest beats a big one that guesses. In an ER, 129 words that work are more useful than thousands that don't.

Sign language is much more than hands. Facial expressions and word order carry a lot of the grammar. Our cougar signs word by word in English order, and we learned how much that leaves out.

And the person who knows what they meant should be the one who checks it.

## What's next for SignWave

First, we want to put it in front of Deaf users and ASL interpreters and listen to what they tell us.

After that, we want to test speech recognition with real voices and real ER noise. We want to train the sentence model on ER phrases so we can turn it back on. We also want to add fingerspelling for names and drug names, and teach the cougar ASL word order and facial grammar. Longer term, we'd love to pilot SignWave in a real emergency department with a Deaf advisory group.

SignWave is a research prototype. It is not a certified medical interpreter, and a qualified interpreter is still the right choice for care. We see it as something that helps until that interpreter arrives.

---

## Built with

Python, FastAPI, PyTorch, MediaPipe, Silero VAD, ASL Citizen, sign.mt, React, TypeScript, Three.js, Tailwind CSS, Vite, WebSockets, Claude, ElevenLabs

## Links

GitHub: https://github.com/saaranshpandey/codered-hackathon

Demo video: add your link here

---

## Did you implement a generative AI model or API in your hack this weekend?

Yes. We used three generative AI APIs, each for one narrow job.

Claude (Haiku 4.5) turns the patient's signs into a sentence. The sign model gives us labels like STOMACH and HURT, which read as "Stomach hurt." Claude rewrites that as "My stomach hurts." We kept it on a short leash. The prompt tells it never to add symptoms, body parts, times or amounts. It gets 60 tokens and 3 seconds. If anything fails, the app shows the plain labels instead. Most important, the patient reads the sentence and approves it before the doctor sees it.

ElevenLabs Scribe v2 turns the doctor's speech into captions. We send it a list of ER terms so it spells drug names right. On our test sentences it had a 0.9% word error rate and got every medical term right.

ElevenLabs Flash v2.5 reads each confirmed patient message out loud. That way the doctor hears the patient's words without having to read the screen. We mute the mic while it plays, so the app never captions its own voice.

We were just as careful about where not to use generative AI. The signing cougar never makes up motion. Every sign it shows is a real Deaf signer's recording. We also tried a sentence level translation model, but it invented meanings. It read STOMACH HURT as "He was heartbroken." So we switched it off.
