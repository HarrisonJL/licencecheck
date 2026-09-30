"""
Deterministic tests for LicenceCheck using genlayer-test's Direct Mode.

Every test reads the REAL ESMA interim MiCA register (tests/fixtures/
CASPS.csv and NCASP.csv, captured unmodified - see PROVENANCE.md) and real
GLEIF records. The register's own quirks are the test cases: service
letters that contradict their descriptions, "EL" for Greece, "SL" for
Slovenia, a home state missing from its own passport list, a website
written "https.//coinbase.com", a retired LEI still listed. The few
synthetic cases (a future withdrawal date, a renamed column) edit one cell
of the real file, never invent a register.

Four layers:
1. Registration - LEI checksum, service letters, member state, website.
2. Verdicts - every verdict on a real firm.
3. The two-reader rule and the LLM's limits - AUTHORISED needs the
   deterministic reader AND the LLM; the LLM alone can never grant it; a
   restriction needs a verbatim quote.
4. Consensus boundary via direct_vm.run_validator.
"""

import json
import pathlib
import re
import sys

import pytest

FIXTURES = pathlib.Path(__file__).parent / "fixtures"
CASPS_URL = "https://www.esma.europa.eu/sites/default/files/2024-12/CASPS.csv"
NCASP_URL = "https://www.esma.europa.eu/sites/default/files/2024-12/NCASP.csv"
GLEIF = "https://api.gleif.org/api/v1/lei-records/"
NOW = "2026-09-30T12:00:00Z"
LLM_PATTERN = "interim MiCA register of"

BYBIT = "5299005V5GBSN2A4C303"
BITPANDA_LISTED = "5493007WZ7IFULIL8G21"  # RETIRED at GLEIF
BITPANDA_CURRENT = "98450086582EV2FFC109"  # not in ESMA's register
HPB = "529900D5G4V6THXC5P79"  # comment: limited solely to one fund
BLUE_EMI = "254900XFMACGD0L7AI73"  # comment: own e-money token only
NORTHCRYPTO = "743700CHRVVP342JOA67"  # comment: administrative
DECUBATE = "894500ZVOL3A9LO8LN34"  # withdrawn 26/03/2026
COINBASE_LU = "984500F14CA4571AAC11"  # website written "https.//coinbase.com"
TESCO = "2138002P5RNKC5W2JZ46"  # real LEI, not a CASP
ETORO = "213800GIFQMSV7HROS23"  # Greece written "EL"
OKX = "54930069NLWEIGLHXU42"  # home MT missing from its passport list
AMINA = "5299005I4LYIFW7GKB54"  # Slovenia written "SL"
SCHEICH = "54930079HJ1JTMKTW637"  # letters shifted against descriptions


def _fixture(name: str) -> str:
    return (FIXTURES / name).read_bytes().decode("utf-8")


def _mock(direct_vm, url: str, body: str, status: int = 200) -> None:
    direct_vm.mock_web(re.escape(url) + "$", {"method": "GET", "status": status, "body": body})


def _serve(direct_vm, lei: str, casps=None, ncasp=None, gleif=None, casps_status=200, ncasp_status=200,
           gleif_status=200) -> None:
    _mock(direct_vm, CASPS_URL, casps if casps is not None else _fixture("CASPS.csv"), casps_status)
    _mock(direct_vm, NCASP_URL, ncasp if ncasp is not None else _fixture("NCASP.csv"), ncasp_status)
    if gleif is None and gleif_status == 200:
        gleif = _fixture(f"gleif_{lei}.json")
    _mock(direct_vm, GLEIF + lei, gleif if gleif is not None else "{}", gleif_status)


def _reader(direct_vm, entries: list) -> None:
    direct_vm.mock_llm(LLM_PATTERN, json.dumps({"entries": entries}))


def _entry(i: int, services: dict, restricts=False, evidence=None) -> dict:
    return {"entry": i, "services": services, "restricts": restricts, "evidence": evidence}


def _warp(direct_vm, timestamp: str) -> None:
    # genlayer-test 0.29.2's warp() refreshes only sender/origin in the SDK's
    # already-imported gl.message_raw, never its datetime - so after deploy
    # it alone never moves the clock the contract reads. Live GenVM hands
    # every call a fresh timestamp (confirmed on Studio Next - CONTRACT.md).
    direct_vm.warp(timestamp)
    gl = sys.modules.get("genlayer.gl")
    if gl is not None and getattr(gl, "message_raw", None) is not None:
        gl.message_raw["datetime"] = timestamp


def _deploy(direct_vm, direct_deploy, direct_owner):
    direct_vm.warp(NOW)
    direct_vm.sender = direct_owner
    contract = direct_deploy("contracts/licence_check.py")
    _warp(direct_vm, NOW)
    return contract


def _check(lc, direct_vm, inquiry_id: str, lei: str, llm_entries=None, **serve) -> dict:
    direct_vm.clear_mocks()
    _serve(direct_vm, lei, **serve)
    if llm_entries is not None:
        _reader(direct_vm, llm_entries)
    lc.attest(inquiry_id)
    return lc.latest_check(inquiry_id)


