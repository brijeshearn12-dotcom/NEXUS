"""Real-data fixtures: cross-case matching on curated Indian Kanoon judgments.

Runs the EXISTING corpus loader, extraction (spaCy; Gemini disabled), per-case alias
resolution and graph build on a subset of real judgments in an isolated database, then
checks what the matcher discovers. Nothing about the expected pair is given to the matcher.
Skipped when the spaCy English model is not installed.
"""

from __future__ import annotations

import pytest

spacy = pytest.importorskip("spacy")
try:
    spacy.load("en_core_web_sm")
except OSError:  # pragma: no cover - environment dependent
    pytest.skip("spaCy model en_core_web_sm is not installed", allow_module_level=True)

from app.core import db as core_db  # noqa: E402
from app.services.corpus_service import load_curated_corpus  # noqa: E402
from app.services.cross_case.matcher import list_cross_case_links, run_cross_case_matching  # noqa: E402
from app.services.cross_case.safeguards import classify_mentions  # noqa: E402
from app.services.extraction.service import extract_and_store_document  # noqa: E402
from app.services.graph.builder import build_graph_for_case  # noqa: E402
from app.services.resolution.alias_resolver import (  # noqa: E402
    normalize_alias_name,
    resolve_case_aliases,
)
from tests.cross_case_support import (  # noqa: E402
    close_isolated_client,
    diff_snapshots,
    open_isolated_client,
    snapshot_per_case_state,
)

ALLAHABAD_AKHLAKH = "case_141720225"  # Akhlakh Ahmad @ Ekhlakh Ahmad v. State of U.P.
ALLAHABAD_KAISH = "case_31981506"  # Kaish Ahmad v. State of U.P.
AP_PELLAKURU = "case_165285253"  # State of A.P. v. Pellakuru Krishna Mohan Reddy
AP_CHEVIREDDY = "case_148603334"
SAJJAN_COPY_A = "doc_112621805"  # Krishan Khokar v. CBI  } one Delhi HC judgment
SAJJAN_COPY_B = "doc_4190613"  # State through CBI v. Sajjan Kumar  } indexed twice
SANJAY_SINGH = "case_105576387"
JAGDISH_ARORA = "case_76881707"

REAL_DOCUMENTS = [
    "doc_141720225", "doc_31981506", "doc_165285253", "doc_148603334",
    SAJJAN_COPY_A, SAJJAN_COPY_B, "doc_105576387", "doc_76881707",
]


@pytest.fixture(scope="module")
def real_run():
    client, real = open_isolated_client()
    previous_client = core_db._client
    core_db._client = client
    db = client.test_database
    try:
        load_curated_corpus()
        for doc_id in REAL_DOCUMENTS:
            extract_and_store_document(doc_id, enable_gemini_fallback=False)
        case_ids = sorted({db.documents.find_one({"id": d})["case_id"] for d in REAL_DOCUMENTS})
        for case_id in case_ids:
            resolve_case_aliases(case_id=case_id, database=db)
            build_graph_for_case(case_id=case_id, database=db)
        before = snapshot_per_case_state(db, case_ids)
        summary = run_cross_case_matching(database=db)
        links = list_cross_case_links(database=db)
        after = snapshot_per_case_state(db, case_ids)
        yield {"db": db, "summary": summary, "links": links, "before": before, "after": after}
    finally:
        core_db._client = previous_client
        close_isolated_client(client, real)


def _cases(link):
    return {link["side_a"]["case_id"], link["side_b"]["case_id"]}


def _names(link):
    return {
        str(side.get(key, "")).lower()
        for side in (link["side_a"], link["side_b"])
        for key in ("entity_name", "matched_name_form")
    }


def test_allahabad_pair_is_discovered_from_the_data(real_run):
    pair = [l for l in real_run["links"] if _cases(l) == {ALLAHABAD_AKHLAKH, ALLAHABAD_KAISH}]
    assert pair, "the matcher should propose at least one link between the two Allahabad orders"
    values = {(c["kind"], c["value"]) for link in pair for c in link["corroboration"]}
    assert ("fir_police_station", "114/2023@dhoomanganj") in values
    assert ("vehicle", "UP70FB5433") in values


