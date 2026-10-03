# OathBond

**Conviction-staked accountability bonds, settled by a GenLayer AI validator jury.**

Stake GEN behind a public, verifiable promise and name the page that will prove you kept it.
When it is time to settle, the Intelligent Contract opens that page **on-chain**, a GenLayer
validator jury reads it and rules **KEPT** or **BROKEN**, and the money moves accordingly —
no oracle, no human referee.

- **Live app:** https://oathbond.vercel.app
- **Source:** https://github.com/phu1271997/oathbond
- **Contract (studionet):** `0x631e51d15d03504a863CFf393A4B2CB487467820`
- **Deploy tx:** `0xd3a81741d3e5e7c92a8842e050663e52e456e066be5d6c421a8d3d2419ed90a1`
- **Explorer:** https://explorer-studio.genlayer.com/address/0x631e51d15d03504a863CFf393A4B2CB487467820
- **Network:** GenLayer **studionet** (via GenLayer Studio)

---

## Why this dies without GenLayer

The core action is a **subjective verification with real money on the line**: *"Did this person
actually keep the promise they bonded?"* Answering it requires:

1. **Reading an arbitrary live web page** (a release page, a published report, a merged PR), and
2. **Reasoning in natural language** about whether that page genuinely satisfies the promise.

A normal smart contract can do neither. OathBond puts both **inside the contract**:
`gl.nondet.web.render` fetches the proof page on-chain and `gl.nondet.exec_prompt` has the
validator jury judge it. Remove the AI + web read and there is nothing left — it is the heart,
not a garnish.

## What makes it more than an escrow: conviction staking

Besides the maker, **anyone who believes the promise will be kept can `back` it**, adding to the
pot. If the oath is **KEPT**, every contributor is refunded their exact contribution. If it is
**BROKEN**, the whole pot (maker + backers) is slashed to the named **beneficiary**. Backers
therefore put skin in the game behind someone else's credibility — a reputation market, not a
work-for-hire escrow.

## Consensus design (the part that matters)

Validators do **not** agree on byte-identical JSON. In `_judge`, each validator **independently**
fetches the proof URL, runs its own LLM, and endorses the leader **only if its own verdict
(`KEPT` / `BROKEN` / `INCONCLUSIVE`) matches the leader's**. Differently-worded rationales still
reach consensus; a genuine KEPT-vs-BROKEN split does not. That is the meaning-level consensus the
rubric asks for, built on the docs-recommended `gl.vm.run_nondet` (with a fallback to
`run_nondet_unsafe` only on older Studio builds that lack the sandboxed name).

## Lifecycle

```
maker    -> open_oath(statement, proof_url, beneficiary, criteria)   [stakes GEN]
backer*  -> back_oath(oath_id)                                       [co-stakes]
anyone   -> resolve(oath_id)      ...reads proof_url + LLM verdict...
  KEPT          -> pot refunded pro-rata to maker + every backer
  BROKEN        -> pot slashed to the beneficiary
  INCONCLUSIVE  -> stays open for ONE stricter re-check:
anyone   -> escalate(oath_id)     ...strict re-read; still unverifiable => BROKEN...
```

### Edge cases handled explicitly
- Proof page fails to fetch / is empty / irrelevant → `INCONCLUSIVE` (never a blind slash).
- A stricter re-check that is *still* inconclusive resolves to `BROKEN` — an unprovable promise
  cannot keep the bond forever.
- Zero stake, too-short statement, non-`http(s)` URL, beneficiary == maker → rejected.
- Backing a non-open oath, resolving twice → rejected.
- Terminal state is written **before** any value transfer (re-entrancy safety).

## Frontend routes

The dApp is split into dedicated views rather than one crammed page:

| Route | Purpose |
|---|---|
| `/` | **Make an oath** — connect wallet, stake a bond, and act on oaths awaiting a verdict (resolve / back / escalate). Primary actions only. |
| `/explorer` | **Public ledger** — read-only, no wallet needed. Every oath with its verdict, rationale, pot, payout destination, and filters (All / Open / Inconclusive / Kept / Broken). This is the transparency layer. |

## Seeded on-chain demo

The live contract already holds real, jury-resolved oaths so the Explorer is not empty:

- **Oath #0 — KEPT** — "The GenLayer documentation site is publicly live" → the jury fetched
  `https://docs.genlayer.com` and ruled KEPT; the bond was refunded to the maker.
- **Oath #1 — BROKEN** — "This page proves we shipped our iOS app" citing a placeholder page →
  first pass INCONCLUSIVE, then `escalate()` ruled BROKEN; pot slashed to the beneficiary path.

Reproduce with `source ~/.genlayer/env.sh && node scripts/seed.mjs`.

## Project layout

```
contracts/oathbond.py     # the Intelligent Contract
frontend/index.html       # Home route (assert + act)
frontend/explorer.html    # /explorer route (read-only ledger)
frontend/app.js           # shared genlayer-js client (MetaMask signs; no key in the bundle)
frontend/styles.css       # shared styles
tests/test_oathbond.py    # gltest: happy path + edge cases (LLM/web mocked)
scripts/deploy.mjs        # deploy to studionet, writes address to .env
scripts/build.mjs         # bakes the address into frontend/app.js (Vercel build step)
scripts/seed.mjs          # populate real oaths for the Explorer demo
```

## Deploy to studionet (step by step)

1. Fund your deployer wallet with GEN from the Studio **Accounts** panel (studionet, **not** a
   testnet faucet).
2. Load the central keystore and deploy:
   ```bash
   source ~/.genlayer/env.sh      # exports GENLAYER_PRIVATE_KEY (funded)
   npm install
   npm run deploy                 # node scripts/deploy.mjs
   ```
   The script prints the contract address and writes `GENLAYER_CONTRACT_ADDRESS` into `.env`.
3. In the Studio **Run & Debug** view, confirm the deploy transaction shows **`Result: SUCCESS`**
   (not merely `Status: FINALIZED`).

## Run the frontend

```bash
npm run build     # bakes GENLAYER_CONTRACT_ADDRESS from .env into frontend/index.html
npm run dev       # serves frontend/ at http://localhost:8080
```
Connect MetaMask; the app auto-switches to the GenLayer Studio network. To point the UI at a
different OathBond instance, append `?address=0x…` to either route.

### Deploying the frontend (Vercel)
`vercel.json` runs `node scripts/build.mjs` as the build command and serves `frontend/`. Set the
`GENLAYER_CONTRACT_ADDRESS` environment variable in the Vercel project so the build bakes the
right address.

## Tests

```bash
source ~/.genlayer/env.sh
gltest                       # local simulator (fast)
gltest --network studionet   # against studionet
```
Non-deterministic transactions install LLM/web mocks first (`sim_installMocks`) so the jury
verdict is deterministic in tests.

## One-line pitch

*OathBond dies without GenLayer because no oracle or human referee can open an arbitrary web page
and judge whether a promise was kept — the validator jury does it on-chain, and the bond follows
the verdict.*