def _edit_row(casps: str, lei: str, old: str, new: str) -> str:
    """Edit one cell's text in the real register row carrying this LEI."""
    lines = casps.split("\r\n")
    hits = [i for i, line in enumerate(lines) if lei in line]
    assert len(hits) == 1, f"expected exactly one physical line for {lei}"
    assert old in lines[hits[0]], f"row for {lei} no longer contains {old!r}"
    lines[hits[0]] = lines[hits[0]].replace(old, new, 1)
    return "\r\n".join(lines)


# --- 1. Registration ---------------------------------------------------------


def test_initial_state_and_catalogue(direct_vm, direct_deploy, direct_owner):
    lc = _deploy(direct_vm, direct_deploy, direct_owner)
    assert lc.get_state() == {"inquiry_count": 0, "check_count": 0}
    catalogue = lc.service_catalogue()
    assert sorted(catalogue) == list("abcdefghij")
    assert catalogue["a"] == "providing custody and administration of crypto-assets on behalf of clients"


def test_register_normalises_every_input(direct_vm, direct_deploy, direct_owner):
    lc = _deploy(direct_vm, direct_deploy, direct_owner)
    lc.register_inquiry("bybit-1", BYBIT.lower(), "C, a", "el", "https://www.Bybit.eu/en/", "Bybit EU")
    q = lc.get_inquiry("bybit-1")
    assert (q["lei"], q["services"], q["member_state"], q["website"]) == (BYBIT, "ac", "GR", "bybit.eu")
    assert q["check_count"] == 0
    assert lc.latest_verdict("bybit-1") == "NONE"
    assert lc.is_authorised("bybit-1", 10**6) is False
    assert lc.get_sources("bybit-1") == [CASPS_URL, NCASP_URL, GLEIF + BYBIT]


@pytest.mark.parametrize("field,value", [
    ("inquiry_id", ""), ("inquiry_id", "x" * 33), ("inquiry_id", "has space"), ("inquiry_id", "a/b"),
    ("lei", BYBIT[:-1] + ("1" if BYBIT[-1] != "1" else "2")),  # one-digit typo: checksum fails
    ("lei", "5299005V5GBSN2A4C30"),  # 19 characters
    ("services", ""), ("services", "k"), ("services", "a;b"), ("services", ", ,"),
    ("member_state", "GB"), ("member_state", "US"), ("member_state", ""),
    ("website", "not a website"), ("website", "https://"),
    ("label", ""),
])
def test_register_rejects_invalid_input(direct_vm, direct_deploy, direct_owner, field, value):
    lc = _deploy(direct_vm, direct_deploy, direct_owner)
    args = {"inquiry_id": "q1", "lei": BYBIT, "services": "a", "member_state": "DE", "website": "", "label": "x"}
    args[field] = value
    with pytest.raises(Exception):
        lc.register_inquiry(args["inquiry_id"], args["lei"], args["services"], args["member_state"],
                            args["website"], args["label"])


def test_register_rejects_duplicate_and_attest_rejects_unknown(direct_vm, direct_deploy, direct_owner):
    lc = _deploy(direct_vm, direct_deploy, direct_owner)
    lc.register_inquiry("q1", BYBIT, "a", "DE", "", "Bybit")
    with pytest.raises(Exception):
        lc.register_inquiry("q1", BYBIT, "c", "FR", "", "again")
    with pytest.raises(Exception):
        lc.attest("nope")


# --- 2. Verdicts on real firms ------------------------------------------------


def test_authorised_for_custody_and_fiat_exchange_in_germany(direct_vm, direct_deploy, direct_owner):
    lc = _deploy(direct_vm, direct_deploy, direct_owner)
    lc.register_inquiry("bybit", BYBIT, "a,c", "DE", "https://www.bybit.eu", "Bybit EU")
    c = _check(lc, direct_vm, "bybit", BYBIT, [_entry(0, {"a": True, "c": True})])
    assert c["verdict"] == "AUTHORISED"
    assert c["reasons"] == []
    assert c["coverage"] == {"a": "YES", "c": "YES"}
    assert c["entity_name"] == "Bybit EU GmbH"
    f = c["facts"]
    assert f["register_rows"] == 362
    # Newest genuine update in the file. One row (REGULAR FINANCE SAS) is
    # dated 11/09/2028 - a future date that must not count.
    assert f["register_as_of"] == "2026-09-22"
    assert f["website_listed"] is True
    [entry] = f["entries"]
    assert (entry["authority"], entry["home_state"], entry["status"]) == (
        "Austrian Financial Market Authority (FMA)", "AT", "ACTIVE")
    assert lc.is_authorised("bybit", 3600) is True


def test_not_authorised_for_a_service_it_does_not_hold(direct_vm, direct_deploy, direct_owner):
    lc = _deploy(direct_vm, direct_deploy, direct_owner)
    lc.register_inquiry("bybit-b", BYBIT, "b", "DE", "", "Bybit trading platform")
    c = _check(lc, direct_vm, "bybit-b", BYBIT, [_entry(0, {"b": False})])
    assert c["verdict"] == "NOT_AUTHORISED"
    assert c["reasons"] == ["service_not_covered:b"]


