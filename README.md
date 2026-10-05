# LicenceCheck

**Is this counterparty authorised under MiCA to provide *these* crypto-asset services in *this* EU/EEA country, right now?** A GenLayer Intelligent Contract that reads ESMA's official MiCA register live — every validator independently — cross-checks identity against GLEIF and screens against ESMA's own non-compliant-entity list, and publishes a verdict a downstream contract can gate on.

| | |
|---|---|
| Network | GenLayer Studio Next (chain 61997) |
| Contract | [`0x301740e01AB6b7538B9078D9ec98914540b4B91F`](https://explorer-studio-dev.genlayer.com/address/0x301740e01AB6b7538B9078D9ec98914540b4B91F) |
| Deploy tx | [`0xdf46a236…396c`](https://explorer-studio-dev.genlayer.com/tx/0xdf46a23612039073cab6d4ebd7067ff769e64a7451f8f9da7b65b18e0356396c) |
| Live proof | [CONTRACT.md](CONTRACT.md) — 13 real firms, all 7 verdicts, every tx linked, every committee unanimous |
| Tests | 69 Direct Mode tests on the **real, unmodified** ESMA register; 36/36 safety mutations killed |

## Why this exists

Since MiCA's transitional period ended, a crypto-asset service provider needs a MiCA authorisation for each service it offers, in each member state it offers it. A treasury, a DAO or a payments contract that wants to deal only with authorised counterparties has two options today: a person reads a register once, or a compliance vendor's API nobody can re-check. Neither is something a smart contract can rely on.

LicenceCheck turns "is X authorised for custody in Germany?" into a public, repeatable, consensus-backed answer that a contract can require — fresh, per service, per country.

## The register is messier than it looks

ESMA publishes the interim MiCA register as CSV files. Read carefully, the live file (24 September 2026, 362 entries) contains:

- **Service letters that contradict their descriptions** — Bankhaus Scheich's entry lists *"c. exchange of crypto-assets for other crypto-assets"* (that's d), *"e. placing"* (f), *"g. providing advice"* (h), *"h. providing portfolio management"* (i).
- **Services run together** with `|`, ` I `, `/`, `,` or nothing at all; some cut off mid-word; some in prose with no letters.
- **Greece as "EL"** — how *most* of the register writes it; a lookup for "GR" would call nearly every CASP unpassported to Greece.
- **"SL" for Slovenia** (AMINA, FIOR Digital), **"Fi"**, spaces inside country lists.
- **A home state missing from its own passport list** — OKX Europe is authorised by Malta's MFSA; "MT" isn't in its list.
- **A website written `https.//coinbase.com`**, and two entries with prose instead of a URL.
- **Malformed LEIs** (19 and 21 characters, a trailing full stop).
- **A retired LEI still listed**: Bitpanda GmbH appears under `5493007WZ7IFULIL8G21`, which GLEIF now marks `RETIRED` (record last updated 2026-06-24) with successor `98450086582EV2FFC109` — which the register doesn't list.
- A "last update" dated **2028**.
- Free-text regulator comments that **materially limit** an authorisation (*"limited solely to a Passive Digital Assets (PDA) AIF"*, *"in relation to own issued EMT called BLUEUR"*, *"Voluntary request to revoke authorisation"*) sitting next to purely administrative ones (*"Passporting information updated"*).

A deterministic parser alone mis-grants on the first bullet; an LLM alone can hallucinate. So the contract uses both, and neither is allowed to grant on its own.

## How it decides

### 1. Primary sources only — and the contract picks them

Every validator fetches, as raw bytes, three fixed sources built by the contract: ESMA's `CASPS.csv`, ESMA's `NCASP.csv` (the non-compliant-entities list), and the GLEIF record for the LEI. A caller supplies an LEI (ISO 17442 — **checksum-verified on-chain**, so a typo never costs a check), service letters `a`–`j`, a member state and optionally the website they're dealing with. **No caller-supplied text ever reaches the LLM prompt** — only ESMA's text and the contract's own MiCA service catalogue.

### 2. Two independent readers must agree

For each requested service, in each register entry for that LEI:

- a **deterministic reader** matches each MiCA service's distinctive wording (*"custody and administration"*, *"trading platform"*, …) and, where an entry uses letters at all, requires the letter **and** the description to both be present — a letter with no matching description, or a description under the wrong letter, is `AMBIGUOUS`, never a guess;
- an **LLM reader** reads the entry judging by the description wording (the prompt says why: some entries carry the wrong letter).

| Deterministic | LLM | Service is… |
|---|---|---|
| YES | yes | covered |
| NO | no | not covered |
| anything else | | **ambiguous → UNVERIFIED** |

Live proof: Bankhaus Scheich, service *i*. The LLM reads *"h. providing portfolio management"* and says yes; the deterministic reader sees no *"i."* anywhere and says ambiguous. Verdict: `UNVERIFIED` — the LLM could not grant it alone (CONTRACT.md, case 5).

Passporting is deterministic: the requested state must be the firm's home state or in its passport list (`EL` read as Greece). An entry with an unrecognised country token (`SL`) is ambiguous for any state not otherwise listed — most likely a typo for SI, but not the contract's to assume.

### 3. The LLM can only make things stricter

The LLM is also the only thing that can read the regulator's free-text comments. A comment it flags can only move `AUTHORISED` **down**: to `AUTHORISED_RESTRICTED` if it quotes the limiting words verbatim from the comment, or to `UNVERIFIED` if it can't quote them. Nothing the LLM says can produce `AUTHORISED`. Live, the real reader flagged HPB's single-fund limit and BLUE EMI's own-token limit, and correctly left NorthCrypto's *"Passporting information updated"* alone — the distinction a keyword filter can't make.

### 4. Identity and impersonation

- **GLEIF must agree the LEI is current**: registration `ISSUED`/`LAPSED`/pending, entity `ACTIVE`, and the record returned must be for that LEI. A retired LEI is `UNVERIFIED` and names GLEIF's successor (live: Bitpanda).
- **Website check**: if the caller says which website they're dealing with, it must be the register's listed site for that firm, or a subdomain of it — `bybit.eu.secure-login.com` and `fakebybit.eu` are not `bybit.eu` (live: case 9).
- **ESMA warning list**: a website (or LEI) on `NCASP.csv` is `WARNING_LISTED`, even when the LEI it quotes is genuinely authorised (live: Bybit's LEI quoted from a site the Belgian FSMA warned against). Names are deliberately *not* fuzzy-matched — clone sites borrow real firms' names, and a name match would flag the real firm.

### 5. Fail closed

An unreachable or **reshaped** register (a required column renamed), an unreachable warning list, GLEIF unavailable, more matching entries than the contract reads, an unparseable withdrawal date — each is `UNVERIFIED` with a reason, never a half-read. A network-level fetch failure fails the transaction rather than recording anything.

### Verdicts, most severe first

The published verdict is the most severe one any finding supports; `reasons` lists them all.

| Verdict | Meaning |
|---|---|
| `WARNING_LISTED` | The website or LEI is on ESMA's non-compliant-entity list. |
| `NOT_LISTED` | No register entry carries this LEI. |
| `WITHDRAWN` | Every entry for this LEI has a withdrawal date on or before today. |
| `NOT_AUTHORISED` | Listed, but both readers agree a requested service isn't held, or it isn't passported to the requested state. |
| `UNVERIFIED` | Something couldn't be established: readers disagree, identity isn't current at GLEIF, website not the listed one, a source is unavailable or reshaped, a restriction couldn't be quoted. Makes no claim about the firm either way. |
| `AUTHORISED_RESTRICTED` | Covered — but the regulator's comment limits it (verbatim quote recorded). |
| `AUTHORISED` | Every requested service covered in the requested state by both readers, identity current, website (if given) listed, warning list clear, no limiting comment. |

## Equivalence principle

A custom leader/validator pair (`gl.vm.run_nondet`):

1. **Deterministic facts: exact agreement.** Each validator re-fetches the three sources and recomputes every fact — the matched entries (including the exact text the LLM will read), passport lists, warning-list hits, GLEIF status. Any difference rejects the leader. ESMA updates the files roughly weekly; if an update lands between two validators' fetches they disagree and the round rotates, rather than recording a mixed read.
2. **LLM reader: decision-level agreement.** Each validator runs its own reader on the same entry text and must reach the same yes/no per requested service, and the same restriction outcome — including whether the leader's quote really is in the comment.
3. **The verdict is never taken from the leader.** It's recomputed from the agreed facts and readings after consensus.

The consensus-boundary tests (`tests/test_licence_check.py`, section 4) show a validator rejecting: forged register facts (with or without an honest LLM reading alongside), an LLM reading that grants what its own doesn't, a hidden restriction, a restriction with a fabricated quote, an invented unquoted restriction, LLM output where none was needed, misaligned entries, and error/garbage results.

## Using it from another contract

```python
licences = gl.contract.get_at(Address("0x301740e01AB6b7538B9078D9ec98914540b4B91F"))
# True only for AUTHORISED (not RESTRICTED), and only if checked within the last 7 days.
if not licences.view().is_authorised("bybit-de", 7 * 24 * 3600):
    raise gl.vm.UserError("counterparty not MiCA-authorised for this")
```

An inquiry is immutable once registered — which LEI, which services, which state and which website a consumer relies on can't be changed under it. `is_authorised(inquiry_id, max_age_seconds)` reads only the **latest** check, is true only for `AUTHORISED` (a contract can't judge a regulator's scope limit, so `AUTHORISED_RESTRICTED` is false), and only if fresh.

| Method | |
|---|---|
| `register_inquiry(inquiry_id, lei, services, member_state, website, label)` | Permissionless, immutable. `services` like `"a,c"`; `website` may be `""`. |
| `attest(inquiry_id)` | Permissionless fresh check. |
| `is_authorised(inquiry_id, max_age_seconds)` | The consumer view. |
| `latest_check` / `latest_verdict` / `get_check` / `get_checks(offset, limit)` | Full history with facts, both readers' outputs, and reasons. |
| `get_inquiry` / `list_inquiries` / `get_sources` / `service_catalogue` / `get_state` | |

## Testing

```bash
python3 -m venv .venv && .venv/bin/pip install genlayer-test==0.29.2 genvm-linter==0.11.0 pytest
.venv/bin/pytest tests -q                     # 69 tests
python3 scripts/mutation_check.py             # 36/36 mutations killed
.venv/bin/genvm-lint check contracts/licence_check.py
```

- **The real register.** Tests read ESMA's actual `CASPS.csv` and `NCASP.csv`, unmodified (`scripts/build_fixtures.py`; provenance in `tests/fixtures/PROVENANCE.md`), and real GLEIF records. The register's own quirks *are* the test cases. The few synthetic cases (a future withdrawal date, a renamed column) edit one cell of the real file.
- **Every service text in the register** was run through the deterministic reader before deployment: 360 of 362 entries read cleanly; the 2 ambiguous ones are genuinely ambiguous (a truncated *"d."* entry, and Bankhaus Scheich's shifted letters).
- Bugs the real data caught before deployment: a regex whose optional *s* could backtrack past its own lookahead and read *"crypto assets and fiat"* as crypto-for-crypto; the `https.//` typo; the 2028 date; and `import io` (genvm-lint forbids it — replaced with a split proven to parse both files identically).
- **Mutation check.** `tests/mutations.txt` lists 36 deliberate breakages, each removing one safety property (the two-reader rule, the EL alias, the home-state rule, GLEIF checks, grounding, each validator comparison, …). `scripts/mutation_check.py` applies each and confirms the suite fails. All 36 are caught.
- `contracts/licence_check.py` is the tested source (GenVM v0.2.11 — the only generation genlayer-test's Direct Mode runs); `contracts/licence_check_studio_next.py` is its mechanical port, generated by `scripts/port_to_studio_next.py`.

## Known limitations

- **FCA (UK) not covered — shown infeasible, not skipped.** The FCA register's public site is a JavaScript application that fails to load in GenVM's renderer (probe tx [`0x02f0da2d…`](https://explorer-studio-dev.genlayer.com/tx/0x02f0da2d25b61f6a3dbe847c6f9cf8d7bbe3566fb7ec84196df2352992ca4b2c): `WEBPAGE_LOAD_FAILED`), and its API needs a private key that can't be embedded in a public contract. See `research/`.
- **ESMA's interim register URLs may change** as ESMA moves the register into its IT systems. The URLs are deliberately immutable (an owner-updatable URL would let its holder point every check at a file they wrote); if they move, checks fail closed and the contract is redeployed.
- **The interim register is ESMA's compilation of national authorities' data** and can lag them. LicenceCheck attests what ESMA's register says, cross-checked where it can be; it is not legal advice.
- **LEI is the identity key.** A firm the register lists under a malformed or retired LEI can't be confirmed under its correct one — that's reported (`NOT_LISTED` / `UNVERIFIED` with GLEIF's successor), never papered over.
- **`AUTHORISED_RESTRICTED` isn't machine-interpretable** — whether a limit matters depends on the use. The consumer view treats it as not authorised; the verbatim limit is recorded for a person to judge.
- **Warning-list matching is by website host and LEI only.** Most warning-list entries have no LEI, and name matching would flag real firms whose names clones borrow.
- **Availability is never traded for safety.** Anyone can pay for a fresh check, and the latest check wins. If a source is momentarily unreachable, that check records `UNVERIFIED` (or fails and records nothing), and consumers fail closed until the next good check. A griefer can make a good verdict temporarily unavailable, never a bad one look good, and the next check restores it.
- **Prompt injection.** Service text is partly written by the firms, and comments by regulators. Everything the LLM reads is framed as untrusted data, and it can only *withhold or restrict*: `AUTHORISED` needs the deterministic reader to agree, so an injected "yes" cannot grant a service.
- **Inquiry ids are first-come.** Anyone can register an `inquiry_id` before you, with different parameters. Read the immutable record (`get_inquiry`) and pin the parameters you expect rather than trusting an id's name.

## Repository layout

```
contracts/licence_check.py              tested source (GenVM v0.2.11)
contracts/licence_check_studio_next.py  deployed port (Studio Next)
tests/                                  Direct Mode tests, real ESMA + GLEIF fixtures, mutations.txt
scripts/                                fixture capture, port, mutation check
studio-next/                            deploy, schema check, demo CLI, live proof (prove.ts, live_proof.json)
research/                               live connectivity probe used to choose the data path (incl. FCA)
```
