# Salesforce foundation + find-accounts territory — design

- **Date:** 2026-06-25
- **Status:** Draft for review
- **Author:** Jarrod Wilbur (Solutions Consultant) with Claude
- **Roadmap:** Active sequence item 1 — "SF access foundation + find-accounts territory" (Salesforce MCP unlock)

## Context

`find-accounts` surfaces net-new, in-territory, *triggered* prospects for a rep. Today it learns the
rep's territory from a hand-maintained `~/Documents/ObservePoint Revenue/territory.md` (region +
verticals), asks the rep if the file is missing, and dedups only against its own `seen-log`.

The **Salesforce MCP is now connected**, so territory and "already-known accounts" can come from the
system of record instead of a rep's memory. This is the first consumer of a shared Salesforce
foundation that later items (research-account write-back, the CSM review builder, expansion radar,
reporting) will reuse — so the foundation is designed once, here, read-only.

## The architecture rule (the crux of fitting SF to this plugin)

The plugin's invariant is *Claude gathers and judges → deterministic Python computes and renders; no
LLM math, no LLM-maintained state.* The SF MCP fits without bending that:

> **The model calls the SF MCP (the *gather* step); deterministic Python only ever parses and
> processes the JSON the MCP hands back (the *compute* step). No Python script fetches Salesforce.
> No model arithmetic. No model-held state.**

This works because MCP tools are model-invoked, not callable from Python. So SF simply becomes another
thing Claude gathers and passes to scripts — exactly like web-research results today.

**This entire item is read-only.** No `create`/`update` SF calls. Writes (research write-back, the
page-count field) are deferred to Active-sequence item 4 and gated on a rev-ops governance contract.

## Scope

**In scope**
- A dedicated `salesforce-core` skill housing the shared read-side foundation.
- `find-accounts` territory resolution from SF (replacing the `territory.md`-first flow).
- The overlap-guard (SF-aware dedup), policy **"own hard, others flagged."**
- `find-accounts` flow + output changes; tests.

**Out of scope (roadmap, not here)**
- Any Salesforce write (research-account → SF, scope-calculator page-count field) + the write
  governance contract. (Active sequence items 4–5.)
- CSM review builder, expansion radar, reporting. (CS section / future.)
- The SF↔platform bridge (`OP_Account_ID__c`/`OP_App_ID__c`) and Gong-in-SF data — *discovered here*
  (see below) and reserved for the CSM/expansion items; not used by find-accounts.

## Discovered org facts (verified live 2026-06-25, read-only)

- Connected SF identity: Jarrod Wilbur — profile *Territory Manager*, role *Account Executive* — but
  functionally a **Solutions Consultant**; he carries **no** AE/ADM territory.
- **Territory object `OP_Territories__c`**: `AE__c`, `ADM__c`, `CSM__c` (User refs), `Segment__c`
  (Enterprise/Corporate/Partner), `World_Region__c`, `Sub_Region__c`, `Country__c`/`Country_Code__c`,
  `State__c`/`State_Code__c`, `Routing_Type__c`, `Name`/`Name__c`. **1,145 rows have an `AE__c` set**
  → the AE→territory model is real and broadly populated.
- **Accounts link to a territory** via `Account.OP_Territory__c` (lookup → `OP_Territories__c`;
  child relationship `Accounts__r`).
- **Account fields that matter here:** `Type` ∈ {Customer, Prospect, Previous Customer, Partner,
  Prospective Partner, Previous Partner, Defunct}; `Industry` (standard SF picklist incl. Healthcare,
  Finance, Insurance, Media, Retail, Technology, Telecommunications, Government, Education…);
  `OwnerId`/`Owner.Name`; `Website`; `Segment__c` (Enterprise/Corporate); `BillingCountry`,
  `BillingState`, `Country_Region__c`, `Continental_Region__c`, `Sub_Region__c`.
- **Roles:** every account has an Owner, an ADM, a CSM, and an SC. **Only AEs and ADMs have
  territories.** **AEs can hold named accounts outside their territory** → caught by `OwnerId`, not
  territory membership. ADM↔AE are 1:1 today but may diverge → key logic on the specific role.
- **Field hygiene:** `Account.Region__c` is labeled *"Region (OLD DONT USE)"* → use `Country_Region__c`.
  `getObjectSchema` returns admin-authored guidance — read it before building queries.

