# Scope-of-Work flow + proposal-from-xlsx (Phases 3+4) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Finish the Scope-of-Work-first redesign — rewrite the flow/reference docs off the retired multiplier model (Part A), and build the proposal-from-the-AE-edited-workbook path with an integrity validator + rework `build_proposal` to the additive-buffer model (Part B).

**Architecture:** The engine (`compute_scope.py`) and workbook (`build_model.py`) are already on the additive-buffer model. This plan brings the *docs* and the *proposal* in line. The proposal is no longer assembled from Stage-2 output up front — it is built **on request** by reading the AE-edited `<Customer> - Scope of Work.xlsx`, recomputing through `compute_scope`, and rendering. A new `read_scope_of_work.py` parses the workbook's input cells, **validates integrity** (formula cells untampered, structure intact, inputs valid — hard-stop with an itemized message), and produces a `compute_scope`-ready payload; `build_proposal.py` renders the new-model proposal.

**Tech Stack:** Python 3, `openpyxl`, `python-docx`, `pytest`. Interpreter: `/opt/homebrew/bin/python3`. Full suite: `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests -q`.

**Spec:** `docs/superpowers/specs/2026-06-16-scope-of-work-first-redesign-design.md`
**Verbatim doc edits (full new_text per change):** the understand-pass artifact at `/private/tmp/claude-501/-Users-jarrodwilbur-Downloads-Bryce/fb09abd6-456e-40fb-b29e-e03bb6be2e79/tasks/wvtotfm01.output` — `result.docResults[].proposed_changes[]` carries the exact ready-to-paste `new_text` for every Part-A edit, `result.xlsxMap` the cell geometry, `result.design` the reader spec. Dispatch prompts paste from there.

---

## Locked decisions

1. **Strategy A — proposal speaks the new vocabulary.** `build_proposal` §3 renders Total Pages Found → ×geographies → ×consent → ×environments → **Combined**, then the 4 cadence layers + an **additive Buffer row**, then the single **predicted total**; §4 is **"Annual investment"** = the *exact* `graduated_price(predicted_scans)`. The retired "Recommended contract" pair and `recommended_scans`/`recommended_price`/`pages_per_sweep` are gone. Rationale: the customer also sees the Scope of Work workbook the proposal is recomputed from — they must reconcile.
2. **Reader recomputes via `compute_scope`** from the workbook's INPUT cells → payload consistent by construction. The **integrity validator** is the guard (not a payload-drift reconcile guard).
3. **Fixtures are recomputed, never hand-arithmetic.** Every `predicted_scans` / price in a test fixture is produced by running `compute_scope.compute(...)` on that fixture's inputs (new 4-layer ladder, `buffer_pct=0.15`) and pasting the engine's exact output. The understand-pass fixture numbers are illustrative placeholders ONLY.
4. **Validator↔builder lock via a round-trip test** (build a fresh workbook with `build_model`, assert the validator passes it clean) rather than refactoring `build_model` to share formula-template helpers now.
5. **Aggregate row is position-independent** — the reader detects the long-tail row by regex `^\(\d+ additional domains`, so the bottom-aggregate layout from Phase 1-2 works unchanged.
6. **`.work/` relocation + on-request behavior is SKILL.md instruction (no central script).** The build scripts already take an output path argv; the orchestrator writes the SoW to `<Customer>/`, the JSONs + pre-built internal-evidence to `<Customer>/.work/`, and on request moves internal-evidence up / builds the proposal via `read_scope_of_work` → `build_proposal`.
7. **Do NOT add "purchased"/"contract" to `customer_clean.FORBIDDEN`** (false-positive risk on legitimate prose); document the retired terms in `customer-vocabulary.md` only.

---

## File structure

Part A (docs — mostly prose; low test surface):
- Modify `observepoint-revenue/skills/scope-calculator/references/frequency-advisor.md`
- Modify `observepoint-revenue/skills/scope-calculator/references/pricing-model.md`
- Modify `observepoint-revenue/skills/scope-calculator/references/usage-methodology.md`
- Modify `observepoint-revenue/skills/scope-calculator/references/deliverables-mapping.md`
- Modify `observepoint-revenue/skills/scope-calculator/references/customer-vocabulary.md`
- Modify `observepoint-revenue/skills/scope-calculator/SKILL.md`

