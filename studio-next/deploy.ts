import * as fs from "fs";
import { client, fees, waitDecided, EXPLORER } from "./lib";

async function main() {
  const file = process.argv[2] ?? "licence_check_studio_next.py";
  const c = client();
  console.log(`Deploying ${file} as ${c.account.address}`);
  const code = fs.readFileSync(`../contracts/${file}`, "utf-8");
  const hash = await c.deployContract({ code, args: [], fees: await fees(c) });
  console.log(`Deploy tx: ${hash}`);
  const tx = await waitDecided(c, hash);
  const address = tx.to_address ?? tx.recipient;
  console.log(`Result: ${tx.txExecutionResultName ?? tx.result_name}`);
  console.log(`Contract address: ${address}`);
  console.log(`${EXPLORER}/tx/${hash}`);
  process.exit(0);
}
main().catch((e) => {
  console.error(e);
  process.exit(1);
});
