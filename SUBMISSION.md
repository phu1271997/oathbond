# GENLAYER PROJECT EXPLORER — SUBMISSION (OathBond)
**Project:** OathBond · **Network:** studionet · **Status: READY TO SUBMIT**

Everything below is live right now: contract deployed, frontend on Vercel (Home + Explorer routes),
and real jury-resolved oaths already on-chain for a reviewer to inspect without a wallet.

---

# FIELDS TO PASTE INTO THE PORTAL EXPLORER FORM

## Project name
```
OathBond
```

## Primary category
```
Dispute Resolution
```
The whole product is an adjudication: a GenLayer validator jury reads a live page and rules whether a
bonded public promise was KEPT or BROKEN. GenLayer calls itself the "adjudication layer" — this sits
squarely there rather than in a crowded AI & Agents catalog.

## Category tag 1
```
Evidence Assessment
```
The decision is made on live web evidence the contract fetches itself: `gl.nondet.web.render(proof_url)`
inside `_judge`, feeding the LLM prompt. Every oath passes through it.

## Category tag 2
```
Escrow Claims
```
`open_oath` escrows the bond, `back_oath` lets supporters co-stake, and settlement either refunds the
pot (KEPT) or slashes it to the named beneficiary (BROKEN). Staking / conviction market is the mechanic.

**Rejected tags:** `Jury Selection` (jury is GenLayer validators, not app-selected); `Prediction Markets`
(no odds/orderbook — it is a verifiable commitment, not a bet on an external event).

## One-liner (173 chars)
```
Stake GEN behind a public promise and name the page that proves it; a GenLayer AI jury reads that page on-chain and rules KEPT or BROKEN — refunding the bond or slashing it.
```

## Description (944 chars)
```
Conviction-staked accountability bonds settled on-chain by a GenLayer AI jury.

A maker stakes GEN behind a verifiable public promise and names the URL that should prove it was kept. Anyone who believes the promise will hold can back it, adding to the pot. At settlement the contract fetches that page via gl.nondet.web.render and each validator's LLM rules KEPT, BROKEN, or INCONCLUSIVE. KEPT refunds every contributor; BROKEN slashes the whole pot to the beneficiary; INCONCLUSIVE stays open for one stricter re-check, and an unprovable promise then resolves BROKEN.

For teams, founders, and DAOs who want to put money behind their word.

Consensus is on the meaning of the verdict, not byte-identical JSON: each validator independently re-fetches and re-judges and only agrees if its verdict matches the leader's. A normal contract cannot read an arbitrary page and judge whether a promise was kept — that is why OathBond lives on GenLayer.
```

## How to try it

**Prerequisites**
- MetaMask installed (the app auto-adds & switches to GenLayer Studio Network on Connect — chain `61999` / `0xf22f`).
- Wallet funded with GEN on **studionet** (not the public testnet). Empty wallet → the app shows a banner linking to **Studio → Accounts** to transfer GEN. `~30,000` wei is enough.
- No wallet needed to browse: open **/explorer** and the ledger loads read-only.

**Step 1 — Browse the Explorer.** Open the live URL → **Explorer**. You see real oaths already ruled by the jury: one **KEPT** (green) and one **BROKEN** (red), each with the AI's one-line rationale, the pot, and where the money went. Filters: All / Open / Inconclusive / Kept / Broken.

**Step 2 — Connect MetaMask** (Home route). Approve connection + the network switch. If balance is 0, follow the funding banner.

**Step 3 — Open an oath.** Statement (what a page must prove), proof URL, optional beneficiary + criteria, bond in wei (e.g. `10000`). Sign in MetaMask.

**Step 4 — Resolve.** Click **Resolve now** on the open oath. Wait ~15–20s — the contract calls `gl.nondet.web.render` and the validator jury runs its LLMs. The oath flips to KEPT / BROKEN / INCONCLUSIVE with the rationale stamped on-chain. Inconclusive oaths expose an **Escalate** button for one stricter re-check.

**If something goes wrong:**
- "insufficient funds" — wallet empty on studionet; fund from Studio → Accounts.
- Wrong-chain RPC error — click Reconnect to re-trigger the network switch.
- To point the UI at another OathBond instance, append `?address=0x…` to either route.

## Expected verification outcome (458 chars)
```
Open /explorer with no wallet: the ledger shows a KEPT oath (green, bond refunded to the maker) and a BROKEN oath (red, pot slashed), each with a one-sentence AI rationale. Both are real validator-jury output — open the contract link, find the resolve tx on explorer-studio.genlayer.com, and it shows GENVM RESULT: SUCCESS with CONSENSUS Accepted. Opening a fresh oath and clicking Resolve triggers a ~15-20s consensus wait and writes a new verdict on-chain.
```

## Contract link
```
https://explorer-studio.genlayer.com/address/0x631e51d15d03504a863CFf393A4B2CB487467820
```
- **Network:** studionet
- **Status:** Preview (Studio deploy = Preview per Explorer rules)
- **Address:** `0x631e51d15d03504a863CFf393A4B2CB487467820`
- **Deploy tx:** `0xd3a81741d3e5e7c92a8842e050663e52e456e066be5d6c421a8d3d2419ed90a1`

## Website
```
https://oathbond.vercel.app
```
Explorer route: `https://oathbond.vercel.app/explorer`

## GitHub
```
https://github.com/phu1271997/oathbond
```

## Community links (optional)
Leave blank, or add your Discord / X / Telegram.

---

## SEEDED ON-CHAIN DEMO (already live)
| Oath | Statement | Proof URL | Verdict | Money |
|---|---|---|---|---|
| #0 | "GenLayer documentation site is publicly live" | https://docs.genlayer.com | **KEPT** | bond refunded to maker |
| #1 | "This page proves we shipped our iOS app" | https://example.com | **BROKEN** (INCONCLUSIVE → escalate) | pot slashed |

Reproduce: `source ~/.genlayer/env.sh && node scripts/seed.mjs`

## PRE-SUBMISSION CHECKLIST
- [x] Core decision runs via `gl.nondet.*` inside the contract (not off-chain AI)
- [x] Contract deployed on studionet, writes finalize (`Result: SUCCESS`)
- [x] Consensus checks the **verdict**, not JSON schema (`validator_fn` in `_judge`)
- [x] Frontend signs real txs + reads real state; Home + `/explorer` routes
- [x] Explorer shows real resolved cases with no wallet connected
- [x] `GENLAYER_CONTRACT_ADDRESS` baked into `frontend/app.js` on the live deploy
- [x] One-liner ≤180 (173) · Description ≤1000 (944) · Verification ≤500 (458)
- [x] Website + GitHub present
- [ ] Logo attached (PNG/JPEG/WebP, 128–2048 px square, < 2 MB) — optional, ask if you want one generated
- [ ] Demo video recorded
