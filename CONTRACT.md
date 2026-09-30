# LicenceCheck — deployment and live proof

## Deployment

| | |
|---|---|
| Network | GenLayer Studio Next, chain 61997 (`chains.studioDevnet`, genlayer-js 2.0.0-rc.1) |
| Contract | [`0x301740e01AB6b7538B9078D9ec98914540b4B91F`](https://explorer-studio-dev.genlayer.com/address/0x301740e01AB6b7538B9078D9ec98914540b4B91F) |
| Deploy tx | [`0xdf46a23612039073cab6d4ebd7067ff769e64a7451f8f9da7b65b18e0356396c`](https://explorer-studio-dev.genlayer.com/tx/0xdf46a23612039073cab6d4ebd7067ff769e64a7451f8f9da7b65b18e0356396c) |
| Source deployed | [`contracts/licence_check_studio_next.py`](contracts/licence_check_studio_next.py) — mechanical port of the tested [`contracts/licence_check.py`](contracts/licence_check.py) |
| Runner | `py-genlayer:5jycge4q8k23462jtb0b9fyey1s9qz928sz2nbrd9mg4sxqg2qng` (v0.3.0) |
| Deployer | `0x5cdb5699bc1038e115A973bb91A646f7E98C075b` |

Checked against the live runner with `getContractSchemaForCode` before deploying (`studio-next/check_schema.ts`): 12 methods, 10 view / 2 write.

**The code on-chain is byte-identical to the repo's port** — `cd studio-next && npx tsx verify_code.ts <address>` fetches it from the chain (`gen_getContractCode`) and compares: both are SHA-256 `648832c871eafed4ebd202bdac9a36af3c4fd83d41dd07b6a78b29c9e3f721c9`.

## Live proof (30 September 2026)

Reproduce with `cd studio-next && npx tsx prove.ts 0x301740e01AB6b7538B9078D9ec98914540b4B91F`. Every row is from [`studio-next/live_proof.json`](studio-next/live_proof.json), written by that script as it ran — including each check's full facts and both readers' outputs. All 13 checks read the same ESMA register (362 entries, newest genuine update 2026-09-22) and warning list (173 entries). "Agree" counts the validators that actively voted (Studio Next leaves the rest of the 5-seat committee idle). **Every one of the 13 committees was unanimous.**

| # | Inquiry | What it tests | Verdict | Reasons | Transactions | Agree |
|---|---|---|---|---|---|---|
| 0 | Bybit EU custody + fiat exchange in Germany<br>`5299005V5GBSN2A4C303` ac in DE via bybit.eu | both readers agree, identity current, website listed | **AUTHORISED** | — | [reg](https://explorer-studio-dev.genlayer.com/tx/0x187cf14a2aa87511b96250c1df9ba3a6b8e872f9d746f8917efe8567f3b9b472) · [check](https://explorer-studio-dev.genlayer.com/tx/0x0f2797eff305cb9f01d038e940bdf89d0d096f95d89561edfb20768edecd2811) | 3/3 |
| 1 | Bybit EU custody in Malta<br>`5299005V5GBSN2A4C303` a in MT | authorised, but not passported to Malta | **NOT_AUTHORISED** | `service_not_covered:a` | [reg](https://explorer-studio-dev.genlayer.com/tx/0x7d05164df6bd6e054b4f046e6522f137ab7229c4e120fbd14de79a1744c5c131) · [check](https://explorer-studio-dev.genlayer.com/tx/0x257f930850f2b30a66b812ccf46db4b9e3d6657f90b8699de4f95b43be45647e) | 3/3 |
| 2 | HPB custody in Croatia<br>`529900D5G4V6THXC5P79` a in HR | regulator comment limits it to one fund | **AUTHORISED_RESTRICTED** | `regulator_comment_restricts:row_229` | [reg](https://explorer-studio-dev.genlayer.com/tx/0x8fe4fd2faa52beb65b64bcc99c5fc330d955f712f19cf6faed63285ea293323c) · [check](https://explorer-studio-dev.genlayer.com/tx/0xcc26619bdb276380041be3604c441778f08bb0982061dea9dd381e34711d6b71) | 3/3 |
| 3 | BLUE EMI custody in Lithuania<br>`254900XFMACGD0L7AI73` a in LT | regulator comment limits it to its own e-money token | **AUTHORISED_RESTRICTED** | `regulator_comment_restricts:row_269` | [reg](https://explorer-studio-dev.genlayer.com/tx/0xd2086ef1b3a67b473977ca8a8563dd863ffda0bdd2fca19924081930616e0b65) · [check](https://explorer-studio-dev.genlayer.com/tx/0x0e910848db826fd00001cace2f8f3c476c38816037d46bcd82ff8ec8f4927600) | 3/3 |
| 4 | NorthCrypto custody in Finland<br>`743700CHRVVP342JOA67` a in FI via northcrypto.com | comment is administrative ('Passporting information updated') | **AUTHORISED** | — | [reg](https://explorer-studio-dev.genlayer.com/tx/0xfcea6addd245eab3d4e7455c7110cc2ffd0201951e039cb17120299eef15f256) · [check](https://explorer-studio-dev.genlayer.com/tx/0xdd36bb4871fc926a31bb2215326d2ac3ebe1b6f3fe49ad3ae2d21119569940bd) | 3/3 |
| 5 | Bankhaus Scheich portfolio management<br>`54930079HJ1JTMKTW637` i in DE | letters shifted against descriptions — the LLM says yes, the deterministic reader can't confirm, so it isn't granted | **UNVERIFIED** | `service_ambiguous:i` | [reg](https://explorer-studio-dev.genlayer.com/tx/0xaacdef6b768cb7b63c449e615a6a06bf6ecea708c91ecc70a1090a352f4e6c63) · [check](https://explorer-studio-dev.genlayer.com/tx/0xf8353ab7fe455aa4724a8b2e887f40a7c860f802b221fda00b2d7a6e3f2e3a10) | 3/3 |
| 6 | Bitpanda under the LEI ESMA lists<br>`5493007WZ7IFULIL8G21` a in AT | GLEIF marks that LEI `RETIRED`, with a successor | **UNVERIFIED** | `lei_not_current:RETIRED/INACTIVE:successor_98450086582EV2FFC109` | [reg](https://explorer-studio-dev.genlayer.com/tx/0xdaabc589f8ccfd2e82602ba6fe52ebdedf818ee4cde4d964b6e637c29505ddec) · [check](https://explorer-studio-dev.genlayer.com/tx/0x7662265e1d166a98de7b1db12cdd3aff1c0c838ae2a6a67c33959b85ea5866b5) | 3/3 |
| 7 | Bitpanda under its current LEI<br>`98450086582EV2FFC109` a in AT | ESMA's register doesn't list the current LEI | **NOT_LISTED** | `lei_not_in_register` | [reg](https://explorer-studio-dev.genlayer.com/tx/0x0b5411ea8951261b34338bf6bd63f4ce3023b06e35acf523f03e3f0f211552e9) · [check](https://explorer-studio-dev.genlayer.com/tx/0x899126f131051564122bbc84a02c6469770f1ff342427352bdc413baf5f3489b) | 3/3 |
| 8 | Decubate placing in the Netherlands<br>`894500ZVOL3A9LO8LN34` f in NL | authorisation withdrawn 26/03/2026 | **WITHDRAWN** | `authorisation_withdrawn` | [reg](https://explorer-studio-dev.genlayer.com/tx/0x91f77e13a29ed4a9ca756cb2d6f429213751652a37f075c0425efe559a97144c) · [check](https://explorer-studio-dev.genlayer.com/tx/0x954daca96df2a4e7b690e6ba59e30c1ca628cb1bb40e86268b4a5259eb7d98a2) | 3/3 |
| 9 | Bybit's LEI quoted by a look-alike site<br>`5299005V5GBSN2A4C303` a in DE via bybit.eu.secure-login.com | website is not the one the register lists | **UNVERIFIED** | `website_not_in_register` | [reg](https://explorer-studio-dev.genlayer.com/tx/0x7519a243f66389286ca91a5d30ef7a1becacc24c2f59b6266c7997fa74d49dcd) · [check](https://explorer-studio-dev.genlayer.com/tx/0x28f6dff1edd56e5cf8324a924a88e9a200bbb8335375d73d2f47c28cdefb4737) | 3/3 |
| 10 | Bybit's LEI quoted by an ESMA-warned site<br>`5299005V5GBSN2A4C303` a in DE via bank-bit.com | website is on ESMA's non-compliant list | **WARNING_LISTED** | `esma_warning_list:website:bank-bit.com`, `website_not_in_register` | [reg](https://explorer-studio-dev.genlayer.com/tx/0x0bc3f4271879ad9db07a353ac382296f1e87dc5c19bdc980ca2ed077524dcd7f) · [check](https://explorer-studio-dev.genlayer.com/tx/0x5d0adcdb3b93779123531d90679fc43e7f2956d99797a4bc773ef33ef45fdf83) | 3/3 |
| 11 | eToro custody in Greece<br>`213800GIFQMSV7HROS23` a in GR | register writes Greece as 'EL' | **AUTHORISED** | — | [reg](https://explorer-studio-dev.genlayer.com/tx/0xb1452ccbfc6f8a1a4354974b4dbaa7808bc746b06f5b29e0743130e647954240) · [check](https://explorer-studio-dev.genlayer.com/tx/0x861249fa818c63391cbd457723c9f6d989fdc7a0031657ae72fae0e855707489) | 3/3 |
| 12 | Coinbase Luxembourg custody<br>`984500F14CA4571AAC11` a in LU via coinbase.com | register writes its website 'https.//coinbase.com' | **AUTHORISED** | — | [reg](https://explorer-studio-dev.genlayer.com/tx/0x9e35fd6f00ff1b59198413a9a6530f531c4097c71cd194779202cea41ce05b66) · [check](https://explorer-studio-dev.genlayer.com/tx/0xf260ec936b1fff8d7ebda133ea405876718b257270e7ed5c7935b4e9a171506e) | 3/3 |

Consumer view, read after the run:

```
is_authorised("bybit-de", 3600)      = true    # AUTHORISED, checked minutes ago
is_authorised("bybit-de", 1)         = false   # same check, but older than 1 second
is_authorised("hpb-hr", 999999999)   = false   # AUTHORISED_RESTRICTED is never "authorised" to a contract
```

### What the readers actually said

Case 0 — Bybit EU, services a + c in Germany (`AUTHORISED`). The register entry, both readers, and GLEIF:
```json
{"entry": {"row": 2, "name": "Bybit EU GmbH", "authority": "Austrian Financial Market Authority (FMA)",
  "home_state": "AT", "status": "ACTIVE", "det": {"a": "YES", "c": "YES"},
  "services_text": "a. providing custody and administration of crypto-assets on behalf of clients | c. exchange of crypto-assets for funds | d. exchange of crypto-assets for other crypto-assets | f. placing of crypto-assets | j. providing transfer services for crypto-assets on behalf of clients"},
 "llm": [{"row": 2, "services": {"a": true, "c": true}, "restricts": false, "evidence": null}],
 "gleif": {"lei": "5299005V5GBSN2A4C303", "registration_status": "ISSUED", "entity_status": "ACTIVE", "legal_name": "Bybit EU GmbH"},
 "website_listed": true, "warnings": []}
```

Case 2 — HPB (`AUTHORISED_RESTRICTED`). Both readers find custody; the LLM flags the Croatian National Bank's comment and quotes it verbatim, which every validator checked against its own copy:
```json
{"comment": "The crypto-asset services are limited solely to a Passive Digital Assets (PDA) AIF",
 "llm": [{"row": 229, "services": {"a": true}, "restricts": true,
          "evidence": "The crypto-asset services are limited solely to a Passive Digital Assets (PDA) AIF"}]}
```
Case 4 — NorthCrypto, comment *"Passporting information updated"*: the same reader returns `"restricts": false` → `AUTHORISED`. That contrast is the job a keyword filter can't do.

Case 5 — Bankhaus Scheich, service i (`UNVERIFIED`). The LLM says yes (judging *"h. providing portfolio management"* by its description); the deterministic reader finds that description but no *"i."* letter anywhere in the entry, so it says `AMBIGUOUS`. Disagreement is never resolved in the LLM's favour:
```json
{"det": {"i": "AMBIGUOUS"}, "llm": [{"row": 75, "services": {"i": true}, "restricts": false, "evidence": null}]}
```

Case 6 — Bitpanda under the LEI ESMA lists (`UNVERIFIED`). The register entry is live and both readers find custody, but GLEIF says:
```json
{"lei": "5493007WZ7IFULIL8G21", "registration_status": "RETIRED", "entity_status": "INACTIVE",
 "legal_name": "Bitpanda GmbH", "successor_lei": "98450086582EV2FFC109"}
```
and case 7 shows ESMA's register doesn't list that successor (`NOT_LISTED`). Neither is papered over: a relying contract gets "can't confirm", with the reason.

Case 10 — Bybit's genuine LEI, quoted from `bank-bit.com` (`WARNING_LISTED`). The LLM isn't even consulted — nothing it could say would change the outcome:
```json
{"warnings": [{"name": "Bank Bit", "authority": "Financial Services and Markets Authority (FSMA)",
               "decision_date": "29/06/2026", "matched_on": "website:bank-bit.com"}],
 "website_listed": false, "llm": []}
```

## Earlier deployment (superseded)

| Address | Why superseded |
|---|---|
| `0xAB274F89F87793373ea1475011Ab85A9fFc76f46` | First deployment — produced the same verdicts on every case above. Review before submission added two fail-closed checks: more register entries for one LEI than the contract reads is now `UNVERIFIED` (previously the extras were ignored), and GLEIF's record must be for the LEI asked about. |
