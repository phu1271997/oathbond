import { createClient, createAccount } from "genlayer-js";
import { studionet } from "genlayer-js/chains";
let pk=process.env.GENLAYER_PRIVATE_KEY; if(!pk.startsWith("0x"))pk="0x"+pk;
const acct=createAccount(pk);
const c=createClient({chain:studionet,account:acct});
const addr="0x406ac5a6297D49ae8d97155b1f43DaCB8cdc6903";
const before = await c.readContract({address:addr,functionName:"get_oath_count",args:[]});
console.log("count before:", before);
const hash = await c.writeContract({address:addr,functionName:"open_oath",
  args:["The GenLayer documentation site is publicly live and reachable","https://docs.genlayer.com","0x0000000000000000000000000000000000000000",""],
  value:20000n});
console.log("tx:", hash);
// full receipt dump once
try{ const r=await c.getTransactionReceipt({hash}); console.log("receipt.status:", r?.status, "statusName:", r?.statusName); }catch(e){console.log("rcpt err",e.message);}
// poll STATE
for(let i=0;i<48;i++){
  await new Promise(r=>setTimeout(r,5000));
  const n = await c.readContract({address:addr,functionName:"get_oath_count",args:[]});
  if(Number(n)>Number(before)){ console.log(`state committed after ~${(i+1)*5}s, count=`,n); process.exit(0); }
  if(i%4===3) console.log(`  …waiting, count still ${n} (${(i+1)*5}s)`);
}
console.log("state did NOT commit within timeout");
