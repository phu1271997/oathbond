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

const bene = "0x0000000000000000000000000000000000000000"; // no beneficiary => back to maker on BROKEN

// Oath 0 — a promise a live page can prove KEPT.
await write("open_oath",
  ["The GenLayer documentation site is publicly live and reachable", "https://docs.genlayer.com", bene, ""],
  20000, "open #0 (expect KEPT)");
// Oath 1 — a promise the proof page does NOT substantiate => BROKEN.
await write("open_oath",
  ["This page proves we shipped our iOS app to the Apple App Store", "https://example.com", bene, ""],
  15000, "open #1 (expect BROKEN)");

console.log("Resolving (nondet jury reads the pages on-chain — this is slower)…");
await write("resolve", [0], undefined, "resolve #0");
await write("resolve", [1], undefined, "resolve #1");

const raw = await client.readContract({ address, functionName: "list_oaths", args: [] });
console.log("\nCurrent ledger:");
for (const o of JSON.parse(raw)) console.log(`  #${o.id} [${o.status}] verdict=${o.verdict || "-"} :: ${o.statement.slice(0, 48)}`);