Part B (code + tests):
- Modify `observepoint-revenue/skills/scope-calculator/scripts/build_proposal.py`
- Modify `observepoint-revenue/tests/test_build_proposal.py`
- Create `observepoint-revenue/skills/scope-calculator/scripts/read_scope_of_work.py`
- Create `observepoint-revenue/tests/test_read_scope_of_work.py`
- Modify `README.md`, `CLAUDE.md` (test count), `plugin.json` (version bump on ship — separate, after merge)

---

## PART A — Flow & reference docs (Phase 3)

Each Part-A task: apply the exact `new_text` edits for that file from the understand artifact's `docResults[]` entry, then run the full suite (docs aren't broken by edits, but `test_frequency_advisor_reference_exists_and_has_ladder` and any vocab-sync test must stay green — note these move in Part B), then commit. Part-A files are independent (different files) and may be applied in parallel, but commit each separately for a clean history.

### Task A1: `frequency-advisor.md` → 4-layer + additive-buffer ladder
**Files:** Modify `…/references/frequency-advisor.md`
- [ ] Apply the 5 edits from `docResults[1].proposed_changes` (intro, the ladder table → 4 layers + a Buffer-% note, the blend note → `predicted_scans = Σ(combined×pct×runs) + round(combined×buffer%)`, the additive-layers note, the pull-back order). New ladder: Baseline inventory/Yearly/100%, High Priority/Weekly/1.5%, Moderate Priority Pages/Monthly/7.5%, Low Priority Pages/Quarterly/20%, Buffer %/15% (additive, one pass).
- [ ] Commit: `docs(frequency-advisor): 4-layer + additive-buffer default ladder`

### Task A2: `pricing-model.md` → additive buffer; delete recommended-contract
**Files:** Modify `…/references/pricing-model.md`
- [ ] Apply `docResults[2].proposed_changes`: §2 tier classified on `predicted_scans`; rewrite §3 to the additive buffer (`buffer_scans = round(combined_pages × buffer_pct)`, default 15%, no purchased number, price/tier on `predicted_scans`); **delete §3b** (recommended-contract back-solve) entirely.
- [ ] Commit: `docs(pricing-model): additive buffer; retire purchased/recommended-contract`

### Task A3: `usage-methodology.md` → combined_pages + additive + 4-layer
**Files:** Modify `…/references/usage-methodology.md`
- [ ] Apply `docResults[3].proposed_changes`: §1 code block → `combined_pages` / additive buffer / `predicted_scans` / exact graduated price; §1 prose; §3 → the 4-layer + additive-buffer ladder table; §4 implied-blended-frequency → `predicted_scans / combined_pages`; §5 ask-map cadence-mix + buffer-% rows.
- [ ] Commit: `docs(usage-methodology): combined_pages + additive buffer + 4-layer ladder`

### Task A4: `deliverables-mapping.md` → Scope-of-Work-first contract
**Files:** Modify `…/references/deliverables-mapping.md`
- [ ] Apply `docResults[4].proposed_changes`: intro → SoW default + proposal/internal on-request + recompute-from-edited-xlsx; cadence-layers blockquote → `combined_pages` multiplicand + additive buffer formula; reconcile target → `usage.combined_pages`; "Output 1/2/3" → "Output — … (DEFAULT / ON REQUEST)"; `usage` bullet → `{combined_pages, predicted_scans}`; `pricing` bullet → `{predicted_scans, modeled_price, range_*}` (drop recommended pair); workbook section → "Scope of Work workbook" + 4 tabs + Scope Detail levers + not-protected; model.json schema → 4 layers + `buffer_pct` default 0.15; Output-3 internal → pre-built into `.work/`, moved on request, drop recommended_contract.
- [ ] Commit: `docs(deliverables-mapping): Scope-of-Work-first contract + additive buffer`

