# ObservePoint brand — usage guidelines

Human-readable companion to `brand-spec.json` (the machine source of truth). When
they disagree, the JSON wins; fix the JSON, then this doc.

## Colors
- **Brand yellow `#F2CD14`** — the signature accent. Verified from the site CSS
  (`.logo{color:#f2cd14}`). Use for accents, rules, chips, highlights — not body text.
- **Ink `#1E1E1E`** — primary text on light; near-black brand neutral.
- **Dark surfaces** — bg `#14151A`, panel `#1E2027`, panel2 `#262932`, border `#313440`,
  text `#E8E9EC`, muted `#9AA1AD`.
- **Light surfaces** — page `#FFFFFF`, fill `#F2F2F2`, gray `#5C5C5C`, input `#FFF7CC`,
  hairline `#D9D9D9`.
- **Semantic** — success `#27A567`, alert `#F34146`, link `#7CB8FF`.

## Logos
- **Primary** (all-yellow logotype) → dark backgrounds only.
- **Ink** (dark logotype) → light backgrounds.
- **Secondary** (white Observe + yellow Point) → decks (file pending).
- **Favicon** (OP monogram, gray on yellow) → small spaces / app icon.
- Don't recolor, rotate, stretch, add effects, or place the yellow primary on a light
  background (it disappears — use ink).

## Typography
- **Montserrat** everywhere. Weights: 400 body, 600 labels, 700 subheads, 800 headlines.
- Fallback stack: `-apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif`.

## Themes by format
- **Dark (default):** HTML dossier, PDFs, one-pagers, reports, decks.
- **Light (default):** `.xlsx` workbook, `.docx` proposal, letters, memos.
- Either is available on request via `--theme`.
