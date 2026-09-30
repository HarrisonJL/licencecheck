// Live demo / operator CLI for LicenceCheck on Studio Next.
//
//   npx tsx demo.ts <address> register <inquiry_id> <lei> <services> <member_state> <website|-> <label...>
//   npx tsx demo.ts <address> attest <inquiry_id>
//   npx tsx demo.ts <address> show <inquiry_id>
//   npx tsx demo.ts <address> authorised <inquiry_id> <max_age_seconds>
//   npx tsx demo.ts <address> state
import { client, readClient, write, safeJson } from "./lib";

const get = (o: any, k: string) => (o instanceof Map ? o.get(k) : o?.[k]);

async function main() {
  const [address, cmd, ...rest] = process.argv.slice(2);
  if (!address || !cmd) throw new Error("usage: demo.ts <address> <register|attest|show|authorised|state> ...");

  if (cmd === "register") {
    const [id, lei, services, state, website, ...label] = rest;
    await write(client(), address, "register_inquiry", [id, lei, services, state, website === "-" ? "" : website, label.join(" ")]);
  } else if (cmd === "attest") {
    await write(client(), address, "attest", [rest[0]]);
    await show(address, rest[0]);
  } else if (cmd === "show") {
    await show(address, rest[0]);
  } else if (cmd === "authorised") {
    const r = await readClient().readContract({ address, functionName: "is_authorised", args: [rest[0], Number(rest[1])] });
    console.log(`is_authorised(${rest[0]}, ${rest[1]}) = ${r}`);
  } else if (cmd === "state") {
    const c = readClient();
    console.log("get_state:", safeJson(await c.readContract({ address, functionName: "get_state", args: [] })));
    console.log("list_inquiries:", safeJson(await c.readContract({ address, functionName: "list_inquiries", args: [] }), 1));
  }
  process.exit(0);
}

async function show(address: string, id: string) {
  const c: any = await readClient().readContract({ address, functionName: "latest_check", args: [id] });
  console.log(`\n${id}: ${get(c, "verdict")}  reasons=${safeJson(get(c, "reasons"))}`);
  const facts = get(c, "facts");
  if (!facts) return;
  const g = get(facts, "gleif");
  console.log(`  ${get(c, "entity_name")} | services=${get(facts, "services")} in ${get(facts, "member_state")} | coverage=${safeJson(get(c, "coverage"))}`);
  console.log(`  register rows=${get(facts, "register_rows")} as_of=${get(facts, "register_as_of")} | warning list rows=${get(facts, "warning_list_rows")} hits=${safeJson(get(facts, "warnings"))}`);
  console.log(`  GLEIF ${get(g, "registration_status")}/${get(g, "entity_status")} "${get(g, "legal_name")}" successor=${get(g, "successor_lei") || "-"} | website=${get(facts, "website") || "-"} listed=${get(facts, "website_listed")}`);
  for (const e of get(facts, "entries") ?? []) {
    console.log(`  entry row ${get(e, "row")}: ${get(e, "name")} [${get(e, "authority")}] home=${get(e, "home_state")} status=${get(e, "status")} det=${safeJson(get(e, "det"))} comment="${get(e, "comment")}"`);
  }
  for (const r of get(c, "llm") ?? []) {
    console.log(`  LLM row ${get(r, "row")}: services=${safeJson(get(r, "services"))} restricts=${get(r, "restricts")} evidence=${safeJson(get(r, "evidence"))}`);
  }
  if (get(c, "restriction_evidence")) console.log(`  restriction_evidence="${get(c, "restriction_evidence")}"`);
  console.log(`  check_id=${get(c, "check_id")} checked_at=${get(c, "checked_at")}`);
}

main().catch((e) => {
  console.error(e?.shortMessage ?? e?.message ?? e);
  process.exit(1);
});
