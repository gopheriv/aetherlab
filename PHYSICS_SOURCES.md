# University Physics — Reference Book Sources for AetherLab RAG

Researched, license-checked sources of university-level physics texts to enrich
the ChromaDB reference database. Two ways to load any of these into AetherLab:

- **Auto-download** — OpenStax only (CC BY 4.0, stable CMS URLs) via
  Library → **Get starter library**. See `aetherlab/services/starter_library.py`.
- **Add folder** — download any PDF below yourself, then Library →
  **Add folder** (copies into your library and indexes it into RAG). This path
  is the license-clean way to use personal-use / NC materials.

Links and sizes were verified live on 2026-07-03.

---

## 1. OpenStax — CC BY 4.0 (already wired for auto-download)
Rice University. Fully redistributable. The 8 titles now in the starter catalog:
University Physics Vol 1–3, Astronomy 2e, Calculus Vol 1–3, College Physics 2e.
Catalog resolved live from `https://openstax.org/apps/cms/api/v2/pages/`.

## 2. LibreTexts Physics — CC BY / BY-SA / BY-NC-SA (per book)
`https://phys.libretexts.org` — the largest OER physics library. Each book has a
"Download Full Book (PDF)" export. University-level bookshelves worth indexing:
- University Physics (OpenStax mirror) — Classical Mechanics / E&M / Optics & Modern
- Classical Mechanics (Dourmashkin, MIT 8.01) — CC BY-NC-SA
- Electricity and Magnetism, Quantum Mechanics, Thermodynamics & Statistical Mechanics bookshelves
Licenses vary per title — check the page footer before redistributing; personal
"Add folder" use is always fine.

## 3. Light and Matter — Benjamin Crowell — CC BY-SA
`https://www.lightandmatter.com` — reputable open series. Fully redistributable.
- **Simple Nature** — calculus-based intro physics (the university-level one)
- **Mechanics**, **Fields and Circuits**, **Modern Physics**, **Special/General Relativity**
Books are chapter-split PDFs on each book page (no single stable full-book URL),
so grab them from the book page and use **Add folder**.

## 4. Motion Mountain — Christoph Schiller — CC BY-NC-ND (free, personal use)
`https://www.motionmountain.net` — a 6-volume, full-color modern physics text.
Direct, stable per-volume PDFs (verified live):
- Vol 1 Mechanics/Heat — `https://www.motionmountain.net/motionmountain-volume1.pdf` (247 MB)
- Vol 2 Relativity/Cosmology — `.../motionmountain-volume2.pdf` (53 MB)
- Vol 3 Light/Charges/Brain — `.../motionmountain-volume3.pdf` (80 MB)
- Vol 4 Quantum of Change — `.../motionmountain-volume4.pdf` (28 MB)
- Vol 5 Pleasure/Technology — `.../motionmountain-volume5.pdf` (97 MB)
- Vol 6 Strand Model — `.../motionmountain-volume6.pdf` (35 MB)
NC clause → use **Add folder**, don't bundle into a redistributed build.

## 5. Individual open university texts (CC, direct sources)
- **Variational Principles in Classical Mechanics** — Douglas Cline, U. Rochester —
  CC BY-NC-SA. Upper-division analytical mechanics (Lagrangian/Hamiltonian).
  `https://openbooks.lib.msu.edu/` mirror & `http://classicalmechanics.lib.rochester.edu/`
- **Electromagnetics Vol 1 & 2** — Steven Ellingson, Virginia Tech (VTechWorks) —
  CC BY-SA. `https://doi.org/10.21061/electromagnetics-vol-1` (and `-vol-2`)
- **University Physics I/II/III** — Julio Gea-Banacloche, U. Arkansas ScholarWorks —
  CC BY. Calculus-based. `https://scholarworks.uark.edu/oer/`
- **Mechanics and Relativity** — Timon Idema, TU Delft Open — CC BY-NC-SA.
  `https://textbooks.open.tudelft.nl/textbooks/catalog/book/14`
- **Calculus-Based Physics** — Jeffrey Schnick — CC BY. `http://www.cbphysics.org`

## 6. Public-domain classics (fully free, great for historical/derivation refs)
- Einstein, *Relativity: The Special and General Theory* — Project Gutenberg #30155
- Maxwell, *A Treatise on Electricity and Magnetism* — archive.org
- Newton, *Principia* (Motte/Cajori translation) — archive.org
- Feynman *Lectures on Physics* — free to **read** at
  `https://www.feynmanlectures.caltech.edu` but **not** redistributable (no bundling).

---

### Aggregators to browse for more
- Open Textbook Library — `https://open.umn.edu/opentextbooks/subjects/physics`
- OER Commons — `https://oercommons.org` (Physics)
- Directory of Open Access Books (DOAB) — `https://directory.doabooks.org`
- OpenAccessTexts Physics — `https://openaccesstexts.com/physics/`

### License note
Only CC BY / CC BY-SA / public-domain works are safe to bundle into a
distributed build (that's why the auto-downloader stays OpenStax-only). Anything
NC/ND is fine for your own machine via **Add folder** — AetherLab treats it like
any other library PDF and indexes it into the RAG store.