def test_not_authorised_in_a_state_it_has_not_passported_to(direct_vm, direct_deploy, direct_owner):
    # Bybit EU's passport list covers 27 states but not Malta.
    lc = _deploy(direct_vm, direct_deploy, direct_owner)
    lc.register_inquiry("bybit-mt", BYBIT, "a", "MT", "", "Bybit in Malta")
    c = _check(lc, direct_vm, "bybit-mt", BYBIT, [_entry(0, {"a": True})])
    assert c["verdict"] == "NOT_AUTHORISED"
    assert c["reasons"] == ["service_not_covered:a"]


def test_home_state_is_covered_even_when_missing_from_the_passport_list(direct_vm, direct_deploy, direct_owner):
    # OKX Europe is authorised by Malta's MFSA; its own list omits "MT".
    lc = _deploy(direct_vm, direct_deploy, direct_owner)
    lc.register_inquiry("okx-mt", OKX, "b", "MT", "", "OKX in Malta")
    c = _check(lc, direct_vm, "okx-mt", OKX, [_entry(0, {"b": True})])
    assert "MT" not in c["facts"]["entries"][0]["countries"]
    assert c["verdict"] == "AUTHORISED"


def test_greece_written_el_is_read_as_greece(direct_vm, direct_deploy, direct_owner):
    # Most of the register writes Greece "EL"; without the alias nearly every
    # CASP would read as not passported to Greece.
    lc = _deploy(direct_vm, direct_deploy, direct_owner)
    lc.register_inquiry("etoro-gr", ETORO, "a", "GR", "", "eToro in Greece")
    c = _check(lc, direct_vm, "etoro-gr", ETORO, [_entry(0, {"a": True})])
    assert "GR" in c["facts"]["entries"][0]["countries"]
    assert c["verdict"] == "AUTHORISED"


def test_unrecognised_country_token_is_ambiguous_not_a_refusal(direct_vm, direct_deploy, direct_owner):
    # AMINA's list says "SL" and never "SI". Most likely a typo for Slovenia -
    # but the contract doesn't assume it either way.
    lc = _deploy(direct_vm, direct_deploy, direct_owner)
    lc.register_inquiry("amina-si", AMINA, "a", "SI", "", "AMINA in Slovenia")
    c = _check(lc, direct_vm, "amina-si", AMINA, [_entry(0, {"a": True})])
    assert c["facts"]["entries"][0]["countries_unrecognised"] == ["SL"]
    assert c["verdict"] == "UNVERIFIED"
    assert c["reasons"] == ["service_ambiguous:a"]


def test_website_not_listed_for_this_firm_is_unverified(direct_vm, direct_deploy, direct_owner):
    # A real, authorised LEI - quoted by a site the register doesn't list.
    lc = _deploy(direct_vm, direct_deploy, direct_owner)
    lc.register_inquiry("clone", BYBIT, "a", "DE", "bybit-eu-login.com", "Bybit look-alike")
    c = _check(lc, direct_vm, "clone", BYBIT, [_entry(0, {"a": True})])
    assert c["facts"]["website_listed"] is False
    assert c["verdict"] == "UNVERIFIED"
    assert c["reasons"] == ["website_not_in_register"]
    assert lc.is_authorised("clone", 10**6) is False


def test_subdomain_of_a_listed_website_is_accepted(direct_vm, direct_deploy, direct_owner):
    lc = _deploy(direct_vm, direct_deploy, direct_owner)
    lc.register_inquiry("sub", BYBIT, "a", "DE", "https://app.bybit.eu/login", "Bybit app")
    c = _check(lc, direct_vm, "sub", BYBIT, [_entry(0, {"a": True})])
    assert c["verdict"] == "AUTHORISED"


@pytest.mark.parametrize("lookalike", ["https://bybit.eu.secure-login.com", "fakebybit.eu", "bybit.eu-verify.com"])
def test_lookalike_domains_containing_the_listed_one_are_not_accepted(direct_vm, direct_deploy, direct_owner,
                                                                     lookalike):
    lc = _deploy(direct_vm, direct_deploy, direct_owner)
    lc.register_inquiry("look", BYBIT, "a", "DE", lookalike, "look-alike")
    c = _check(lc, direct_vm, "look", BYBIT, [_entry(0, {"a": True})])
    assert c["facts"]["website_listed"] is False
    assert c["verdict"] == "UNVERIFIED"


def test_register_website_typo_still_matches(direct_vm, direct_deploy, direct_owner):
    # Coinbase Luxembourg's entry reads "https.//coinbase.com".
    lc = _deploy(direct_vm, direct_deploy, direct_owner)
    lc.register_inquiry("cb", COINBASE_LU, "a", "LU", "https://www.coinbase.com", "Coinbase LU")
    c = _check(lc, direct_vm, "cb", COINBASE_LU, [_entry(0, {"a": True})])
    assert c["facts"]["entries"][0]["website_hosts"] == ["coinbase.com"]
    assert c["verdict"] == "AUTHORISED"


