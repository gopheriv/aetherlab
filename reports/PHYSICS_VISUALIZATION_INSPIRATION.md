# Physics Visualization: Research and Inspiration for New AetherLab Videos

**Written:** 26 September 2026
**Context:** The v1 review pack scored 8/10 ("missing more details and explanation"). F216 added intro and closing explanation cards, and the v2 pack scored 9/10. This report asks what the next point would come from. It covers learning-science evidence, the working methods of the best physics visualizers, and a ranked list of new video ideas that fit AetherLab's numeric-first architecture.

---

## TL;DR

**Five techniques with the strongest evidence, in priority order:**

1. **Explain *during* the animation, next to the thing being explained.** Temporal and spatial contiguity have the largest effects in the multimedia literature. F216 explains before and after the animation, not during it. This is the gap between 9/10 and 10/10.
2. **Ask a prediction before the reveal.** Students who only watch a demonstration learn no more than students who never saw it. Students who predict first learn significantly more.
3. **Confront the misconception on screen.** Clear expository videos can *increase* confidence in a wrong idea. Dialogue that addresses the misconception outperformed exposition (d = 0.71).
4. **Signal and segment.** Highlight what matters at the moment it matters (g ≈ 0.38), and give each idea its own beat (g ≈ 0.32–0.36).
5. **Put the explanation in narration rather than on-screen text** (modality principle). AetherLab's AI scenes are designed this way already, but `narration_enabled` is off.

**Ten new video ideas** (details in §5): projectile motion with and without air drag; cutting the string in circular motion; Doppler effect and the Mach cone; driven resonance; the rolling race; the special-relativity light clock; a charged particle in a magnetic field; "slow down to catch up" in orbit; quantum tunnelling; heat diffusion.

---

## 1. What the research says