def test_allahabad_proposals_carry_evidence_from_both_judgments(real_run):
    pair = [l for l in real_run["links"] if _cases(l) == {ALLAHABAD_AKHLAKH, ALLAHABAD_KAISH}]
    for link in pair:
        a, b = link["side_a"], link["side_b"]
        assert {a["document_id"], b["document_id"]} == {"doc_141720225", "doc_31981506"}
        for side in (a, b):
            assert side["matched_name_form"].lower() in side["evidence_passage"].lower()
            assert side["source_url"].startswith("https://indiankanoon.org/doc/")
        assert link["status"] == "proposed"


def test_cited_precedent_name_is_not_proposed(real_run):
    db = real_run["db"]
    # The trap is real: the name belongs to a party in the AP case ...
    assert db.entities.find_one({"case_id": AP_PELLAKURU, "name": {"$regex": "Krishna Mohan Reddy"}})
    # ... and appears in the Allahabad orders only inside citations.
    for doc_id in ("doc_31981506", "doc_141720225"):
        doc = db.documents.find_one({"id": doc_id})
        mentions = classify_mentions(doc["text"], "Krishna Mohan Reddy", own_title=doc["title"])
        assert mentions["citation"] and not mentions["participant"]
    assert not [l for l in real_run["links"] if any("krishna mohan reddy" in n for n in _names(l))]


def test_duplicate_copies_are_not_separate_evidence(real_run):
    groups = real_run["summary"]["duplicate_groups"]
    sajjan = next(g for g in groups if SAJJAN_COPY_A in g["members"])
    assert SAJJAN_COPY_B in sajjan["members"] and sajjan["representative"] == SAJJAN_COPY_A
    for link in real_run["links"]:
        docs = {link["side_a"]["document_id"], link["side_b"]["document_id"]}
        assert SAJJAN_COPY_B not in docs
        assert docs != {SAJJAN_COPY_A, SAJJAN_COPY_B}


def test_unrelated_judgments_that_cite_the_same_precedents_are_not_linked(real_run):
    for pair in ({SANJAY_SINGH, JAGDISH_ARORA}, {AP_PELLAKURU, ALLAHABAD_KAISH},
                 {AP_PELLAKURU, ALLAHABAD_AKHLAKH}, {AP_CHEVIREDDY, ALLAHABAD_KAISH}):
        assert not [l for l in real_run["links"] if _cases(l) == pair], pair


def test_judge_and_counsel_of_the_allahabad_orders_are_not_proposed(real_run):
    # The same judge and the same State counsel appear in both orders (coram line, appearance
    # roster, signature). Sharing a bench or a prosecutor is not a cross-case link.
    court_personnel = {"shekhar kumar yadav", "manish goyal", "manish goel", "rupak chaubey",
                       "thakur azad singh", "praveen kumar pandey"}
    for link in real_run["links"]:
        assert not (_names(link) & court_personnel), (link["link_id"], _names(link))


def test_proposed_names_are_proper_name_mentions(real_run):
    # Ordinary words mislabelled as PERSON ("barbaric") and fragments of longer names ("Yadav"
    # inside "Abhishek Yadav") must not produce proposals.
    for link in real_run["links"]:
        assert not (_names(link) & {"barbaric", "yadav"}), link["link_id"]
        for side in (link["side_a"], link["side_b"]):
            assert side["matched_name_form"] in side["evidence_passage"], side["matched_name_form"]


def test_every_real_proposal_is_corroborated_beyond_the_name(real_run):
    for link in real_run["links"]:
        assert link["corroboration"], link["link_id"]
        single_word = min(len(normalize_alias_name(link["side_a"]["matched_name_form"]).split()),
                          len(normalize_alias_name(link["side_b"]["matched_name_form"]).split())) < 2
        if single_word:
            assert any(c["kind"] != "shared_participant" for c in link["corroboration"])


def test_per_case_analysis_is_unchanged_on_real_data(real_run):
    assert diff_snapshots(real_run["before"], real_run["after"]) == []