def test_website_on_esma_warning_list_is_warning_listed(direct_vm, direct_deploy, direct_owner):
    # Someone quoting Bybit's real LEI from a site ESMA lists as non-compliant.
    # The LLM isn't consulted (no mock): nothing it said could change this.
    lc = _deploy(direct_vm, direct_deploy, direct_owner)
    lc.register_inquiry("warned", BYBIT, "a", "DE", "https://www.bank-bit.com", "Bybit?")
    c = _check(lc, direct_vm, "warned", BYBIT)
    assert c["verdict"] == "WARNING_LISTED"
    assert c["reasons"][0] == "esma_warning_list:website:bank-bit.com"
    [w] = c["facts"]["warnings"]
    assert w["name"] == "Bank Bit"
    assert w["authority"] == "Financial Services and Markets Authority (FSMA)"
    assert c["llm"] == []


def test_retired_lei_still_listed_by_esma_is_unverified_and_names_the_successor(direct_vm, direct_deploy, direct_owner):
    # ESMA lists Bitpanda GmbH under an LEI GLEIF now marks RETIRED (record
    # last updated 2026-06-24), with a successor LEI ESMA doesn't list.
    lc = _deploy(direct_vm, direct_deploy, direct_owner)
    lc.register_inquiry("bp-old", BITPANDA_LISTED, "a", "AT", "", "Bitpanda (listed LEI)")
    c = _check(lc, direct_vm, "bp-old", BITPANDA_LISTED, [_entry(0, {"a": True})])
    assert c["coverage"] == {"a": "YES"}
    assert c["verdict"] == "UNVERIFIED"
    assert c["reasons"] == ["lei_not_current:RETIRED/INACTIVE:successor_" + BITPANDA_CURRENT]


def test_current_lei_absent_from_register_is_not_listed(direct_vm, direct_deploy, direct_owner):
    lc = _deploy(direct_vm, direct_deploy, direct_owner)
    lc.register_inquiry("bp-new", BITPANDA_CURRENT, "a", "AT", "", "Bitpanda (current LEI)")
    c = _check(lc, direct_vm, "bp-new", BITPANDA_CURRENT)  # no LLM: nothing to read
    assert c["verdict"] == "NOT_LISTED"
    assert c["reasons"] == ["lei_not_in_register"]
    assert c["entity_name"] == "Bitpanda GmbH"


def test_non_casp_is_not_listed(direct_vm, direct_deploy, direct_owner):
    lc = _deploy(direct_vm, direct_deploy, direct_owner)
    lc.register_inquiry("tesco", TESCO, "a", "IE", "", "Tesco")
    assert _check(lc, direct_vm, "tesco", TESCO)["verdict"] == "NOT_LISTED"


def test_withdrawn_authorisation(direct_vm, direct_deploy, direct_owner):
    lc = _deploy(direct_vm, direct_deploy, direct_owner)
    lc.register_inquiry("decubate", DECUBATE, "f", "NL", "", "Decubate")
    c = _check(lc, direct_vm, "decubate", DECUBATE)  # no LLM: nothing live to read
    assert c["verdict"] == "WITHDRAWN"
    assert c["facts"]["entries"][0]["end_date"] == "26/03/2026"


def test_scheduled_withdrawal_counts_only_once_its_date_passes(direct_vm, direct_deploy, direct_owner):
    lc = _deploy(direct_vm, direct_deploy, direct_owner)
    lc.register_inquiry("bybit", BYBIT, "a", "DE", "", "Bybit")
    casps = _edit_row(_fixture("CASPS.csv"), BYBIT, ",28/05/2025,,", ",28/05/2025,31/12/2026,")
    before = _check(lc, direct_vm, "bybit", BYBIT, [_entry(0, {"a": True})], casps=casps)
    assert before["verdict"] == "AUTHORISED"
    _warp(direct_vm, "2027-01-01T00:00:00Z")
    after = _check(lc, direct_vm, "bybit", BYBIT, casps=casps)
    assert after["verdict"] == "WITHDRAWN"


def test_unparseable_withdrawal_date_is_ambiguous(direct_vm, direct_deploy, direct_owner):
    lc = _deploy(direct_vm, direct_deploy, direct_owner)
    lc.register_inquiry("bybit", BYBIT, "a", "DE", "", "Bybit")
    casps = _edit_row(_fixture("CASPS.csv"), BYBIT, ",28/05/2025,,", ",28/05/2025,TBC,")
    c = _check(lc, direct_vm, "bybit", BYBIT, [_entry(0, {"a": True})], casps=casps)
    assert c["facts"]["entries"][0]["status"] == "UNKNOWN"
    assert c["verdict"] == "UNVERIFIED"
    assert c["reasons"] == ["service_ambiguous:a"]


