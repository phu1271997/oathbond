// seed.mjs — populate the deployed OathBond contract with real oaths so the
// Explorer has resolved cases to show. Signs with the funded keystore wallet.
//
//   source ~/.genlayer/env.sh
//   node scripts/seed.mjs
import { readFileSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { createClient, createAccount } from "genlayer-js";
import { studionet } from "genlayer-js/chains";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
let address = process.env.GENLAYER_CONTRACT_ADDRESS;
if (!address && existsSync(join(root, ".env"))) {
  const m = readFileSync(join(root, ".env"), "utf8").match(/GENLAYER_CONTRACT_ADDRESS\s*=\s*(.*)/);
  if (m) address = m[1].trim();
}
let pk = process.env.GENLAYER_PRIVATE_KEY;
if (!pk) { console.error("GENLAYER_PRIVATE_KEY not set (source ~/.genlayer/env.sh)"); process.exit(1); }
if (!pk.startsWith("0x")) pk = "0x" + pk;

const account = createAccount(pk);
const client = createClient({ chain: studionet, account });
console.log("Seeding", address, "as", account.address);

async function waitSuccess(hash, label, tries = 40) {
  for (let i = 0; i < tries; i++) {
    try {
      const r = await client.getTransactionReceipt({ hash });
      const st = r?.status;
      if (st === "success") { console.log(`  ✓ ${label}`); return true; }
      if (st === "error" || st === "reverted") { console.log(`  ✗ ${label}: ${st}`); return false; }
    } catch {}
    await new Promise((r) => setTimeout(r, 5000));
  }
  console.log(`  … ${label}: still pending after timeout (will finalize on chain)`);
  return false;
}

async function write(fn, args, value, label) {
  const req = { address, functionName: fn, args };
  if (value !== undefined) req.value = BigInt(value);
  const hash = await client.writeContract(req);
  console.log(`  tx ${label}: ${hash}`);
  await waitSuccess(hash, label);
  return hash;
}

// A broken oath now REQUIRES an explicit, non-maker beneficiary. Use a second
// funded keystore wallet; fall back to a fixed non-maker demo address.
let benePk = process.env.GENLAYER_PRIVATE_KEY_2;
let bene;
if (benePk) {
  if (!benePk.startsWith("0x")) benePk = "0x" + benePk;
  bene = createAccount(benePk).address;
} else {
  bene = "0x000000000000000000000000000000000000dEaD";
}
if (bene.toLowerCase() === account.address.toLowerCase()) {
  console.error("Beneficiary wallet must differ from the maker wallet"); process.exit(1);
}
console.log("Beneficiary (slash recipient on BROKEN):", bene);

// Settlement window: resolution is rejected before the due date, so give each
// oath a short window, then wait it out before resolving.
const DUE_LEAD_MS = 20_000;
const due = new Date(Date.now() + DUE_LEAD_MS).toISOString();

// Oath 0 — a promise a live page can prove KEPT.
await write("open_oath",
  ["The GenLayer documentation site is publicly live and reachable", "https://docs.genlayer.com", bene, "", due],
  20000, "open #0 (expect KEPT)");
// Oath 1 — a promise the proof page does NOT substantiate => BROKEN.
await write("open_oath",
  ["This page proves we shipped our iOS app to the Apple App Store", "https://example.com", bene, "", due],
  15000, "open #1 (expect BROKEN)");

const waitMs = Date.parse(due) - Date.now() + 5_000;
if (waitMs > 0) {
  console.log(`Waiting ${Math.ceil(waitMs / 1000)}s for the settlement window to open…`);
  await new Promise((r) => setTimeout(r, waitMs));
}

console.log("Resolving (nondet jury reads the pages on-chain — this is slower)…");
await write("resolve", [0], undefined, "resolve #0");
await write("resolve", [1], undefined, "resolve #1");

const raw = await client.readContract({ address, functionName: "list_oaths", args: [] });
console.log("\nCurrent ledger:");
for (const o of JSON.parse(raw)) console.log(`  #${o.id} [${o.status}] verdict=${o.verdict || "-"} :: ${o.statement.slice(0, 48)}`);
