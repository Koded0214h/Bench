# Story-driven product film — reusable prompt

Paste everything below the line into a Claude design project. Fill the four blanks in **Brief**. Everything else is the system that made the Veil film.

---

Make me a story-driven product film as an animated video. Use the animation engine (one continuous composition on a single clock, scene list in the timeline so I can trim, re-speed, and export), not a hand-rolled timeline. 16:9 at 1920×1080 unless I say otherwise. Full-screen: every beat fills the frame.

## Brief
- **Product:** [name — one line on what it does]
- **The old ritual:** [the painful thing people do today, in one concrete image — a piece of paper, a queue, a form, a phone call]
- **The turn:** [the one sentence that names what the product replaces it with]
- **Proof beats:** [3–5 things the product actually does, in the order you'd demo them]
- **Tagline + URL:** [tagline] · [url]
- **Brand:** [accent hex, ground (dark or light), display font, mono font]

## Structure — do not reorder
Write the film in three acts on a colour rhythm. Alternate grounds; never sit on one ground for more than ~20 seconds.

**Act 1 · The problem (light ground, ~15s).** Off-white with a warm glow of the accent. Ink type.
1. *Opener* — one line that names the old ritual. Start the camera zoomed 7× onto the key word, pull back to the whole line in 1.4s with a motion-blur peak halfway.
2. *The rules* — 4–5 short stamps, each whip-panning in from the right and out to the left, each hold shorter than the last (0.8s → 0.55s). Bottom-left, never centred.
3. *The stakes* — three lines, three different entrances: pop (spring), zoom (1.6→1 with blur), burst (scale 0.4→1 with letter-spacing 0.35em→0). Last line in the accent colour.
4. *The second wall* — the second, less obvious problem. "Say you get past that." then a mono error line types in red, then one plain sentence explaining it.

**The turn (hard cut to black, ~4s).** No crossfade. The logo mark draws on as one stroke (dashed path, offset 100→0). The wordmark letter-staggers in beneath (y −90→0, blur 12→0, 90ms apart). Tagline word-staggers. Then the accent colour floods outward *from the mark* as an expanding circle clip-path, carrying an ink copy of the wordmark inside the clipped layer so each letter changes colour exactly where the edge crosses it. Cut back to black.

**Act 2 · The product (dark ground, ~35s).** Near-black radial gradient with a breathing accent glow that parallaxes against the camera. The mark stays on screen the whole act, shrunk into the top-left corner (one element, spring-animated from centre to corner — never remount it).
5. *The key* — the product's core idea in one hero reveal (scale 1.16→1, blur 18→0, 900ms), then 3 chips popping in with spring, then one explanatory line.
6–N. *Proof beats* — one glass card per beat (rgba white 4.5%, 1px border at 10%, radius 34, shadow 0 34px 80px black 90%, inset top highlight). Each beat follows the same grammar:
   - card materialises: spring scale 0.92→1, blur 22→0, then a 15° light sweep crosses it once
   - the camera zooms 1.5× onto the field being filled, pans down to the next field, zooms back out before the confirm
   - text types itself; numbers count up with Emphasized easing; amount digits spring-bounce in one by one
   - confirmation is a **slide** control: Anticipate easing (wind-up), thumb reaches the far end and spring-settles, glow trails it
   - the card recedes (scale 0.94, blur 8, opacity 40%) and a **signing ring** draws over it (stroke-dashoffset), then a check draws in a second colour
   - one payoff move per beat: a paper plane on a cubic bezier carrying the value chip, two coins orbit-swapping places with velocity blur, a balance flipping between currencies with a squash, a value dropping in from above with a ripple
   - one closing line, word-staggered, at the bottom
   If the product has an assistant/agent, show a chat bubble typing, tool chips ticking as they complete, an approval card, and the same signing ring — with the line "The agent builds. Only you sign." (adapt).

**Act 3 · Payoff (light → dark → accent, ~15s).**
   - Iris (circle clip-path) back into the light ground for the "what this means for you" beat. Remap colours for light: text to ink, accent to its darker light-mode variant, cards to translucent white. The corner mark goes ink.
   - If Act 1 had a second wall, answer it here, in mirrored wording.
   - *Triple* — three short lines, each a zoom-in, ~0.95s apart, last one in the accent.
   - *End card* — iris to a solid accent field. Mark returns to centre (same element), wordmark, tagline, URL, one light sweep across. Fade to black over 0.8s.

## Motion system — use only these
**Easing:** Standard `cubic-bezier(.4,0,.2,1)` · Emphasized `(.2,0,0,1)` for hero moves and camera · Decelerated `(0,0,.2,1)` for enters · Accelerated `(.4,0,1,1)` for exits, ~30% faster than the enter · Snap `(.3,1.3,.6,1)` · Anticipate `(.7,-.35,.25,1.25)` for the slide control.
**Springs (JS):** soft `1−e^(−5t)·cos(1.8πt)` · bouncy `1−e^(−6t)·cos(4πt)` · elastic `1−e^(−8t)·cos(5.6πt)`.
**Durations:** micro 150–250ms · standard 300–450ms · hero 600–900ms · springs 700–900ms to settle · stagger letters 25–40ms, words 60–130ms, chips 120–150ms. Nothing on screen without motion for more than 2s; nothing holding longer than the viewer needs to read it once.
**Rules:** animate only transform, opacity, filter:blur. Blur is for hero moments and speed (motion blur proportional to velocity). Everything settles; the only loops are the ambient glow breath and the camera drift (sum of slow sines, never random). Motion implies mass — big things move slower, chips snap. One hero move per beat.

## Camera
A single virtual camera wraps the whole composition: a keyframe list of `{time, scale, x, y}` interpolated with Emphasized easing, plus a constant drift (`scale += 0.006·sin(0.33t)`, `x += 5·sin(0.21t)`, `y += 4·cos(0.17t)`). Zoom 1.5× onto fields as they fill; pan between fields; pull out to 1.0 before any confirm; push in 1.1–1.2× on payoffs. Camera moves are the transitions — avoid fades between beats inside an act.

## Continuity
- One element tree on one clock. The logo mark, the ground, and the camera persist across the whole film; everything else is `visible(from, to)`-gated and interpolated in and out.
- No black frames between scenes: the next element starts entering before the previous finishes exiting (overlap 0.2–0.4s).
- Seams: check every cut at ±0.1s for ghosts, double type, or empty frames.

## Type & copy
Display: a heavy grotesk at 800, tracking −0.035em, line-height 0.98 (Bricolage Grotesque if the brand has none). Mono for UI, labels, addresses, and errors (JetBrains Mono / Inconsolata). Wordmark in the brand's display face.
Copy is short declaratives. No jargon in the primary line — the technical words go in the mono sub-line. Keep the user's copy verbatim if given. Never say "seamless".

## Deliver
The film as a `.dc.html` on the animation engine with the scene list as named beats matching the structure above, a Motion-editor tweak, and (on request) a standalone HTML bundle with fonts and logos inlined.