def test_register_unreachable_fails_closed(direct_vm, direct_deploy, direct_owner):
    lc = _deploy(direct_vm, direct_deploy, direct_owner)
    lc.register_inquiry("bybit", BYBIT, "a", "DE", "", "Bybit")
    c = _check(lc, direct_vm, "bybit", BYBIT, casps="unavailable", casps_status=503)
    assert c["verdict"] == "UNVERIFIED"
    assert c["reasons"] == ["register_unavailable:503"]


def test_reshaped_register_fails_closed(direct_vm, direct_deploy, direct_owner):
    lc = _deploy(direct_vm, direct_deploy, direct_owner)
    lc.register_inquiry("bybit", BYBIT, "a", "DE", "", "Bybit")
    casps = _fixture("CASPS.csv").replace("ac_serviceCode,", "ac_services,", 1)
    c = _check(lc, direct_vm, "bybit", BYBIT, casps=casps)
    assert c["verdict"] == "UNVERIFIED"
    assert c["reasons"] == ["register_format_changed"]


def test_warning_list_unreachable_blocks_authorised(direct_vm, direct_deploy, direct_owner):
    lc = _deploy(direct_vm, direct_deploy, direct_owner)
    lc.register_inquiry("bybit", BYBIT, "a", "DE", "", "Bybit")
    c = _check(lc, direct_vm, "bybit", BYBIT, [_entry(0, {"a": True})], ncasp="err", ncasp_status=500)
    assert c["verdict"] == "UNVERIFIED"
    assert c["reasons"] == ["warning_list_unavailable:500"]


def test_lei_unknown_to_gleif_blocks_authorised(direct_vm, direct_deploy, direct_owner):
    lc = _deploy(direct_vm, direct_deploy, direct_owner)
    lc.register_inquiry("bybit", BYBIT, "a", "DE", "", "Bybit")
    c = _check(lc, direct_vm, "bybit", BYBIT, [_entry(0, {"a": True})], gleif_status=404)
    assert c["verdict"] == "UNVERIFIED"
    assert c["reasons"] == ["lei_unknown_to_gleif"]


@pytest.mark.parametrize("registration_status,entity_status,expected", [
    ("LAPSED", "ACTIVE", "AUTHORISED"),     # unpaid renewal only - identity unchanged
    ("RETIRED", "ACTIVE", "UNVERIFIED"),    # the LEI itself is no longer valid
    ("ANNULLED", "ACTIVE", "UNVERIFIED"),
    ("ISSUED", "INACTIVE", "UNVERIFIED"),   # the legal entity has ceased
])
def test_lei_registration_and_entity_status_each_checked(direct_vm, direct_deploy, direct_owner,
                                                         registration_status, entity_status, expected):
    lc = _deploy(direct_vm, direct_deploy, direct_owner)
    lc.register_inquiry("bybit", BYBIT, "a", "DE", "", "Bybit")
    doc = json.loads(_fixture(f"gleif_{BYBIT}.json"))
    doc["data"]["attributes"]["registration"]["status"] = registration_status
    doc["data"]["attributes"]["entity"]["status"] = entity_status
    c = _check(lc, direct_vm, "bybit", BYBIT, [_entry(0, {"a": True})], gleif=json.dumps(doc))
    assert c["verdict"] == expected


def test_gleif_record_for_a_different_lei_is_rejected(direct_vm, direct_deploy, direct_owner):
    lc = _deploy(direct_vm, direct_deploy, direct_owner)
    lc.register_inquiry("bybit", BYBIT, "a", "DE", "", "Bybit")
    c = _check(lc, direct_vm, "bybit", BYBIT, [_entry(0, {"a": True})], gleif=_fixture(f"gleif_{ETORO}.json"))
    assert c["verdict"] == "UNVERIFIED"
    assert c["reasons"] == ["gleif_record_mismatch"]


def test_more_matching_rows_than_the_contract_reads_is_unverified(direct_vm, direct_deploy, direct_owner):
    # No LEI has more than two rows today; if one ever had more than the
    # contract reads (10), the unread rows could change the answer.
    lc = _deploy(direct_vm, direct_deploy, direct_owner)
    lc.register_inquiry("bybit", BYBIT, "a", "DE", "", "Bybit")
    casps = _fixture("CASPS.csv")
    [row] = [line for line in casps.split("\r\n") if BYBIT in line]
    casps = casps.rstrip("\r\n") + "\r\n" + "\r\n".join([row] * 10) + "\r\n"
    c = _check(lc, direct_vm, "bybit", BYBIT, [_entry(i, {"a": True}) for i in range(10)], casps=casps)
    assert c["facts"]["entries_matched"] == 11
    assert len(c["facts"]["entries"]) == 10
    assert c["verdict"] == "UNVERIFIED"
    assert c["reasons"] == ["register_entries_truncated:11"]


def test_not_authorised_outranks_unverified(direct_vm, direct_deploy, direct_owner):
    # Bitpanda's listed LEI is retired (UNVERIFIED on its own) - but the
    # register positively shows no trading platform (b) either, and the
    # more definite finding wins.
    lc = _deploy(direct_vm, direct_deploy, direct_owner)
    lc.register_inquiry("bp-b", BITPANDA_LISTED, "b", "AT", "", "Bitpanda trading platform")
    c = _check(lc, direct_vm, "bp-b", BITPANDA_LISTED, [_entry(0, {"b": False})])
    assert c["verdict"] == "NOT_AUTHORISED"
    assert c["reasons"][0] == "service_not_covered:b"
    assert c["reasons"][1].startswith("lei_not_current:RETIRED")


