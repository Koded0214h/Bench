# Skill: Apple-style motion film

Use whenever asked for a promo, launch film, product reel, or "Apple-style" animation. Follow the PROCESS in order. The catalog at the end is a reference to pick FROM, never a list to use.

## 0. The one idea
Apple motion is restraint plus rhythm. The viewer should be able to describe the film's motion in one sentence ("things rise and settle, the camera slowly pushes in"). If they'd need a paragraph, it's wrong.

## 1. Plan before code (write this as a comment at the top of the scene file)
- **Beats**: one idea per beat. One line of copy (≤ 7 words) or one object. Never two ideas in one beat.
- **Beat timing**: enter 0.5–0.9s → HOLD ≥ 1.5s (≥ 2× the enter) → exit 0.3s. A 4s beat is: 0.7 in, 2.6 hold, 0.4 out, 0.3 black or overlap.
- **Vocabulary budget** (pick and name them, then use nothing else):
  - 1 text enter (default: Hero Reveal for headlines, Slide Up for body)
  - 1 object enter (default: Pop In with the SOFT spring)
  - 1 exit (Accelerated fade + 8px rise or 0.97 scale). Every exit is animated. Never `T >= x ? 0 : 1`.
  - 1 camera language (default: none. Otherwise ≤ 3 moves in the whole film, each ≥ 1.5s, Emphasized, motivated by content)
  - 1 signature moment (pull-back, track matte, match cut, or iris) used ONCE, at the turn or the end
- **Palette**: black or white field, one text color, ONE accent. Not two.
- **Type**: one display face, one weight for headlines. Mono/labels only if the product is technical, and never animated per-letter.

## 2. Build rules
- Animate only transform, opacity, blur. Blur only in the signature moment and for background depth (recede ≤ 8px). Never blur every enter.
- Springs: soft (≈6% overshoot) on objects. Bouncy/elastic only on ONE playful element in the whole film, never on letters or numbers.
- Stagger: letters 25–35ms, words 100–130ms, cards 60–90ms. Total stagger span ≤ 0.6s.
- Overlap: next beat's enter may start 100–150ms before the previous exit finishes. Otherwise leave 200–300ms of empty field. Both are fine; instant swaps are not.
- Ambient motion: at most one idle behaviour (breathe or float), amplitude ≤ 5% / 10px. No handheld camera noise.
- Layer styles: one per element. Shadow OR glow OR hairline, not stacked.
- Copy: ≤ 7 words per beat, one number per screen, no UI chrome (fee rows, labels, badges) unless the beat IS the UI and it's shown as a single clean card.
- Typewriter: max once per film.

## 3. Audit before delivering (answer each in the file's top comment)
1. How many distinct enter styles? (must be ≤ 2)
2. Longest run without a ≥ 1.5s hold? (must be 0)
3. How many bouncy springs? (≤ 1) How many blurred enters outside the signature moment? (0)
4. Any element that disappears without an animated exit? (0)
5. Camera moves count and are they motivated? (≤ 3)
6. Accent colors? (1)
7. Could a viewer describe the motion in one sentence?
If any answer fails, cut, don't add.

## Easing tokens
Standard `cubic-bezier(0.4,0,0.2,1)` · Emphasized `(0.2,0,0,1)` · Decelerated `(0,0,0.2,1)` enters · Accelerated `(0.4,0,1,1)` exits · Spring soft `1-e^(-5t)cos(1.8πt)` · Spring bouncy `1-e^(-6t)cos(4πt)` (rationed) · Snap `(0.3,1.3,0.6,1)` (rationed)

## Reference catalog (choose from, ≤ 3 in play)
Text: Hero Reveal (scale 1.16→1 + blur 18→0 + fade, 900ms) · Slide Up (y 36→0 per letter) · Word Stagger · Letter Stagger (y −90 + blur, hero only) · Typewriter (once).
Objects: Pop In (spring soft, scale 0.9→1) · Rise (y 44→0, Decelerated) · Iris (clip-path circle) · Blur-in (signature only).
Signature: Camera pull-back (7×→1, 1.4s Emphasized) · Track matte (scene revealed through type, scale mask 1→45× Accelerated) · Match cut (same object, same place, hard cut).
Ambient: Breathe ±5% · Float ±10px.