## Design

### A. `salesforce-core` (the shared, read-side foundation)

A new skill `observepoint-revenue/skills/salesforce-core/` — a "library skill" (like `branding-guide`
hosts `brand_kit.py`), depended on by SF-backed skills. Two artifacts:

1. **`references/salesforce-org.md`** — the canonical, human-readable org map: the objects/fields
   above, the field-hygiene rules, the **named SOQL queries** each skill runs (territory, account
   lookup), and the read-only-for-now rule. Single source of truth for "how we read this org,"
   analogous to find-accounts' `discovery-sources.md`. When the org schema changes, this file changes.
2. **`scripts/sf_io.py`** — deterministic helpers that *parse, shape-check, and normalize* the JSON
   the SF MCP returns. Never calls SF. Functions (initial):
   - `parse_records(mcp_result)` → list of record dicts; validates `done`/`totalSize`, raises on the
     known error envelopes (timeout, permission-stream-closed) so callers can fall back cleanly.
   - `normalize_domain(url_or_host)` → bare registrable host, for account matching.
   - (write-payload builders graduate in here later, item 4.)

`tests/conftest.py` adds `salesforce-core/scripts` to `sys.path` so other skills `import sf_io`.
`salesforce-core` may later expose a tiny user-facing capability ("show me my territory / my book"),
but v1 is foundation only.

### B. Territory resolution (`find-accounts/scripts/resolve_territory.py`)

Replaces the `territory.md`-first flow. Order of resolution:

1. **Identify the target AE/ADM.** `getUserInfo` is a *hint only* — the MCP authenticates as whoever
   connected it (an SC, here), which need not be the human running the tool. So:
   - If the connected user is an AE/ADM **and** no target is named → default to them (confirmed, not
     silently assumed).
   - Otherwise the rep names the target AE/ADM (resolve by **email** first, else name with
     disambiguation if multiple users match), **or** passes a region+segment directly.