# --- 3. The two-reader rule and the LLM's limits ---------------------------


def test_llm_alone_can_never_grant_a_service(direct_vm, direct_deploy, direct_owner):
    # The LLM claims Bybit offers a trading platform (b). The deterministic
    # reader finds no such service in the entry. Disagreement is UNVERIFIED
    # - never AUTHORISED on the LLM's word.
    lc = _deploy(direct_vm, direct_deploy, direct_owner)
    lc.register_inquiry("bybit-b", BYBIT, "b", "DE", "", "Bybit trading platform")
    c = _check(lc, direct_vm, "bybit-b", BYBIT, [_entry(0, {"b": True})])
    assert c["verdict"] == "UNVERIFIED"
    assert c["reasons"] == ["service_ambiguous:b"]
    assert lc.is_authorised("bybit-b", 10**6) is False


def test_llm_can_veto_what_the_phrase_matcher_found(direct_vm, direct_deploy, direct_owner):
    lc = _deploy(direct_vm, direct_deploy, direct_owner)
    lc.register_inquiry("bybit", BYBIT, "a", "DE", "", "Bybit")
    c = _check(lc, direct_vm, "bybit", BYBIT, [_entry(0, {"a": False})])
    assert c["verdict"] == "UNVERIFIED"
    assert c["reasons"] == ["service_ambiguous:a"]


def test_malformed_llm_answer_can_only_withhold(direct_vm, direct_deploy, direct_owner):
    lc = _deploy(direct_vm, direct_deploy, direct_owner)
    lc.register_inquiry("bybit", BYBIT, "a", "DE", "", "Bybit")
    direct_vm.clear_mocks()
    _serve(direct_vm, BYBIT)
    direct_vm.mock_llm(LLM_PATTERN, json.dumps({"entries": [{"entry": 0, "services": {"a": "yes"}}]}))
    lc.attest("bybit")
    c = lc.latest_check("bybit")
    assert c["llm"][0]["services"] == {"a": False}
    assert c["verdict"] == "UNVERIFIED"


def test_shifted_letters_need_letter_and_description_to_agree(direct_vm, direct_deploy, direct_owner):
    # Bankhaus Scheich's entry reads "c. exchange ... for other crypto-assets",
    # "e. placing", "h. providing portfolio management": descriptions sit
    # under the wrong letters. Portfolio management (i) is described but no
    # "i." appears anywhere - ambiguous, whatever the LLM says.
    lc = _deploy(direct_vm, direct_deploy, direct_owner)
    lc.register_inquiry("scheich-i", SCHEICH, "i", "DE", "", "Bankhaus Scheich")
    c = _check(lc, direct_vm, "scheich-i", SCHEICH, [_entry(0, {"i": True})])
    assert c["facts"]["entries"][0]["det"] == {"i": "AMBIGUOUS"}
    assert c["verdict"] == "UNVERIFIED"
    assert c["reasons"] == ["service_ambiguous:i"]


def test_description_only_entry_is_read_by_its_wording(direct_vm, direct_deploy, direct_owner):
    # Ronin EM's entry has no letters at all, only prose - including
    # "Exchange between crypto assets and fiat currency" (c) and
    # "Exchange between crypto assets" (d), which a careless pattern confuses.
    lc = _deploy(direct_vm, direct_deploy, direct_owner)
    lc.register_inquiry("ronin", "213800V83W83UL8WR118", "c,d,b", "CY", "", "Ronin EM")
    c = _check(lc, direct_vm, "ronin", "213800V83W83UL8WR118",
               [_entry(0, {"b": False, "c": True, "d": True})])
    assert c["facts"]["entries"][0]["det"] == {"b": "NO", "c": "YES", "d": "YES"}
    assert c["coverage"] == {"b": "NO", "c": "YES", "d": "YES"}
    assert c["verdict"] == "NOT_AUTHORISED"


def test_crypto_for_fiat_alone_is_not_crypto_for_crypto(direct_vm, direct_deploy, direct_owner):
    # Ronin's entry with its "Exchange between crypto assets/" clause removed
    # leaves only "Exchange between crypto assets and fiat currency" - that
    # is c, never d. (An earlier pattern let the optional "s" backtrack
    # past its own lookahead and read it as d as well.)
    lc = _deploy(direct_vm, direct_deploy, direct_owner)
    lc.register_inquiry("ronin", "213800V83W83UL8WR118", "c,d", "CY", "", "Ronin EM")
    casps = _edit_row(_fixture("CASPS.csv"), "213800V83W83UL8WR118", "Exchange between crypto assets/ ", "")
    c = _check(lc, direct_vm, "ronin", "213800V83W83UL8WR118", [_entry(0, {"c": True, "d": False})], casps=casps)
    assert c["facts"]["entries"][0]["det"] == {"c": "YES", "d": "NO"}
    assert c["verdict"] == "NOT_AUTHORISED"
    assert c["reasons"] == ["service_not_covered:d"]


