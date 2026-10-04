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
Appeal Review
```
`escalate()` is a secondary review layer: an INCONCLUSIVE first pass can be re-judged once under
stricter rules before the bond settles — exactly "secondary/tertiary review layers for initial
judgments." Distinct from CiteGuard's tag-2 so the two entries don't collide.

**Close alternative (not chosen):** `Escrow Claims` also fits — `open_oath`/`back_oath` lock funds and
settlement refunds or slashes them. Picked Appeal Review as the more distinctive secondary focus.
**Rejected:** `Jury Selection` (jury is GenLayer validators, not app-selected).

> Tags above are taken strictly from `~GEN_RULES/tag_taxonomy_specification.md` (Primary →
> sub-tags only within that Primary). Honest note: both of my current projects are genuinely
> **Dispute Resolution** at core; I did not mis-tag them into other Primaries just to spread the
> catalog. Future projects should diversify across the 11 Primaries (see that spec).

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

**Step 3 — Open an oath.** Statement (what a page must prove), proof URL, a required non-maker beneficiary (paid if BROKEN), a due date (judging unlocks only after it), optional criteria, bond in wei (e.g. `10000`). Sign in MetaMask.

**Step 4 — Resolve.** Click **Resolve now** on the open oath. Wait ~15–20s — the contract calls `gl.nondet.web.render` and the validator jury runs its LLMs. The oath flips to KEPT / BROKEN / INCONCLUSIVE with the rationale stamped on-chain. Inconclusive oaths expose an **Escalate** button for one stricter re-check.

**If something goes wrong:**
- "insufficient funds" — wallet empty on studionet; fund from Studio → Accounts.
- Wrong-chain RPC error — click Reconnect to re-trigger the network switch.
- To point the UI at another OathBond instance, append `?address=0x…` to either route.

## Expected verification outcome (458 chars)
```
Open /explorer with no wallet: the ledger shows a KEPT oath (green, bond refunded) and an INCONCLUSIVE oath whose Escalate stays locked until its 24h challenge window elapses, each with a one-sentence AI rationale. Both are real validator-jury output — open the contract link, find the resolve tx on explorer-studio.genlayer.com, and it shows GENVM RESULT: SUCCESS with CONSENSUS Accepted. A fresh oath cannot be resolved before its on-chain due date; once due, Resolve triggers a ~15-20s consensus wait and writes a new verdict on-chain.
```

## Contract link
```
https://explorer-studio.genlayer.com/address/0x59063CE282015BeE398767430a33007b69F99cA3
```
- **Network:** studionet
- **Status:** Preview (Studio deploy = Preview per Explorer rules)
- **Address:** `0x59063CE282015BeE398767430a33007b69F99cA3`
- **Deploy tx:** `0xe6a33113bdd7e905681fb41c9cb5e20bb3afbf538380c602cc81a8896e6933d8`

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
| #0 | "GenLayer documentation site is publicly live" | https://docs.genlayer.com | **KEPT** | bond refunded to maker + backers |
| #1 | "This page proves we shipped our iOS app" | https://example.com | **INCONCLUSIVE** | escalatable to BROKEN after the 24h challenge window → pot slashed to the named beneficiary |

Both were opened with a short settlement window and an explicit non-maker beneficiary, then resolved after the due date — exercising the on-chain guardrails.

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
