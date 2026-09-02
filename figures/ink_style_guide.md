# "Ink" Figure Style Guide — CCR Review: AI in Clinical Pathology & Radiology

Instructions for any coding or design agent producing figures for this project. All figures must follow these conventions so the figure set reads as one system. Figure 1 (`figure1_ink_2x2.svg`, built by `THEMES['ink']` in `build_variants.py`) is the reference implementation; when in doubt, match it.

## 1. Design philosophy

Editorial print aesthetic: white boxes, sharp corners, hairline colored borders, near-black text, serif display headings. Color is **semantic, never decorative** — it appears only where it identifies a data modality (borders, icons, embedding tokens, small sub-labels). Everything structural is drawn in ink and line grays. No fills except white, no gradients, no shadows, no decorative effects. If an element could be understood in grayscale, its color is optional; if not, redesign it (see §7).

## 2. Typography

| Role | Font | Size* | Weight/Style | Color |
|---|---|---|---|---|
| Panel letter (A, B, …) | IBM Plex Serif | 22 | Bold | #141414 |
| Panel title | IBM Plex Serif | 18 | Bold | #141414 |
| Section subtitle within a panel | IBM Plex Serif | 15 | Bold | #141414 |
| Card/box primary label | IBM Plex Sans | 12.5–14 | Bold on colored cards; regular on neutral boxes | #141414 |
| Card secondary line | IBM Plex Sans | 9.5–10.5 | Regular | modality deep color (§3) or #5C6068 |
| Column headers / axis-style labels | IBM Plex Sans | 13 | Italic | #5C6068 |
| Small functional labels (e.g., "pulled together") | IBM Plex Sans | 10–11 | Regular | #5C6068 |
| Text on dark pills | IBM Plex Sans | 12–14 | Bold | #FFFFFF |
| Numbered badges | IBM Plex Sans | 11 | Bold | #141414 |

\* Sizes are in SVG user units on a canvas where one panel column is 600–700 units wide (Figure 1 canvas: 1355×1335 for a 2×2 grid). Scale proportionally if your canvas density differs; never let effective text size fall below ~9.5 units at this density.

Fallback stacks: `'IBM Plex Serif', Georgia, serif` and `'IBM Plex Sans', Arial, sans-serif`. Both families are free (Google Fonts / `apt install fonts-ibm-plex`); install before rendering — do not substitute silently.

## 3. Color

**Neutrals (structure and text):**

- Ink `#141414` — primary text, panel letters/titles, dark pills, badges
- Line `#33373D` — arrows, connectors, brackets
- Subtle `#5C6068` — secondary labels, annotations-in-figure (sparingly; see §6)
- Panel border `#20242B` (1.3 width); neutral box border `#20242B` (1.0 width)
- Backgrounds: `#FFFFFF` only

**Semantic modality palette (Okabe–Ito, colorblind-safe — Wong, Nat Methods 2011). These assignments are FIXED project-wide:**

| Modality | Border/accent | Deep (sub-labels, icon tint) |
|---|---|---|
| Radiology imaging | `#0072B2` | `#00517F` |
| Digital pathology | `#CC79A7` | `#8F4B73` |
| Clinical text / EHR | `#009E73` | `#006B4E` |
| Molecular / omics | `#E69F00` | `#9C6C00` |
| Structural/integrative (fusion modules, joint models, agents) | `#4B4B4B` border, ink text | — |

**Sequential ramps** (e.g., embedding tokens): start from the border color and mix toward white at 25%, 48%, 70%, 87% (5 steps). Example, blue: `#0072B2 → #338EC1 → #66AAD1 → #99C7E0 → #CCE3F0`.

Never introduce new hues. If a figure needs another category, use ink/gray treatments (solid vs. dashed vs. hatched) before proposing a new color to the team.

## 4. Shapes, edges, strokes

- **Boxes/cards:** white fill, corner radius **2** (sharp), colored hairline border 1.4–1.6 wide (modality color for modality elements; `#4B4B4B` for structural; `#20242B` for neutral).
- **Panels:** white fill, `#20242B` border 1.3, radius 10. Every panel gets a serif letter + title at top-left, baseline ~35 units below panel top.
- **Terminal outputs** ("Prediction", final results): fully rounded pill (radius = height/2), solid ink `#141414` fill, white bold text. Secondary/intermediate outputs: `#3D4147` fill.
- **Arrows:** `#33373D`, width 1.6 (1.8–2.0 for major flows), solid triangular arrowhead ~6–7 units. Bidirectional = markers both ends. Curved paths (cubic Béziers) for loops/returns; keep ≥12 units clearance from any box edge.
- **Numbered step badges:** circle r 9.5, white fill, ink stroke 1.5, bold number; placed to the LEFT of the element they label.
- **Dashed strokes** (`4 3` or `5 4`): placeholders, predicted/unknown slots, conceptual boundaries (e.g., embedding-space ellipse).
- **Hatched fill** (45°, 6-unit pattern, `#F0F0F0` ground / `#BDBDBD` lines, 1px gray border): masked, hidden, or inactive elements.
- **No** drop shadows, gradients, 3D effects, clip-art, or emoji.

## 5. Icons

Single-weight line icons only, matching the existing set (X-ray = radiology, microscope = pathology, medical report = clinical text/EHR, DNA = molecular, robot = LLM agent, person = user). Tint modality icons to their **deep** color (§3 table); agents and people are ink `#141414`. Sizes 28–44 units inside cards, placed left of the label. Reuse the existing tinted assets rather than sourcing new icons; if a new concept genuinely needs a new icon, pick one from the same icon family (consistent stroke weight) and flag it for team approval.

## 6. Content rules

- **No explanatory annotations in the artwork.** Definitions, trade-offs, and caveats belong in the figure legend. Only short functional labels (≤4 words) that name what an element *is* may appear in-figure.
- Numbered badges (①②③) for any sequential process; the legend walks the numbers in order.
- No exemplar model names (CONCH, Med-Gemini, …) in artwork — cite them in the manuscript text.
- Title style: short Title Case noun phrases for panels ("Training Paradigms"); sentence case for everything inside.

## 7. Accessibility (required)

Color is never the sole cue: every colored element also carries its icon or a text label. Any new color pairing must remain distinguishable under deuteranopia, protanopia, and tritanopia simulation (the Okabe–Ito palette passes; verify anything custom). Minimum text size per §2; minimum stroke 1.0.

## 8. Deliverables & workflow

- Author figures as **SVG** (fonts referenced by name, not outlined); export **PDF** alongside. Raster previews at ≥2× for review.
- Programmatic builds preferred (see `build_variants.py`, theme `ink`) so revisions are re-renderable; keep the build script with the figure.
- Draft a CCR-style legend with every figure (bold panel letters: "**A,** …"), absorbing all explanatory content removed from the artwork per §6.
- Before delivering: render and visually inspect at full size for overlaps/clipping; check every arrow head lands on its target; confirm fonts rendered (serif headings visible).