def test_regulator_comment_that_limits_scope_is_authorised_restricted(direct_vm, direct_deploy, direct_owner):
    lc = _deploy(direct_vm, direct_deploy, direct_owner)
    lc.register_inquiry("hpb", HPB, "a", "HR", "", "HPB")
    quote = "limited solely to a Passive Digital Assets (PDA) AIF"
    c = _check(lc, direct_vm, "hpb", HPB, [_entry(0, {"a": True}, restricts=True, evidence=quote)])
    assert c["verdict"] == "AUTHORISED_RESTRICTED"
    assert c["restriction_evidence"] == quote
    assert lc.is_authorised("hpb", 10**6) is False  # a contract can't judge a scope limit


def test_own_token_only_authorisation_is_restricted(direct_vm, direct_deploy, direct_owner):
    lc = _deploy(direct_vm, direct_deploy, direct_owner)
    lc.register_inquiry("blue", BLUE_EMI, "a", "LT", "", "BLUE EMI")
    quote = "in relation to own issued EMT called BLUEUR"
    c = _check(lc, direct_vm, "blue", BLUE_EMI, [_entry(0, {"a": True}, restricts=True, evidence=quote)])
    assert c["verdict"] == "AUTHORISED_RESTRICTED"


def test_administrative_comment_is_not_a_restriction(direct_vm, direct_deploy, direct_owner):
    lc = _deploy(direct_vm, direct_deploy, direct_owner)
    lc.register_inquiry("nc", NORTHCRYPTO, "a", "FI", "", "NorthCrypto")
    c = _check(lc, direct_vm, "nc", NORTHCRYPTO, [_entry(0, {"a": True})])
    assert c["facts"]["entries"][0]["comment"] == "Passporting information updated"
    assert c["verdict"] == "AUTHORISED"


def test_restriction_without_a_verbatim_quote_is_unverified(direct_vm, direct_deploy, direct_owner):
    # The reader flags a limit but can't quote it: not published as a
    # restriction, and not AUTHORISED either.
    lc = _deploy(direct_vm, direct_deploy, direct_owner)
    lc.register_inquiry("hpb", HPB, "a", "HR", "", "HPB")
    c = _check(lc, direct_vm, "hpb", HPB,
               [_entry(0, {"a": True}, restricts=True, evidence="only for institutional clients in Croatia")])
    assert c["verdict"] == "UNVERIFIED"
    assert c["reasons"] == [f"restriction_unquoted:row_{c['facts']['entries'][0]['row']}"]
    assert c["restriction_evidence"] == ""


def test_is_authorised_requires_freshness_and_latest_check_wins(direct_vm, direct_deploy, direct_owner):
    lc = _deploy(direct_vm, direct_deploy, direct_owner)
    lc.register_inquiry("bybit", BYBIT, "a", "DE", "", "Bybit")
    _check(lc, direct_vm, "bybit", BYBIT, [_entry(0, {"a": True})])
    _warp(direct_vm, "2026-09-30T12:59:59Z")
    assert lc.is_authorised("bybit", 3600) is True
    _warp(direct_vm, "2026-09-30T13:00:01Z")
    assert lc.is_authorised("bybit", 3600) is False
    assert lc.is_authorised("bybit", 7200) is True
    _check(lc, direct_vm, "bybit", BYBIT, gleif_status=404, llm_entries=[_entry(0, {"a": True})])
    assert lc.latest_verdict("bybit") == "UNVERIFIED"
    assert lc.is_authorised("bybit", 7200) is False
    assert [c["verdict"] for c in lc.get_checks(0, 10)] == ["UNVERIFIED", "AUTHORISED"]
    assert lc.get_inquiry("bybit")["check_count"] == 2


# --- 4. Consensus boundary -------------------------------------------------------


def _payload(check: dict, **overrides) -> str:
    body = {"facts": check["facts"], "llm": check["llm"]}
    body.update(overrides)
    return json.dumps(body, sort_keys=True)


def test_validator_accepts_an_honest_leader(direct_vm, direct_deploy, direct_owner):
    lc = _deploy(direct_vm, direct_deploy, direct_owner)
    lc.register_inquiry("hpb", HPB, "a", "HR", "", "HPB")
    quote = "limited solely to a Passive Digital Assets (PDA) AIF"
    c = _check(lc, direct_vm, "hpb", HPB, [_entry(0, {"a": True}, restricts=True, evidence=quote)])
    assert direct_vm.run_validator() is True
    assert direct_vm.run_validator(leader_result=_payload(c)) is True


def test_validator_rejects_tampered_register_facts(direct_vm, direct_deploy, direct_owner):
    lc = _deploy(direct_vm, direct_deploy, direct_owner)
    lc.register_inquiry("bybit-b", BYBIT, "b", "DE", "", "Bybit")
    c = _check(lc, direct_vm, "bybit-b", BYBIT, [_entry(0, {"b": False})])
    facts = json.loads(json.dumps(c["facts"]))
    facts["entries"][0]["det"]["b"] = "YES"
    forged_llm = [dict(c["llm"][0], services={"b": True})]
    assert direct_vm.run_validator(leader_result=_payload(c, facts=facts, llm=forged_llm)) is False


