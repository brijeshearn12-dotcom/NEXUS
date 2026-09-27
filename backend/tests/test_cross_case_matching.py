"""Integration tests for cross-case candidate matching (isolated test database).

Documents and entities are seeded the way the per-case pipeline stores them, so the
matcher is exercised against realistic records without running spaCy.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.services.cross_case.matcher import (
    CROSS_CASE_COLLECTION,
    list_cross_case_links,
    review_cross_case_link,
    run_cross_case_matching,
)
from app.services.extraction.deduplication import generate_stable_entity_id
from tests.cross_case_support import isolated_db  # noqa: F401  (pytest fixture)

client = TestClient(app)

FILLER = (
    " The trial court record was summoned and the parties were heard at length on the question of"
    " bail, delay in trial and the period of custody already undergone by the applicant."
)

TEXT_A = (
    "The prosecution case is that Case Crime No. 45/2022 was registered at Police Station Kotwali,"
    " District Lucknow. The accused Ramesh Yadav and Suresh Pal Singh were seen near the grain market"
    " in a car bearing number UP 32 AB 1234 on the evening of the incident." + FILLER * 3
)
TEXT_B = (
    "The applicant Ramesh Yadav seeks regular bail. According to the first information report in"
    " Case Crime No. 45/2022, Police Station Kotwali, District Lucknow, the co-accused Suresh Pal Singh"
    " drove the car UP 32 AB 1234 away from the spot." + FILLER * 2 + " Separate reasons follow."
)
TEXT_C_OTHER_STATION = (
    "The applicant Ramesh Yadav seeks anticipatory bail in Case Crime No. 45/2022, Police Station"
    " Civil Lines, District Kanpur, relating to a dispute over agricultural land." + FILLER
)
TEXT_D_PRECEDENT = (
    "Learned counsel placed reliance on Ramesh Yadav v. State of U.P. (2019) 5 SCC 100 to submit"
    " that bail is the rule. This case arises from Case Crime No. 45/2022, Police Station Kotwali,"
    " District Lucknow, in which the applicant Mahesh Chand Gupta is named." + FILLER
)
TEXT_F_SINGLE = (
    "The applicant Ashraf and the co-accused Mohan Lal Gupta were arrested at the bus stand."
    + FILLER * 2
)
TEXT_G_SINGLE = (
    "Ashraf, the brother of the principal accused, and Mohan Lal Gupta are named in the charge sheet."
    + FILLER + " The matter concerns an unrelated incident."
)
TEXT_H_SINGLE_VEHICLE = (
    "The accused Ashraf was intercepted while driving vehicle HR 26 CX 7788 near the toll plaza."
    + FILLER
)
TEXT_I_SINGLE_VEHICLE = (
    "Recovery memo records that Ashraf handed over the keys of vehicle HR 26 CX 7788 to the police."
    + FILLER + " No other recovery was made."
)
TEXT_J_JUDGE = (
    "HON'BLE MR. JUSTICE Arvind Kumar Mishra heard the application arising from Case Crime No."
    " 77/2021, Police Station Hazratganj, District Lucknow." + FILLER
)
TEXT_K_JUDGE = (
    "Before HON'BLE MR. JUSTICE Arvind Kumar Mishra. The appeal arises out of Case Crime No. 77/2021,"
    " Police Station Hazratganj, District Lucknow." + FILLER + " Appeal allowed in part."
)


def seed_judgment(db, tid: str, text: str, people: list[tuple[str, bool]]) -> str:
    doc_id, case_id = f"doc_{tid}", f"case_{tid}"
    db.documents.insert_one(
        {
            "id": doc_id,
            "case_id": case_id,
            "title": f"Synthetic judgment {tid}",
            "text": text,
            "source_url": f"https://example.test/judgments/{tid}",
            "court": "Synthetic High Court",
            "date": "2026-01-01",
        }
    )
    db.cases.insert_one({"id": case_id, "case_id": case_id, "title": f"Synthetic judgment {tid}"})
    for name, is_accused in people:
        start = text.find(name)
        db.entities.insert_one(
            {
                "id": generate_stable_entity_id(case_id, "PERSON", name),
                "case_id": case_id,
                "document_id": doc_id,
                "name": name,
                "entity_type": "PERSON",
                "aliases": [],
                "provenance": {
                    "tier": "primary",
                    "source_ref": doc_id,
                    "method": "spacy_ner",
                    "confidence": 0.85,
                    "metadata": {"start_char": start, "end_char": start + len(name)},
                },
                "verification_status": "unverified",
                "evidence_snippet": text[max(0, start - 50) : start + len(name) + 50],
                "metadata": {"is_accused": is_accused},
            }
        )
    return case_id


def seed_core_corpus(db) -> None:
    seed_judgment(db, "101", TEXT_A, [("Ramesh Yadav", True), ("Suresh Pal Singh", True)])
    seed_judgment(db, "202", TEXT_B, [("Ramesh Yadav", True), ("Suresh Pal Singh", False)])


def pair_cases(link: dict) -> set[str]:
    return {link["side_a"]["case_id"], link["side_b"]["case_id"]}


# ── matcher ──────────────────────────────────────────────────────────────────


def test_corroborated_match_is_proposed_with_evidence_from_both_judgments(isolated_db):
    seed_core_corpus(isolated_db)
    summary = run_cross_case_matching(database=isolated_db)
    links = list_cross_case_links(database=isolated_db)

    assert summary["proposals_created"] == 2
    ramesh = next(l for l in links if l["side_a"]["entity_name"] == "Ramesh Yadav")
    assert pair_cases(ramesh) == {"case_101", "case_202"}
    assert ramesh["status"] == "proposed"
    assert ramesh["match_strength"] == "strong"
    kinds = {c["kind"]: c["value"] for c in ramesh["corroboration"]}
    assert kinds["fir_police_station"] == "45/2022@kotwali"
    assert kinds["vehicle"] == "UP32AB1234"
    assert kinds["shared_participant"] == "suresh pal singh"
    for side in (ramesh["side_a"], ramesh["side_b"]):
        assert "Ramesh Yadav" in side["evidence_passage"]
        assert side["source_url"].startswith("https://example.test/judgments/")
        assert side["extraction_provenance"]["method"] == "spacy_ner"
    assert ramesh["side_a"]["document_id"] != ramesh["side_b"]["document_id"]
    assert all(c["evidence_a"] and c["evidence_b"] for c in ramesh["corroboration"])
    assert ramesh["reasons"] and "not a probability" in ramesh["score_note"].lower()
    assert "does not establish identity" in ramesh["disclaimer"]


def test_same_fir_number_at_a_different_police_station_is_not_corroboration(isolated_db):
    seed_core_corpus(isolated_db)
    seed_judgment(isolated_db, "303", TEXT_C_OTHER_STATION, [("Ramesh Yadav", False)])
    summary = run_cross_case_matching(database=isolated_db)
    links = list_cross_case_links(database=isolated_db)

    assert not any("case_303" in pair_cases(l) for l in links)
    assert summary["rejected_name_only"] >= 1
    assert any(
        "case_303" in (ex["case_a"], ex["case_b"]) and ex["reason"] == "name_only_no_corroboration"
        for ex in summary["rejected_examples"]
    )


def test_a_title_variant_of_the_same_person_is_not_self_corroboration(isolated_db):
    # "M.P. Dinesh Kumar Rawat" is the matched person again, not a second shared participant.
    text_l = (
        "The applicant Dinesh Kumar Rawat seeks bail. It is alleged that former M.P. Dinesh Kumar"
        " Rawat threatened the witnesses." + FILLER * 2
    )
    text_m = (
        "Dinesh Kumar Rawat has filed this appeal. The State submits that former M.P. Dinesh Kumar"
        " Rawat was absconding." + FILLER + " The appeal concerns a separate incident."
    )
    people = [("Dinesh Kumar Rawat", True), ("M.P. Dinesh Kumar Rawat", False)]
    seed_judgment(isolated_db, "515", text_l, people)
    seed_judgment(isolated_db, "616", text_m, people)
    summary = run_cross_case_matching(database=isolated_db)

    assert list_cross_case_links(database=isolated_db) == []
    assert summary["rejected_name_only"] >= 2


def test_name_that_appears_only_in_a_cited_precedent_is_not_matched(isolated_db):
    seed_core_corpus(isolated_db)
    seed_judgment(isolated_db, "404", TEXT_D_PRECEDENT, [("Ramesh Yadav", False), ("Mahesh Chand Gupta", True)])
    summary = run_cross_case_matching(database=isolated_db)
    links = list_cross_case_links(database=isolated_db)

    assert not any("case_404" in pair_cases(l) for l in links)
    assert summary["excluded_person_entities"]["citation_only"] >= 1


def test_duplicate_copy_of_a_judgment_is_not_separate_evidence(isolated_db):
    seed_core_corpus(isolated_db)
    seed_judgment(isolated_db, "505", TEXT_A + " (indexed under a second title)",
                  [("Ramesh Yadav", True), ("Suresh Pal Singh", True)])
    summary = run_cross_case_matching(database=isolated_db)
    links = list_cross_case_links(database=isolated_db)

    assert [g["members"] for g in summary["duplicate_groups"]] == [["doc_101", "doc_505"]]
    assert summary["entities_skipped_as_duplicate_copies"] == 2
    assert len(links) == 2  # exactly the proposals found without the copy
    assert not any("case_505" in pair_cases(l) for l in links)


def test_similar_but_not_identical_names_are_not_matched(isolated_db):
    seed_judgment(isolated_db, "606", TEXT_A.replace("Ramesh Yadav", "Rakesh Yadav"),
                  [("Rakesh Yadav", True), ("Suresh Pal Singh", True)])
    seed_judgment(isolated_db, "707", TEXT_B, [("Ramesh Yadav", True)])
    run_cross_case_matching(database=isolated_db)
    links = list_cross_case_links(database=isolated_db)
    assert not any({l["side_a"]["entity_name"], l["side_b"]["entity_name"]} == {"Rakesh Yadav", "Ramesh Yadav"}
                   for l in links)


def test_single_word_name_needs_an_identifier(isolated_db):
    seed_judgment(isolated_db, "808", TEXT_F_SINGLE, [("Ashraf", True), ("Mohan Lal Gupta", True)])
    seed_judgment(isolated_db, "809", TEXT_G_SINGLE, [("Ashraf", True), ("Mohan Lal Gupta", False)])
    summary = run_cross_case_matching(database=isolated_db)
    assert summary["rejected_single_token_without_identifier"] >= 1
    assert not any(l["side_a"]["entity_name"] == "Ashraf" for l in list_cross_case_links(database=isolated_db))

    seed_judgment(isolated_db, "901", TEXT_H_SINGLE_VEHICLE, [("Ashraf", True)])
    seed_judgment(isolated_db, "902", TEXT_I_SINGLE_VEHICLE, [("Ashraf", False)])
    run_cross_case_matching(database=isolated_db)
    ashraf = [l for l in list_cross_case_links(database=isolated_db)
              if pair_cases(l) == {"case_901", "case_902"}]
    assert len(ashraf) == 1
    assert [c["kind"] for c in ashraf[0]["corroboration"]] == ["vehicle"]


def test_judges_are_never_matched_across_cases(isolated_db):
    seed_judgment(isolated_db, "111", TEXT_J_JUDGE, [("Arvind Kumar Mishra", False)])
    seed_judgment(isolated_db, "112", TEXT_K_JUDGE, [("Arvind Kumar Mishra", False)])
    summary = run_cross_case_matching(database=isolated_db)
    assert list_cross_case_links(database=isolated_db) == []
    assert summary["excluded_person_entities"]["legal_role_or_witness_only"] == 2


def test_repeat_runs_are_deterministic_and_never_duplicate_proposals(isolated_db):
    seed_core_corpus(isolated_db)
    first = run_cross_case_matching(database=isolated_db)
    ids_first = [l["link_id"] for l in list_cross_case_links(database=isolated_db)]
    second = run_cross_case_matching(database=isolated_db)
    ids_second = [l["link_id"] for l in list_cross_case_links(database=isolated_db)]

    assert first["proposals_created"] == 2
    assert second["proposals_created"] == 0 and second["proposals_refreshed"] == 2
    assert ids_first == ids_second
    assert isolated_db[CROSS_CASE_COLLECTION].count_documents({}) == 2


def test_analyst_decisions_survive_a_rerun(isolated_db):
    seed_core_corpus(isolated_db)
    run_cross_case_matching(database=isolated_db)
    link = list_cross_case_links(database=isolated_db)[0]
    review_cross_case_link(link["link_id"], "confirmed", notes="Same FIR", analyst_id="analyst-7",
                           database=isolated_db)
    summary = run_cross_case_matching(database=isolated_db)
    stored = isolated_db[CROSS_CASE_COLLECTION].find_one({"link_id": link["link_id"]})
    assert stored["status"] == "confirmed"
    assert stored["analyst_notes"] == "Same FIR"
    assert summary["reviewed_proposals_kept_unchanged"] == 1


# ── API ──────────────────────────────────────────────────────────────────────


def test_api_is_disabled_by_default(isolated_db, monkeypatch):
    monkeypatch.setattr(settings, "enable_cross_case", False)
    assert client.get("/api/cross-case/status").json()["enabled"] is False
    assert client.post("/api/cross-case/run").status_code == 404
    assert client.get("/api/cross-case/links").status_code == 404
    assert client.patch("/api/cross-case/links/x/verify", json={"status": "confirmed"}).status_code == 404


def test_api_run_retrieve_confirm_reject_and_audit(isolated_db, monkeypatch):
    monkeypatch.setattr(settings, "enable_cross_case", True)
    seed_core_corpus(isolated_db)

    run = client.post("/api/cross-case/run")
    assert run.status_code == 200 and run.json()["proposals_created"] == 2

    listed = client.get("/api/cross-case/links").json()
    assert listed["total"] == 2
    by_case = client.get("/api/cross-case/cases/case_202").json()
    assert by_case["total"] == 2
    link_id = listed["items"][0]["link_id"]
    assert client.get(f"/api/cross-case/links/{link_id}").json()["link_id"] == link_id

    confirmed = client.patch(f"/api/cross-case/links/{link_id}/verify",
                             json={"status": "confirmed", "analyst_id": "analyst-7", "notes": "Same FIR and car"})
    assert confirmed.status_code == 200
    body = confirmed.json()
    assert body["status"] == "confirmed" and body["reviewed_by"] == "analyst-7"
    assert body["review_history"][-1]["previous_status"] == "proposed"

    for case_id in ("case_101", "case_202"):
        trail = client.get(f"/api/cases/{case_id}/audit", params={"limit": 500}).json()["items"]
        actions = [e["action"] for e in trail if e.get("entity_id") == link_id]
        assert "cross_case_match_proposed" in actions
        assert "cross_case_match_confirmed" in actions

    rejected = client.patch(f"/api/cross-case/links/{link_id}/verify",
                            json={"verification_status": "rejected", "analyst_id": "analyst-9"})
    assert rejected.json()["status"] == "rejected"
    assert len(rejected.json()["review_history"]) == 2
    assert isolated_db.audit_log.count_documents({"entity_id": link_id, "action": "cross_case_match_rejected"}) == 2

    assert client.patch(f"/api/cross-case/links/{link_id}/verify", json={"status": "merged"}).status_code == 400
    assert client.patch(f"/api/cross-case/links/{link_id}/verify", json={}).status_code == 422
    assert client.patch("/api/cross-case/links/ccl_missing/verify", json={"status": "confirmed"}).status_code == 404
    assert client.get("/api/cross-case/links/ccl_missing").status_code == 404


@pytest.mark.parametrize("status_value", ["confirmed", "rejected"])
def test_status_filter(isolated_db, monkeypatch, status_value):
    monkeypatch.setattr(settings, "enable_cross_case", True)
    seed_core_corpus(isolated_db)
    client.post("/api/cross-case/run")
    link_id = client.get("/api/cross-case/links").json()["items"][0]["link_id"]
    client.patch(f"/api/cross-case/links/{link_id}/verify", json={"status": status_value})
    filtered = client.get("/api/cross-case/links", params={"status": status_value}).json()
    assert [i["link_id"] for i in filtered["items"]] == [link_id]