### Task A5: `customer-vocabulary.md` → deliverable names + approved-vocab table
**Files:** Modify `…/references/customer-vocabulary.md`
- [ ] Apply `docResults[5].proposed_changes`: intro lines → new deliverable names + `.work/` flow; add the retired-pricing-jargon forbidden row; add the "Approved Scope-of-Work vocabulary" sign-off table; extend the caller-contract paragraph. **Do NOT modify `customer_clean.py` FORBIDDEN.**
- [ ] Run: `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests/test_customer_clean.py -q` — must stay green (the vocab-sync test, if present, must still pass; we only ADD an approved-vocab section, we don't remove forbidden-term docs).
- [ ] Commit: `docs(customer-vocabulary): new deliverable names + approved-vocab sign-off`

### Task A6: `SKILL.md` → Scope-of-Work-first flow
**Files:** Modify `…/SKILL.md`
- [ ] Apply `docResults[0].proposed_changes` (12 edits): intro rewording; **rewrite Phase 0** to "Frame" (no audience prompt; SoW clean by construction; internal context → `<Customer>/.work/`); Stage 2 step 3 → the 4-layer + additive-buffer walk; step 5 → additive buffer compute note; step 6 → single predicted total priced directly (no purchased/contract/tier-flip); **rewrite Stage 3** to "Build the Scope of Work (then proposal on request)" (default builds only the SoW xlsx; JSONs + pre-built internal-evidence → `.work/`; on request move internal-evidence up / build proposal from the AE-edited xlsx via `read_scope_of_work` → `build_proposal`); Customer-workbook + Proposal + Internal-evidence + Output-location bullets; single-source rule; 3 Red-Flags rows.
- [ ] Commit: `docs(SKILL): Scope-of-Work-first flow (no audience prompt; .work/; proposal-on-request)`

---

## PART B — Proposal from the AE-edited workbook (Phase 4)

### Task B1: Rewrite `build_proposal.py` to the additive-buffer model

**Files:** Modify `observepoint-revenue/skills/scope-calculator/scripts/build_proposal.py`

Apply `docResults[6].proposed_changes` (exact code in the artifact). Summary of the 8 edits:
- **§3 sweep table** (lines ~263-272): read `combined = us.get("combined_pages", us.get("pages_per_sweep"))`; terminal row label "**Combined pages monitored**" = `_int(combined)`; table title "From pages to combined scope"; first row "Total Pages Found on your properties" = `pc["anchor"]`.
- **§3 cadence table** (lines ~274-283): per-layer `pages_each = round(combined * pct)`, `scans = round(combined * pct * runs)`; **add an additive Buffer row** when `data.get("buffer_pct")`: `buffer_scans = round(combined * buffer_pct)`, rendered as `["Buffer", "Headroom for new pages, campaigns, and ad-hoc re-scans.", "One pass", buffer_scans, "1", buffer_scans]`; total row = `us.get("predicted_scans", us.get("annual_scans"))`.
- **§4 Investment** (lines ~285-296): section title → **"4. Annual investment"**; highlight = `{predicted} page scans · {predicted_price} / year` where `predicted_price = pr.get("predicted_price", pr.get("recommended_price"))`; reconcile callout reworded to "exact price of your predicted page scans — the cadence above, plus buffer headroom."
- **`_sweep_reconcile_error`** (lines ~339-352): reconcile to `usage.combined_pages` (not `pages_per_sweep`); ADD a second invariant — `Σ round(combined*pct*runs) + round(combined*buffer_pct)` must equal `usage.predicted_scans` within 1% (itemized "predicted scans don't reconcile" message). Exact code in the artifact.
- **`_REQUIRED`** (lines ~315-320): `pricing: "{predicted_price}"`, `usage: "{combined_pages, predicted_scans}"`.
- **Module docstring** (lines ~22-25): `buffer_pct?`; `usage: {combined_pages, predicted_scans}`; `pricing: {predicted_price, range_*}`.
- **Prose renames** (lines 241, 243-246, 303): "the attached investment model" → "the attached Scope of Work workbook"; "Scope detail" → "Scope Detail".

- [ ] **Step 1:** Apply all 8 edits (paste exact `new_text` from the artifact).
- [ ] **Step 2:** This will break `test_build_proposal.py` (old fixtures/keys). That is expected — it's fixed in Task B2. Run only a syntax/import check: `cd observepoint-revenue && /opt/homebrew/bin/python3 -c "import sys; sys.path.insert(0,'skills/scope-calculator/scripts'); import build_proposal"` → no error.
- [ ] **Step 3:** Commit: `feat(build_proposal): additive-buffer §3 (Buffer row) + §4 annual investment; retire pages_per_sweep/recommended-contract`

### Task B2: Rework `test_build_proposal.py` to the new model (with recomputed numbers)

**Files:** Modify `observepoint-revenue/tests/test_build_proposal.py`

- [ ] **Step 1 — recompute fixtures.** For DATA (Gallagher: anchor 95,721, geos 1, scenarios 3, env 1) and GILEAD_DATA (anchor 848, geos 3, scenarios 3, env 1), with the new 4-layer ladder (1.0/1, 0.015/52, 0.075/12, 0.20/4) and `buffer_pct=0.15`, run:
```bash
cd "/Users/jarrodwilbur/Documents/OP Revenue Plugin/observepoint-revenue/skills/scope-calculator/scripts"
/opt/homebrew/bin/python3 - <<'PY'
import compute_scope as cs, json
def show(name, anchor, geos, scen, env):
    out = cs.compute({"page_count":{"low":anchor,"anchor":anchor,"high":anchor},
        "multipliers":{"geographies":geos,"scenarios":scen,"environments":env},
        "buffer_pct":0.15,"tiers":cs.BAKED_TIERS,
        "cadence_layers":[{"name":"Baseline inventory","pct":1.0,"runs_per_year":1},
            {"name":"High Priority","pct":0.015,"runs_per_year":52},
            {"name":"Moderate Priority Pages","pct":0.075,"runs_per_year":12},
            {"name":"Low Priority Pages","pct":0.20,"runs_per_year":4}]})
    a=out["anchor"]
    print(name, "combined:",a["combined_pages"],"predicted:",a["predicted_scans"],
          "price:",a["price"]["total"],"buffer_scans:",a["buffer_scans"])
show("GALLAGHER",95721,1,3,1); show("GILEAD",848,3,3,1)
show("GILEAD_env2",848,3,3,2)
PY
```
  Use the printed `combined_pages`, `predicted_scans`, `price` **verbatim** in the fixtures and assertions below.
- [ ] **Step 2 — rewrite fixtures.** Apply `docResults[7].proposed_changes` for DATA cadence_layers + `buffer_pct: 0.15` + `usage: {combined_pages, predicted_scans}` + `pricing: {predicted_scans, price_total, range_*, price_by_band, pricing_source}`; `internal.implied_blended_frequency`; GILEAD_DATA likewise. **Replace every placeholder number with the Step-1 output.** The per-layer cadence assertions (e.g. Low Priority pages_each/scans, Buffer scans, predicted total) must be recomputed too — derive them as `round(combined*pct)`, `round(combined*pct*runs)`, `round(combined*0.15)`.
- [ ] **Step 3 — retarget tests.** Apply the `proposed_changes`: `test_customer_sections_and_derivation` (combined total, 4 cadences Yearly/Weekly/Monthly/Quarterly, predicted total, "Annual investment"/"Recommended investment", exact price, "Scope of Work" tab); rename `test_recommended_pair_reconciles_in_calculator` → `test_price_is_exact_graduated_price_of_predicted_scans`; `_with_anchor` → set `combined_pages` not `pages_per_sweep`; `test_gilead_sweep_table_has_geographies_row` (c/e/f/g/h with recomputed numbers incl. Buffer row + predicted total); `test_gilead_environments_row_shown_when_gt_one` (recompute combined/predicted for env=2); `test_frequency_advisor_reference_exists_and_has_ladder` → new ladder terms + pcts (`baseline inventory/high priority/moderate priority/low priority/buffer`, `100%/1.5%/7.5%/20%/15%`).
- [ ] **Step 4 — delete the retired §3-payload-drift reconcile tests:** `_gilead_with_dropped_geo`, `test_dropped_geo_multiplier_is_rejected_not_silently_rendered`, `test_cli_friendly_error_on_unreconciled_sweep`, and collapse `test_consistent_chain_still_renders`/`test_environments_one_point_five_reconciles` into render-only tests on the new shape. (The reader recomputes from the xlsx, so the orchestrator-drops-a-multiplier failure mode no longer exists; the combined-pages reconcile guard remains as defense-in-depth and is covered by `test_price_is_exact_...` + the render tests.)
- [ ] **Step 5 — keep unchanged** (still valid): `_text`, `test_no_internal_section_or_confidence_in_customer_doc`, `test_cadence_table_shows_the_why`, all `test_clean_guard_*`, `test_cli_writes_docx`, the two CLI friendly-error tests, the three `_round_sig`/footprint tests, `test_proposal_does_not_mention_removed_methodology_sheet_or_internal_terms`, `test_gilead_environments_row_hidden_when_one`. (Optionally dedup the two near-identical identity-collision clean-guard tests.)
- [ ] **Step 6:** Run `cd observepoint-revenue && /opt/homebrew/bin/python3 -m pytest tests/test_build_proposal.py -q` → all pass. Then the FULL suite (note `test_frequency_advisor_reference_exists_and_has_ladder` depends on Task A1 being done — sequence A1 before B2, or temporarily xfail; the controller sequences A before B).
- [ ] **Step 7:** Commit: `test(build_proposal): rework to additive-buffer model with recomputed fixtures`

### Task B3: Create `read_scope_of_work.py` (reader + integrity validator)

**Files:** Create `observepoint-revenue/skills/scope-calculator/scripts/read_scope_of_work.py`; Create `observepoint-revenue/tests/test_read_scope_of_work.py`

Implement per `result.design` in the artifact (full spec). Public surface:
- `read_scope_of_work(path) -> dict` — two openpyxl loads (`data_only=False` for inputs+formula-integrity, `data_only=True` for cached totals); discovers row geometry dynamically (Scope Detail header row 3, data rows 4..l by walking col A until A&B both empty; Scope of Work cadence rows 14..`buf-1` where `buf`=row whose A=="Buffer %", `total`=buf+1, `inv`=total+2; Pricing bands 5..`total_row-1` where total_row=row whose A startswith "Recommended investment"); returns the payload (customer, page_count low=anchor=high=recomputed Total Pages Found, multipliers, cadence_layers[{name,pct,runs_per_year,why}], buffer_pct, per_domain[{hostname,defensible_pages,include,sample_size}], tiers, `_cached`, `_warnings`).
- `validate_scope_of_work(wb_f, wb_v, *, geom) -> (hard_stops, warnings)` — Groups A (required sheets), B (structure/headers/required rows), C (formula cells untampered — normalized comparison, regenerated for discovered geometry; C9 % formula is WARNING), D (input types/ranges; D9 no-in-scope is HARD-STOP), E (reconciliation, all WARNING; E0 cache-absent WARNING). HARD-STOP raises `IntegrityError` with the itemized `scope-calculator: …` report.
- `proposal_payload_from_scope_of_work(path, *, prepared_by, date, use_case, regulations, monitoring_summary, properties_note, consent_names)` — calls `read_scope_of_work`, recomputes via `compute_scope.compute`, assembles the **new-model** `build_proposal` payload: `usage={combined_pages, predicted_scans}`, `pricing={predicted_price=anchor.price.total, predicted_scans, range_low_price, range_high_price, price_by_band, pricing_source}`, `cadence_layers=anchor.cadence_by_layer`, `buffer_pct`, `multipliers` verbatim.
- CLI: `read_scope_of_work.py "<Customer> - Scope of Work.xlsx" [out.json]` → prints payload JSON or exits non-zero with the integrity report.

Sample-size normalization (§4 of design): if `1 < s <= 100` treat as percent (`/100`, WARNING); `s>100` or `s<=0` → HARD-STOP D3. Aggregate row detected by `^\(\d+ additional domains` → tagged, treated as one opaque domain. Last Pricing band `To >= 1e11` → sentinel, handled.

- [ ] **Step 1 (TDD) — write `test_read_scope_of_work.py`** with these tests (build the workbook fresh via `build_model.build_workbook` into `tmp_path`, then read/tamper):
  - `test_roundtrip_reader_extracts_inputs` — build SoW from a known model, read it back, assert per_domain/multipliers/cadence_layers/buffer_pct/tiers match the model inputs; assert recomputed `page_count.anchor == total_pages_found(per_domain)`.
  - `test_validator_passes_clean_workbook` — fresh workbook → `validate_scope_of_work` returns `([], warnings)` with no hard-stops (the validator↔builder lock).
  - `test_payload_feeds_build_proposal` — `proposal_payload_from_scope_of_work(...)` → `build_proposal.build_proposal(payload)` renders without raising; price in the doc == `graduated_price(predicted_scans)`.
  - `test_tampered_formula_hard_stops` — overwrite `Scope of Work!B6` (or `B10`) with a literal, save, read → raises `IntegrityError`, message names the cell, no doc written.
  - `test_deleted_structural_row_hard_stops` — delete the "Buffer %" row (or a header) → `IntegrityError`.
  - `test_invalid_input_hard_stops` — set a Sample Size to 150% (or pages to -1, or a multiplier to 0) → `IntegrityError` naming the row.
  - `test_no_in_scope_pages_hard_stops` — set all Include? to FALSE → `IntegrityError` ("nothing to price").
  - `test_sample_size_50_normalized_to_half` — a Sample Size cell of `50` → read as 0.5 with a WARNING.
  - `test_cache_absent_is_warning_not_stop` — openpyxl-built workbook (no cached values) → reconciliation skipped, WARNING present, payload still returned.
  - `test_cli_integrity_report_nonzero` — CLI on a tampered file exits non-zero, prints the itemized "scope-calculator:" report, no traceback.
- [ ] **Step 2:** Run the new test file → fails (module absent).
- [ ] **Step 3:** Implement `read_scope_of_work.py` per the design.
- [ ] **Step 4:** Run `tests/test_read_scope_of_work.py` → all pass; then the FULL suite → all pass.
- [ ] **Step 5:** Commit: `feat(read_scope_of_work): parse + integrity-validate the edited Scope of Work; build proposal payload`

### Task B4: Integration + counts

**Files:** Modify `README.md`, `CLAUDE.md`
- [ ] **Step 1:** Confirm end-to-end: `build_model.build_workbook` → save → `proposal_payload_from_scope_of_work` → `build_proposal.build_proposal` renders a clean docx whose numbers equal `compute_scope.compute` on the same inputs. (Covered by `test_payload_feeds_build_proposal`; add an explicit end-to-end assertion if not already pinned.)
- [ ] **Step 2:** Update the test count in `README.md` and `CLAUDE.md` to the new `pytest tests -q` total (run it, paste the number).
- [ ] **Step 3:** Commit: `docs: update test count after Phase 3+4`

---

## Testing summary
- Part A: doc edits; guard via `test_customer_clean.py` (unchanged green) and `test_frequency_advisor_reference_exists_and_has_ladder` (retargeted in B2, depends on A1).
- Part B: `build_proposal` reworked + fixtures recomputed; new `read_scope_of_work` suite (round-trip, validator-clean, tamper hard-stops, normalization, cache-absent warning, CLI). The round-trip + validator-clean tests lock the reader to `build_model`.
- Final: full suite green; an end-to-end build_model→read→build_proposal assertion.

## Sequencing
A1 → (A2–A5 any order, independent) → A6, then B1 → B2 → B3 → B4. (A1 before B2 because B2 retargets the frequency-advisor ladder test.) Branch `feat/scope-of-work-first` (already checked out). After B4: final holistic review of the whole redesign (Phases 1-4), then finishing-a-development-branch (merge + version bump + ship).

## Self-review notes
- **Spec coverage:** flow (A6), all 5 reference docs (A1-A5), proposal-from-edited-xlsx + integrity validation (B3), build_proposal additive-buffer rework (B1-B2), counts (B4). All spec sections mapped.
- **Type consistency:** payload keys (`usage.combined_pages`, `usage.predicted_scans`, `pricing.predicted_price`/`predicted_scans`, `buffer_pct`, `cadence_layers[].{name,pct,runs_per_year,why}`) match between `read_scope_of_work` (B3), `build_proposal` (B1), and the fixtures (B2).
- **No placeholders:** code-heavy tasks inline the change-list; verbatim doc `new_text` lives in the referenced understand artifact (paste at dispatch). Fixture numbers are recomputed (decision 3), never the artifact's placeholders.