def test_validator_rejects_tampered_facts_even_with_an_honest_llm_reading(direct_vm, direct_deploy, direct_owner):
    # The leader's LLM output is exactly what mine produces - but its facts
    # hide that GLEIF retired this LEI.
    lc = _deploy(direct_vm, direct_deploy, direct_owner)
    lc.register_inquiry("bp-old", BITPANDA_LISTED, "a", "AT", "", "Bitpanda")
    c = _check(lc, direct_vm, "bp-old", BITPANDA_LISTED, [_entry(0, {"a": True})])
    facts = json.loads(json.dumps(c["facts"]))
    facts["gleif"].update(registration_status="ISSUED", entity_status="ACTIVE", successor_lei="")
    assert direct_vm.run_validator(leader_result=_payload(c, facts=facts)) is False


def test_validator_rejects_invented_unquoted_restriction(direct_vm, direct_deploy, direct_owner):
    # A leader flagging a restriction my reader doesn't see, with no quote,
    # would silently turn AUTHORISED into UNVERIFIED.
    lc = _deploy(direct_vm, direct_deploy, direct_owner)
    lc.register_inquiry("nc", NORTHCRYPTO, "a", "FI", "", "NorthCrypto")
    c = _check(lc, direct_vm, "nc", NORTHCRYPTO, [_entry(0, {"a": True})])
    invented = [dict(c["llm"][0], restricts=True, evidence=None)]
    assert direct_vm.run_validator(leader_result=_payload(c, llm=invented)) is False


def test_validator_rejects_leader_llm_granting_what_mine_does_not(direct_vm, direct_deploy, direct_owner):
    lc = _deploy(direct_vm, direct_deploy, direct_owner)
    lc.register_inquiry("bybit-b", BYBIT, "b", "DE", "", "Bybit")
    c = _check(lc, direct_vm, "bybit-b", BYBIT, [_entry(0, {"b": False})])  # my reader: b absent
    assert direct_vm.run_validator(leader_result=_payload(c, llm=[dict(c["llm"][0], services={"b": True})])) is False


def test_validator_rejects_leader_hiding_a_restriction(direct_vm, direct_deploy, direct_owner):
    lc = _deploy(direct_vm, direct_deploy, direct_owner)
    lc.register_inquiry("hpb", HPB, "a", "HR", "", "HPB")
    quote = "limited solely to a Passive Digital Assets (PDA) AIF"
    c = _check(lc, direct_vm, "hpb", HPB, [_entry(0, {"a": True}, restricts=True, evidence=quote)])
    hidden = [dict(c["llm"][0], restricts=False, evidence=None)]
    assert direct_vm.run_validator(leader_result=_payload(c, llm=hidden)) is False


def test_validator_rejects_restriction_quote_not_in_the_comment(direct_vm, direct_deploy, direct_owner):
    lc = _deploy(direct_vm, direct_deploy, direct_owner)
    lc.register_inquiry("hpb", HPB, "a", "HR", "", "HPB")
    quote = "limited solely to a Passive Digital Assets (PDA) AIF"
    c = _check(lc, direct_vm, "hpb", HPB, [_entry(0, {"a": True}, restricts=True, evidence=quote)])
    fabricated = [dict(c["llm"][0], evidence="authorisation suspended pending investigation")]
    assert direct_vm.run_validator(leader_result=_payload(c, llm=fabricated)) is False


def test_validator_rejects_llm_output_where_none_was_needed(direct_vm, direct_deploy, direct_owner):
    lc = _deploy(direct_vm, direct_deploy, direct_owner)
    lc.register_inquiry("decubate", DECUBATE, "f", "NL", "", "Decubate")
    c = _check(lc, direct_vm, "decubate", DECUBATE)
    invented = [{"row": c["facts"]["entries"][0]["row"], "services": {"f": True}, "restricts": False, "evidence": None}]
    assert direct_vm.run_validator(leader_result=_payload(c, llm=invented)) is False


def test_validator_rejects_misaligned_or_garbage_results(direct_vm, direct_deploy, direct_owner):
    lc = _deploy(direct_vm, direct_deploy, direct_owner)
    lc.register_inquiry("bybit", BYBIT, "a", "DE", "", "Bybit")
    c = _check(lc, direct_vm, "bybit", BYBIT, [_entry(0, {"a": True})])
    assert direct_vm.run_validator(leader_result=_payload(c, llm=[])) is False
    assert direct_vm.run_validator(leader_result=_payload(c, llm=[dict(c["llm"][0], row=1)])) is False
    assert direct_vm.run_validator(leader_error=Exception("fetch failed")) is False
    assert direct_vm.run_validator(leader_result="not json") is False
    assert direct_vm.run_validator(leader_result=json.dumps({"facts": c["facts"]})) is False
