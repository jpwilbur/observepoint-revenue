# ObservePoint Salesforce — canonical org map (read side)

How this plugin reads the ObservePoint SF org. The MODEL runs these queries via the
Salesforce MCP; scripts only digest the JSON. **Read-only** — no write queries here yet.

## Field hygiene (read before writing SOQL)
- `Account.Region__c` is labeled **"Region (OLD DONT USE)"** → use `Country_Region__c`
  (label "Region"), `Continental_Region__c`, or `Sub_Region__c`.
- Confirm the canonical ARR field (`ARR__c` vs `Calc_ARR__c`) via `getObjectSchema` admin
  guidance before trusting either. (Not used by find-accounts.)
- `getObjectSchema` returns admin-authored guidance — read it before constructing queries.

## Territories — `OP_Territories__c`
Only **AEs and ADMs** have territories. Accounts link via `Account.OP_Territory__c`.
Fields: `AE__c`, `ADM__c`, `CSM__c` (User refs), `Segment__c` (Enterprise/Corporate/Partner),
`World_Region__c`, `Sub_Region__c`, `Country__c`, `State__c`, `Name`/`Name__c`.

**Named query — a target's territory** (key on the target's *actual* role; never assume AE≡ADM):
```sql
SELECT Id, Name, Name__c, Segment__c, World_Region__c, Sub_Region__c,
       Country__c, State__c, AE__r.Name, ADM__r.Name, CSM__r.Name
FROM OP_Territories__c
WHERE AE__c = :targetUserId          -- or ADM__c = :targetUserId
```

**Named query — resolve a target user by email** (when the runner isn't the target):
```sql
SELECT Id, Name, Email FROM User WHERE Email = :email AND IsActive = true
```

## Accounts (overlap-guard)
`Account.Type` ∈ {Customer, Prospect, Previous Customer, Partner, Prospective Partner,
Previous Partner, Defunct}. `OwnerId`/`Owner.Name`, `Website`, `OP_Territory__c`, `Industry`.
**AEs can own named accounts outside their territory** → match on `OwnerId`, not just territory.

**Named query — match swept candidates to existing accounts** (domain-first):
```sql
SELECT Id, Name, Website, Type, OwnerId, Owner.Name, OP_Territory__c, Industry
FROM Account
WHERE Website IN (:candidateDomains)
```
For candidates with no website match, fall back to a name search:
```
FIND {"Acme*"} IN NAME FIELDS RETURNING Account(Id, Name, Website, Type, OwnerId, OP_Territory__c)
```

## Bridges (reserved for later items — NOT used by find-accounts)
- `Account.OP_Account_ID__c` / `OP_App_ID__c` → the ObservePoint platform account.
- Gong is synced into SF (`Gong__Gong_Call__c`, `Gong__Note__c`, `Gong__Gong_Scorecard__c`, …).
- `Product_Adoption_Whitespace__c` + `Account.OP_Product_Lines__c` for expansion.