2. **Boundary query** (model runs via MCP; keyed on the target's *actual* role):
   ```sql
   SELECT Id, Name, Name__c, Segment__c, World_Region__c, Sub_Region__c,
          Country__c, State__c, AE__r.Name, ADM__r.Name, CSM__r.Name
   FROM OP_Territories__c
   WHERE AE__c = :targetUserId            -- or ADM__c, per the target's role
   ```
3. `resolve_territory.py` digests the returned JSON → a **normalized boundary**:
   `{ regions:[], sub_regions:[], countries:[], states:[], segment:str|null, territory_ids:[],
   ae_name, adm_name, csm_name }`. The `territory_ids` are reused by the overlap-guard.
4. **Verticals** are *not* on the territory object → they stay sourced from the ICP
   `targetVerticals` list in `scoring-config.json`, with optional per-run narrowing (unchanged).
   So: **SF owns geography + segment; the ICP config owns verticals.**
5. **Segment** is a *soft* signal for net-new discovery (a prospect's segment can't be known
   authoritatively pre-research) — it informs ranking/labeling, it does not hard-gate candidates.

**`territory.md` is demoted to an optional override / offline fallback:** SF reachable → SF is the
source of truth; SF unreachable (or no SF MCP) → fall back to `territory.md`; neither → ask the rep
(today's behavior). Nothing regresses when SF is down.

### C. Overlap-guard — policy "own hard, others flagged"

Two phases, both model-gathered / script-classified:

**Phase 1 — boundary + territory membership.** From step B we already have `territory_ids` and the
target's `OwnerId`. That defines "mine."

**Phase 2 — match discovered candidates against SF.** After the model assembles its candidate list
(company names + domains from web research), look those specific companies up in SF — *targeted*, not
a bulk pull:
```sql
SELECT Id, Name, Website, Type, OwnerId, Owner.Name, OP_Territory__c, Industry
FROM Account
WHERE Website IN (:candidateDomains)        -- domain-first (most reliable)
-- name-based SOSL `find` as a fallback for candidates with no website match
```
`sf_io.normalize_domain` + a deterministic matcher join each candidate to at most one account
(domain match preferred; exact-normalized-name fallback). **The model does not do fuzzy matching** —
if a name match is ambiguous, the candidate is treated as net-new and the ambiguity is noted.

**Classification per candidate** (deterministic, in `build_exclusions.py` or folded into
`resolve_territory.py`):

| Condition on the matched account | Action |
|---|---|
| In the target's `territory_ids` **OR** `OwnerId` = target | **Hard-exclude** (this catches named accounts in other territories) |
| `Type = Customer` (any owner) | **Hard-exclude** (that's expansion, a different tool) |
| Exists in SF under another rep, or `Type ∈ {Prospect, Previous Customer, Prospective Partner, Previous Partner, Defunct}` | **Flag, still surface:** annotate `in SF — owner: X, type: Y` |
| No SF match | Net-new → surface clean |

This **feeds the existing `rank_candidates.py`**: hard-excludes drop before ranking; flags ride along
as a new `sf_status` field. It **complements** the seen-log (seen-log = our own prior surfacing;
overlap-guard = SF reality).

### D. find-accounts flow + output

- **SKILL.md:** territory section rewritten to SF-first resolution (target AE/ADM → boundary →
  overlap-guard); per-run override preserved; the old shared-laptop `territory.md` rep-name guard is
  replaced by explicit target confirmation. The skill's allowed-tools list gains the SF MCP read
  tools (`getUserInfo`, `soqlQuery`, `find`, `getObjectSchema`); the Playwright ban is unchanged.
- **Output:** chat-first ranked list + optional `.xlsx` radar unchanged, **plus an "In SF?"
  annotation/column** carrying `sf_status` for flagged candidates.

### E. Testing

All deterministic scripts are tested against **fixture MCP JSON** (captured SOQL/getUserInfo
responses) — **no live SF in the test suite**, mirroring the existing deterministic-script pattern.
Fixtures to add:
- a populated AE territory (multiple `OP_Territories__c` rows);
- an empty/SC user (zero territories → resolution must require a target);
- a named account owned by the target but *outside* their territory (must hard-exclude);
- mixed account types (Customer vs Prospect vs Defunct vs other-rep-owned) → correct hard-exclude vs
  flag classification;
- a candidate with no SF match (net-new, clean);
- domain-match and name-fallback matcher cases (incl. an ambiguous name → treated as net-new).
- error-envelope handling in `sf_io` (timeout / permission-stream-closed → clean fallback).

## Decisions (decision log)

1. **Hosting:** shared SF foundation lives in a dedicated `salesforce-core` skill. *(chosen over
   starting inside find-accounts)*
2. **Overlap-guard policy:** "own hard, others flagged" — hard-exclude the target's own
   (territory + owned) and all Customers; surface-but-flag everything else already in SF. *(chosen
   over exclude-all-SF and exclude-only-own)*
3. **Read-only for item 1.** No SF writes until the rev-ops governance contract (item 4).
4. **SF is source of truth for territory when connected;** `territory.md` becomes override/fallback.
5. **Geography + segment from SF; verticals from the ICP config.**
6. **Key territory logic on the specific role** (`AE__c` vs `ADM__c`), never assuming AE≡ADM.

## Assumptions to verify during implementation (never fabricate)

- `Account.OP_Territory__c` is populated for territory members (spot-check on a real AE's book).
- `Account.Website` is populated/reliable enough for domain-first matching; quantify the name-fallback
  rate.
- find-accounts' primary runner in practice (AE self-serve vs SC-on-behalf) — shapes the default in B1.
- Whether ADM-run discovery is needed in v1 or AE-only (mechanism supports both regardless).
- Canonical ARR field (`ARR__c` vs `Calc_ARR__c`) — not needed here, noted for later SF items.

## Out of scope / future (links the foundation forward)

- **Item 4 — research-account → SF write-back:** first use of `sf_io` write-payload builders +
  match-before-write upsert + the **owned-custom-fields governance contract** with rev ops
  (sandbox-first, idempotent, dry-run).
- **Item 5 — scope-calculator page-count field:** trivial write extension; gated on a rev-ops field.
- **CSM review builder / expansion radar:** will reuse `salesforce-core` + the discovered SF↔platform
  bridge (`OP_Account_ID__c`/`OP_App_ID__c`), Gong-in-SF call intel, and `Product_Adoption_Whitespace__c`.