### Animation helps only when it shows the change that matters
- A meta-analysis of 26 studies (76 comparisons) found a medium advantage for instructional animation over static pictures, **d = 0.37**. The advantage was larger when the animation was *representational* rather than decorative (d = 0.40) and when it was realistic (d = 0.76). [Höffler & Leutner 2007](https://www.sciencedirect.com/science/article/abs/pii/S0959475207001077)
- Tversky, Morrison and Bétrancourt explain why many animations fail. Two principles decide it:
  - **Congruence:** change over time should correspond to the concept being taught.
  - **Apprehension:** the change must be slow and simple enough to perceive.

  "Animations are often too complex or too fast to be accurately perceived." [Tversky et al. 2002](https://hci.stanford.edu/courses/cs448b/papers/Tversky_AnimationFacilitate_IJHCS02.pdf)

**For AetherLab:** the curated components already pass the congruence test, because the motion *is* the physics (numeric solve). Apprehension is the weak spot. Several components run the whole phenomenon in one continuous 6–8 s `play()`, with no slow-motion and no pauses at the key moment.

### Contiguity, signaling and segmenting are the proven design levers
- An overview of 29 reviews (1,189 studies, 78,177 participants) found 11 principles with significant positive effects. The largest were **temporal/spatial contiguity** and **signaling**, followed by modality, animation, coherence (remove decoration), segmenting and personalization. [Noetel et al. 2022](https://journals.sagepub.com/doi/abs/10.3102/00346543211052329)
- Reported effect sizes include signaling/cueing **g = 0.38** and segmenting **g = 0.32–0.36**. A 2025 meta-analysis looked for the boundary conditions across media types. [Mayer meta-analysis 2025](https://www.sciencedirect.com/science/article/pii/S1747938X25000673), [principle summary](https://www.digitallearninginstitute.com/blog/mayers-principles-multimedia-learning)

**For AetherLab:**
- **Contiguity:** a label should appear *next to* the object *when* it matters, for example "period = 2.10 s" beside the bob as it completes its first swing, not on a card 15 s later.
- **Signaling:** Manim already has the tools (`Indicate`, `Circumscribe`, `Flash`, `FocusOn`). Only the orbit component uses any of them.
- **Modality:** spoken explanation beats the same words as screen text. This is the strongest argument for turning narration on once it passes the listening review.

### Prediction before the reveal
- Harvard's controlled study of classroom demonstrations found that students who passively watched understood the concept **no better than students who did not see the demonstration at all**. Students who **predicted the outcome first** showed significantly greater understanding. [Crouch, Fagen, Callan & Mazur 2004](https://mazur.harvard.edu/publications/classroom-demonstrations-learning-tools-or-entertainment)

**For AetherLab:** a video can't collect an answer, but it can pose the question and pause. An example card: "Double the mass. Does the period go up, down, or stay the same? (3 s pause)". Learn mode already has prediction questions, and this carries the same move into Solve-mode videos.

### Confront the misconception
- Derek Muller's PhD research (the author of Veritasium) found that **clear expository physics videos can reinforce misconceptions and raise confidence in them**. A version built on dialogue that raised and resolved the misconception produced a significant advantage, **d = 0.71**. [Muller 2008 thesis](https://www.academia.edu/18111353/PhD_Muller_Designing_effective_multimedia_for_physics_education), [summary](https://eric.ed.gov/?id=EJ1211253)
- Well-documented misconceptions (Force Concept Inventory research): "motion implies force", impetus in projectile motion, and a real "centrifugal force" in circular motion. [FCI misconception structure](https://arxiv.org/pdf/1905.06176), [circular motion](https://link.aps.org/doi/10.1103/PhysRevPhysEducRes.16.010134)

**For AetherLab:** each component should carry one named misconception and show it failing. The explanation layer from F216 is already the right place for that content.

### Several representations of one physics
- Van Heuvelen's method pairs the picture with **motion diagrams, force diagrams and energy bar charts**. Students reason qualitatively first and do the maths second. [Multiple representations](https://arxiv.org/pdf/1207.0217), [energy bar charts](https://www.researchgate.net/publication/243492287_Multiple_representations_of_work-energy_processes)
- PhET's "implicit scaffolding" came from 125 sims and 600+ student interviews. It shows the expert model in several linked representations, so cause and effect stay visible. [PhET implicit scaffolding](https://arxiv.org/pdf/1306.6544)

**For AetherLab:** a live **KE/PE bar chart** beside the pendulum, or two energy bars beside the coupled oscillators, would make "energy moves from one mass to the other" something the viewer can *see*. Today it is only stated on the closing card.

---

## 2. What the best physics visualizers do

| Creator | Signature techniques worth copying |
|---|---|
| **3Blue1Brown** (Grant Sanderson; built Manim) | Every movement has a purpose, and visuals say the same thing as the narration. Analysts of his style list **live values** that update with parameters, **density ramps** (visual complexity grows with the concept), **one anchor diagram that never leaves the scene**, and a **reserved caption zone** in the bottom ~20% of the frame. [How he animates](https://3blue1brown.substack.com/p/how-i-animate-3blue1brown), [principles analysis](https://www.clawrxiv.io/abs/2603.00083) |
| **Bartosz Ciechanowski** ([ciechanow.ski](https://ciechanow.ski/)) | Starts with a much simpler object before the real system, and builds intuition in steps. The interactives do the heavy lifting. Topics: Moon, Airfoil, Bicycle, Sound, Mechanical Watch, GPS, Naval Architecture, Internal Combustion Engine, Cameras and Lenses, Lights and Shadows, Gears, Earth and Sun. [archive](https://ciechanow.ski/archives/) |
| **Veritasium / Steve Mould** | One central question or counterintuitive phenomenon. The order is: set up the experiment, observe, then explain. The misconception is exposed on camera. [Mould](https://en.wikipedia.org/wiki/Steve_Mould), [Muller](https://en.wikipedia.org/wiki/Derek_Muller) |
| **PhET / Falstad** | Live parameter control. Falstad's ripple tank shows interference, diffraction, refraction, resonance, phased arrays and the Doppler effect with one 2-D wave solver. [Falstad ripple tank](https://www.falstad.com/ripple/), [PhET research](https://phet.colorado.edu/en/research) |
| **Bret Victor** | "Up and down the ladder of abstraction": show one concrete run, then the **family** of runs across a parameter, then the abstract relationship. He coined "explorable explanations". [Ladder of abstraction](https://notes.andymatuschak.org/zT6QcspwtJ55KAasV5jHwjJ), [explorables](https://en.wikipedia.org/wiki/Explorable_explanation) |

**Common pattern:** start with a question, build from simple to real, keep one anchor picture on screen, show the numbers living inside the picture, and pay off the question at the end.

---

## 3. Where AetherLab stands (after F216)

| Evidence-backed technique | Current state |
|---|---|
| Congruent, physics-true motion | ✅ curated components animate the numeric solve |
| Explanation text | ✅ intro and closing cards (F216), but ⚠ not *during* the animation |
| Live values in the picture | ⚠ AI prompt requires `DecimalNumber` readouts; none of the 15 curated components has one |
| Signaling (highlight at the right moment) | ⚠ only 1 of 15 curated components (orbit) uses `Indicate`/`Circumscribe`/`Flash`/`FocusOn` |
| Segmenting / pacing the key moment | ⚠ often one long continuous `play()`; no slow-motion |
| Prediction before reveal | ❌ not in videos (Learn mode has questions) |
| Misconception confronted on screen | ❌ not in videos |
| Multiple representations (energy bars, force arrows) | ⚠ time-series plots only; no energy bars or free-body arrows |
| Anchor diagram persists | ❌ the closing card clears the stage (`FadeOut(*self.mobjects)`) |
| Narration (modality principle) | ⚠ built and timed, but off in saved settings pending a listening review |
| Parameter family / ladder of abstraction | ❌ one run per video |

---

## 4. Techniques to build next

Each item is small, reuses the existing curated-component architecture, and can be proved with the review pack.

1. **Beat captions during the animation (contiguity plus signaling).** Components expose 2–4 timed "moments", for example `(t=2.1 s, "first full swing: 2.10 s", anchor=bob)`. A shared helper shows a short label beside the anchor at that time and fires `Indicate`/`Flash` on it. Captions go in a reserved bottom band so they never collide with the physics.
2. **A prediction card.** The intro gains a question and a 3 s pause. The closing card answers it. Per component: pendulum "double the mass: does the period change?"; orbit "where is the planet fastest?"; lens "move the object closer: bigger or smaller image?".
3. **A misconception beat.** Each explanation gets one `misconception` entry, shown as "Common idea: … / What actually happens: …". Where cheap, animate it: two pendulums with different masses swinging in lockstep.
4. **Keep the anchor.** Instead of clearing the stage for the closing card, shrink the final animation frame into a corner thumbnail (`scale(0.35).to_corner(UL)`), so the explanation sits next to the picture it explains.
5. **Energy bars and force arrows.** A reusable `EnergyBars` helper driven by the same sampled solution, for KE/PE on the pendulum and orbit, and energy per mass for coupled oscillators. Free-body arrows for projectile and circular motion.
6. **Ghost comparison.** Draw the approximation or the misconception as a translucent ghost next to the true motion: small-angle vs real pendulum, no-drag vs drag projectile, Newtonian vs relativistic.
7. **Slow-motion at the key moment.** Show a "×0.25 speed" badge and slow the `ValueTracker` rate for the interval that carries the insight (the orbit's perihelion pass, or the moment the string is cut).
8. **Turn narration on** once the pending normal-speed listening review of the Planck sample passes. This is the only item that needs no code.

---

## 5. New video ideas (inspiration)

Ranked by teaching value × fit with AetherLab. All except the last group can be driven by `solve_numeric` or a closed form, and can stay LaTeX-free like the existing components.

| # | Video | Hook / misconception confronted | Model | Fit |
|---|---|---|---|---|
| 1 | **Projectile: vacuum vs air drag** | Impetus: "the ball keeps a forward force". Show constant horizontal velocity, then the ghost with drag landing short; the optimal angle drops below 45°. | 4-state ODE with quadratic drag | ★★★ easy |
| 2 | **Cut the string** (circular motion) | "Centrifugal force throws it outward." Cut the string mid-orbit: the ball leaves on the **tangent**, not radially. | Uniform circular motion, then free flight | ★★★ easy |
| 3 | **Doppler effect and Mach cone** | Why a passing siren changes pitch. Wavefront circles emitted by a moving source bunch up ahead, stretch behind, and form a cone when v > c. | Closed form (circles from source positions) | ★★★ easy |
| 4 | **Driven resonance** | "Push harder and it always swings more." Sweep the drive frequency: amplitude peaks at ω₀, and phase lag goes 0 → 90° → 180°. | Driven damped ODE plus an amplitude-response curve | ★★★ easy |
| 5 | **The rolling race** (hoop, disc, sphere) | "Heavier rolls faster." Mass and radius cancel; only the shape (I/mr²) decides the winner. | Closed form a = g·sinθ/(1+I/mr²) | ★★★ easy |
| 6 | **Light clock: time dilation** | "Time is absolute." The same photon bounce seen from a moving frame traces a longer diagonal, so the clock ticks slower by γ. | Closed form, with a γ readout | ★★★ easy |
| 7 | **Charged particle in a magnetic field** | "The magnetic force speeds it up." The force is always perpendicular, so the speed is constant: a circle, and a helix with a parallel component. | Lorentz-force ODE | ★★☆ medium (helix needs 3-D) |
| 8 | **Slow down to catch up** (orbital rendezvous) | "Fire forward to catch the station ahead." Burning retrograde drops to a faster, lower orbit. | Reuses the orbit component's two-body solve | ★★☆ medium |
| 9 | **Quantum tunnelling** | "A particle can't cross a barrier higher than its energy." The packet splits; the transmitted fraction depends on barrier width. | 1-D split-step Schrödinger (numpy FFT) | ★★☆ medium |
| 10 | **Heat diffusion along a rod** | "Heat flows at a fixed speed." A colour-mapped rod spreads as √t; the Fourier modes decay at different rates. | 1-D heat PDE (explicit stencil) | ★★☆ medium |
| 11 | Snell's law and total internal reflection | A fibre-optic "light pipe" and the critical angle. | Closed form | ★★☆ |
| 12 | Ripple tank: interference, diffraction, beats | Generalises the double-slit to N sources and a single slit (Falstad style). | 2-D wave superposition | ★★☆ |
| 13 | Carnot / PV cycle with a piston | Why no engine is 100% efficient. | Closed form | ★★☆ |
| 14 | Lorenz attractor / logistic map | Chaos beyond the double pendulum. | ODE / map | ★★☆ (Lorenz needs 3-D) |
| 15 | Airfoil and the "equal transit time" myth | A classic wrong explanation of lift ([Ciechanowski, Airfoil](https://ciechanow.ski/archives/)). | Needs a flow field | ★☆☆ hard |
| 16 | Gyroscope precession | Why it doesn't fall. | 3-D rigid body | ★☆☆ hard |

**Suggested first batch:** #1, #2, #4 and #6. Each confronts a textbook misconception, is cheap to build as a numeric-driven component, and shows off a technique from §4 (ghost comparison, cut moment in slow-motion, parameter sweep, prediction card).

---

## 6. How to prove the next step

Use the same method that took the pack from 8/10 to 9/10:

1. Build the §4 techniques 1–4 into the shared explanation layer, so all 14 components benefit at once.
2. Render **review pack v3** through Cloud with a before/after proof video against v2.
3. Rate **per axis** this time (legibility, physics, pacing, teaching value) so `tools/human_review_analysis.py` can compute agreement with the vision critic. An overall score moves the product, but it can't calibrate the critic.

**Caveat:** the effect sizes above come from general multimedia and physics-education studies, not from AetherLab videos. They show which levers are worth testing, not what AetherLab's gain will be. Measure that with the review pack before claiming it.
