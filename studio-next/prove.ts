// Reproducible live proof: registers and checks a fixed set of real firms
// covering every verdict and every register quirk the README describes,
// and appends each result (with tx hashes) to live_proof.json - the source
// for CONTRACT.md's tables.
//
//   npx tsx prove.ts <address> [first_case] [last_case]
import * as fs from "fs";
import { client, readClient, write, safeJson } from "./lib";

type Case = { id: string; lei: string; services: string; state: string; website: string; label: string; why: string };

const BYBIT = "5299005V5GBSN2A4C303";
const CASES: Case[] = [
  { id: "bybit-de", lei: BYBIT, services: "a,c", state: "DE", website: "https://www.bybit.eu", label: "Bybit EU custody + fiat exchange in Germany", why: "both readers agree, identity current, website listed" },
  { id: "bybit-mt", lei: BYBIT, services: "a", state: "MT", website: "", label: "Bybit EU custody in Malta", why: "authorised, but not passported to Malta" },
  { id: "hpb-hr", lei: "529900D5G4V6THXC5P79", services: "a", state: "HR", website: "", label: "HPB custody in Croatia", why: "regulator comment limits it to one fund" },
  { id: "blueemi-lt", lei: "254900XFMACGD0L7AI73", services: "a", state: "LT", website: "", label: "BLUE EMI custody in Lithuania", why: "regulator comment limits it to its own e-money token" },
  { id: "northcrypto-fi", lei: "743700CHRVVP342JOA67", services: "a", state: "FI", website: "https://www.northcrypto.com", label: "NorthCrypto custody in Finland", why: "comment is administrative ('Passporting information updated')" },
  { id: "scheich-i", lei: "54930079HJ1JTMKTW637", services: "i", state: "DE", website: "", label: "Bankhaus Scheich portfolio management", why: "letters shifted against descriptions - the LLM alone can't grant it" },
  { id: "bitpanda-listed-lei", lei: "5493007WZ7IFULIL8G21", services: "a", state: "AT", website: "", label: "Bitpanda under the LEI ESMA lists", why: "GLEIF retired that LEI (successor exists)" },
  { id: "bitpanda-current-lei", lei: "98450086582EV2FFC109", services: "a", state: "AT", website: "", label: "Bitpanda under its current LEI", why: "ESMA's register doesn't list the current LEI" },
  { id: "decubate-nl", lei: "894500ZVOL3A9LO8LN34", services: "f", state: "NL", website: "", label: "Decubate placing in the Netherlands", why: "authorisation withdrawn 26/03/2026" },
  { id: "bybit-clone", lei: BYBIT, services: "a", state: "DE", website: "https://bybit.eu.secure-login.com", label: "Bybit's LEI quoted by a look-alike site", why: "website is not the one the register lists" },
  { id: "warned-site", lei: BYBIT, services: "a", state: "DE", website: "https://www.bank-bit.com", label: "Bybit's LEI quoted by an ESMA-warned site", why: "website is on ESMA's non-compliant list" },
  { id: "etoro-gr", lei: "213800GIFQMSV7HROS23", services: "a", state: "GR", website: "", label: "eToro custody in Greece", why: "register writes Greece as 'EL'" },
  { id: "coinbase-lu", lei: "984500F14CA4571AAC11", services: "a", state: "LU", website: "https://www.coinbase.com", label: "Coinbase Luxembourg custody", why: "register writes its website 'https.//coinbase.com'" },
];

async function main() {
  const [address, first = "0", last = String(CASES.length - 1)] = process.argv.slice(2);
  const c = client();
  const log = fs.existsSync("live_proof.json") ? JSON.parse(fs.readFileSync("live_proof.json", "utf-8")) : [];
  const registered = new Set(
    ((await readClient().readContract({ address, functionName: "list_inquiries", args: [] })) as any[]).map((q: any) =>
      q instanceof Map ? q.get("inquiry_id") : q.inquiry_id)
  );
  for (let i = Number(first); i <= Number(last); i++) {
    const k = CASES[i];
    let registerTx = "";
    if (!registered.has(k.id)) {
      registerTx = (await write(c, address, "register_inquiry", [k.id, k.lei, k.services, k.state, k.website, k.label])).hash;
      registered.add(k.id);
    }
    const { hash, tx } = await write(c, address, "attest", [k.id]);
    const r: any = JSON.parse(safeJson(await readClient().readContract({ address, functionName: "latest_check", args: [k.id] })));
    const row = {
      case: i, inquiry_id: k.id, label: k.label, why: k.why, register_tx: registerTx, attest_tx: hash,
      votes: tx.last_round?.validator_votes_name ?? [], verdict: r.verdict, reasons: r.reasons, coverage: r.coverage,
      entity_name: r.entity_name, restriction_evidence: r.restriction_evidence, llm: r.llm, facts: r.facts,
      checked_at: r.checked_at,
    };
    log.push(row);
    fs.writeFileSync("live_proof.json", JSON.stringify(log, null, 1));
    console.log(`CASE ${i} ${k.id}: ${row.verdict} ${safeJson(row.reasons)} coverage=${safeJson(row.coverage)} llm=${safeJson(row.llm)}`);
  }
  for (const [id, maxAge] of [["bybit-de", 3600], ["bybit-de", 1], ["hpb-hr", 999999999]] as [string, number][]) {
    const r = await readClient().readContract({ address, functionName: "is_authorised", args: [id, maxAge] });
    console.log(`is_authorised(${id}, ${maxAge}) = ${r}`);
  }
  process.exit(0);
}

main().catch((e) => {
  console.error(e?.shortMessage ?? e?.message ?? e);
  process.exit(1);
});
