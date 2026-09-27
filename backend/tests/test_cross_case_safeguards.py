"""Unit tests for the cross-case safeguards (pure functions, no database)."""

from __future__ import annotations

from app.services.cross_case.safeguards import (
    classify_mentions,
    extract_fir_station_keys,
    extract_phone_keys,
    extract_vehicle_keys,
    group_near_duplicate_documents,
    is_matchable_person_name,
    normalize_police_station,
    strict_name_match,
)

# Short passages quoted from the real Allahabad High Court orders in data/curated.
PRECEDENT_PASSAGE = (
    "as held by the Supreme Court in Surinder Kumar Khanna v. Directorate of Revenue "
    "Intelligence (2018) 8 SCC 271 and reaffirmed in P. Krishna Mohan Reddy v. State of "
    "Andhra Pradesh (2025) SCC Online SC 1157. In P. Krishna Mohan Reddy (supra), the court held"
)
PARTICIPANT_PASSAGE = (
    "It is alleged that as they got out of the car near their home, the son of former MP "
    "Atiq Ahmad, along with Guddu Muslim, Ghulam, and nine other associates, launched deadly attack"
)


def _long_text(seed: str, words: int = 300) -> str:
    return " ".join(f"{seed}{i} term{i % 11} clause{i % 17}" for i in range(words))


# ── duplicate-document guard ─────────────────────────────────────────────────


def test_near_duplicate_guard_groups_copies_of_one_judgment():
    base = _long_text("fact")
    docs = [
        {"id": "doc_b", "text": base + " indexed under a second title"},
        {"id": "doc_a", "text": base},
        {"id": "doc_c", "text": _long_text("other")},
    ]
    result = group_near_duplicate_documents(docs)
    assert result["representative_of"] == {"doc_a": "doc_a", "doc_b": "doc_a", "doc_c": "doc_c"}
    assert [g["members"] for g in result["duplicate_groups"]] == [["doc_a", "doc_b"]]
    assert result["duplicate_groups"][0]["min_similarity"] >= 0.8


def test_distinct_judgments_sharing_a_fact_narrative_are_not_duplicates():
    shared = _long_text("shared", 120)
    docs = [
        {"id": "doc_x", "text": shared + " " + _long_text("xonly", 200)},
        {"id": "doc_y", "text": shared + " " + _long_text("yonly", 200)},
    ]
    result = group_near_duplicate_documents(docs)
    assert result["duplicate_groups"] == []
    assert result["representative_of"] == {"doc_x": "doc_x", "doc_y": "doc_y"}


def test_duplicate_guard_is_order_independent():
    base = _long_text("same")
    docs = [{"id": f"doc_{n}", "text": base} for n in ("3", "1", "2")]
    first = group_near_duplicate_documents(docs)
    second = group_near_duplicate_documents(list(reversed(docs)))
    assert first == second
    assert set(first["representative_of"].values()) == {"doc_1"}


# ── citation / legal-role / witness context ─────────────────────────────────


def test_cited_precedent_name_is_never_a_participant():
    mentions = classify_mentions(PRECEDENT_PASSAGE, "Krishna Mohan Reddy")
    assert mentions["participant"] == []
    assert len(mentions["citation"]) == 2


def test_bare_references_to_a_cited_precedent_are_not_participants():
    # Later sentences of the real order name the precedent without any citation marker nearby.
    text = PRECEDENT_PASSAGE + (
        " that confessions to a police officer are generally inadmissible. However, this Court"
        " finds that the principles of P. Krishna Mohan Reddy do not singularly govern the"
        " outcome of the present bail application. The case at hand is distinguishable on"
        " several material grounds. First, the core principle of P. Krishna Mohan Reddy is that"
        " a bail application cannot be rejected merely on the basis of a co-accused's statement."
    )
    mentions = classify_mentions(text, "Krishna Mohan Reddy", own_title="Kaish Ahmad vs The State Of U.P.")
    assert mentions["participant"] == []
    assert len(mentions["citation"]) == 4


def test_parties_in_the_judgments_own_title_are_not_treated_as_precedents():
    title = "State Of Andhra Pradesh vs Pellakuru Krishna Mohan Reddy on 19 November, 2025"
    text = (
        title + "\n\nIN THE SUPREME COURT OF INDIA\n\nCRIMINAL APPELLATE JURISDICTION\n\n"
        "1. Leave granted. The State is aggrieved by the order of the High Court under challenge.\n\n"
        "2. The respondent Pellakuru Krishna Mohan Reddy was granted bail by the High Court."
    )
    mentions = classify_mentions(text, "Krishna Mohan Reddy", own_title=title)
    assert len(mentions["participant"]) == 1


def test_fact_narrative_mention_is_a_participant():
    mentions = classify_mentions(PARTICIPANT_PASSAGE, "Atiq Ahmad")
    assert len(mentions["participant"]) == 1
    assert mentions["citation"] == []


def test_judge_and_counsel_mentions_are_excluded():
    text = (
        "HON'BLE MR. JUSTICE Rajiv Mohan Sharma delivered the order. "
        "Learned counsel Mr. Anil Kumar Verma appeared for the applicant."
    )
    assert classify_mentions(text, "Rajiv Mohan Sharma")["participant"] == []
    assert classify_mentions(text, "Anil Kumar Verma")["participant"] == []


# Header, roster and signature lines quoted from the same real Allahabad High Court orders.
CORAM_AND_ROSTER = (
    "Court No. - 86\n\nHON'BLE SHEKHAR KUMAR YADAV, J.\n\n1. Heard Mr Brijesh Sahai, learned Senior "
    "counsel assisted by Mr Bhavya Sahai, learned counsel appearing for the appellant, Mr Manish "
    "Goyal, learned Addl. Advocate General for the State assisted by Mr Rupak Chaubey, learned "
    "AGA-I, Mr Thakur Azad Singh, learned AGA, Mr Praveen Kumar Pandey, learned counsel for the "
    "informant and perused the record."
)
SIGNATURE = "The Criminal appeal lacks merit and is hereby rejected.\n\n(Shekhar Kumar Yadav,J.)\n\nNovember 7, 2025"
ROSTER_WITH_AND = (
    "7. On the contrary, Mr Manish Goel, learned Addl, Advocate General assisted by Mr Rupak "
    "Chaubey and Mr Thakur Azad Singh, learned AGA, appearing on behalf of the prosecution"
)


def test_real_coram_signature_and_counsel_roster_are_legal_roles():
    for text, name in [
        (CORAM_AND_ROSTER, "Shekhar Kumar Yadav"),
        (SIGNATURE, "Shekhar Kumar Yadav"),
        (CORAM_AND_ROSTER, "Brijesh Sahai"),
        (CORAM_AND_ROSTER, "Bhavya Sahai"),
        (CORAM_AND_ROSTER, "Manish Goyal"),
        (CORAM_AND_ROSTER, "Rupak Chaubey"),
        (CORAM_AND_ROSTER, "Thakur Azad Singh"),
        (CORAM_AND_ROSTER, "Praveen Kumar Pandey"),
        (ROSTER_WITH_AND, "Manish Goel"),
        (ROSTER_WITH_AND, "Rupak Chaubey"),
        (ROSTER_WITH_AND, "Thakur Azad Singh"),
    ]:
        mentions = classify_mentions(text, name)
        assert mentions["participant"] == [], name
        assert len(mentions["legal_role"]) == 1, name


def test_counsel_for_party_roster_line_is_a_legal_role():
    text = "Counsel for Applicant :- Rajesh Kumar Dubey,Sanjay Pratap Singh\nCounsel for Opposite Party :- G.A."
    assert classify_mentions(text, "Rajesh Kumar Dubey")["participant"] == []
    assert classify_mentions(text, "Sanjay Pratap Singh")["participant"] == []


def test_lower_case_word_is_not_a_name_mention():
    text = "It is further submitted that it's a heinous and barbaric act of triple murder in broad daylight."
    mentions = classify_mentions(text, "Barbaric")
    assert mentions["participant"] == []
    assert len(mentions["not_a_name"]) == 1


def test_one_word_name_inside_a_longer_name_is_not_a_mention():
    text = (
        "According to the statement of Abhishek Yadav, recorded under Section 164 Cr.P.C.\n"
        "HON'BLE SHEKHAR KUMAR YADAV, J."
    )
    mentions = classify_mentions(text, "Yadav")
    assert mentions["participant"] == []
    assert len(mentions["not_a_name"]) == 2
    assert len(classify_mentions(text, "Abhishek Yadav")["participant"]) == 1


def test_standalone_one_word_names_in_the_fact_narrative_still_count():
    narrative = PARTICIPANT_PASSAGE + ". The murder was conspired by Atiq Ahmad's brother Ashraf, and was carried out"
    assert len(classify_mentions(narrative, "Ghulam")["participant"]) == 1
    assert len(classify_mentions(narrative, "Ashraf")["participant"]) == 1


def test_witness_mentions_are_excluded():
    text = "PW-3 Suresh Chandra Tiwari deposed that he saw the vehicle near the crossing."
    mentions = classify_mentions(text, "Suresh Chandra Tiwari")
    assert mentions["participant"] == []
    assert len(mentions["witness"]) == 1


# ── FIR + police station ─────────────────────────────────────────────────────


def test_fir_key_pairs_number_with_police_station():
    text = (
        "Bail Application No. 4196 of 2023 arising out of Case Crime No. 114/2023, under "
        "Sections 147, 148, 149, 302 IPC, Police Station Dhoomanganj, District Prayagraj."
    )
    keys, unresolved = extract_fir_station_keys(text)
    assert list(keys) == ["114/2023@dhoomanganj"]
    assert unresolved == []
    assert "Dhoomanganj" in keys["114/2023@dhoomanganj"]["passage"]


def test_fir_without_a_police_station_is_not_an_identifier():
    keys, unresolved = extract_fir_station_keys("The FIR No. 114/2023 was lodged under Section 302 IPC.")
    assert keys == {}
    assert [u["fir"] for u in unresolved] == ["114/2023"]


def test_same_fir_number_at_different_police_stations_gives_different_keys():
    a, _ = extract_fir_station_keys("Case Crime No. 114/2023, Police Station Dhoomanganj, District Prayagraj.")
    b, _ = extract_fir_station_keys("Case Crime No. 114/2023, Police Station Kotwali, District Lucknow.")
    assert set(a) == {"114/2023@dhoomanganj"}
    assert set(b) == {"114/2023@kotwali"}
    assert not set(a) & set(b)


def test_fir_of_year_form_and_comma_station():
    keys, _ = extract_fir_station_keys(
        "regular bail in connection with Crime No.21 of 2024 of CID Police Station, Mangalagiri, registered"
    )
    assert list(keys) == ["21/2024@mangalagiri"]


def test_police_station_name_is_trimmed():
    assert normalize_police_station("Dhoomanganj District Prayagraj") == "dhoomanganj"
    assert normalize_police_station("Civil Lines") == "civil lines"


# ── strict name rule ─────────────────────────────────────────────────────────


def test_exact_normalized_name_match_ignores_honorifics_and_case():
    assert strict_name_match("Shri KAISH AHMAD", "Kaish Ahmad") == (True, "exact_normalized_name", 1.0)


def test_clear_initials_match():
    matched, basis, _ = strict_name_match("R. Kumar", "Rajesh Kumar")
    assert matched and basis == "initials_match"


def test_near_miss_spellings_are_not_matched():
    # A fuzzy score would call these ~90% similar; the strict rule refuses them.
    assert strict_name_match("Kaish Ahmad", "Kaish Ahmed")[0] is False


def test_different_given_names_are_not_matched():
    assert strict_name_match("Rajesh Kumar", "Suresh Kumar")[0] is False


def test_case_local_identifiers_and_bare_initials_are_not_matchable():
    assert not is_matchable_person_name("A-1")
    assert not is_matchable_person_name("Accused No. 2")
    assert not is_matchable_person_name("R K")
    assert is_matchable_person_name("Kaish Ahmad")
    assert is_matchable_person_name("Ashraf")


# ── vehicles and phones ──────────────────────────────────────────────────────


def test_vehicle_registration_is_normalized():
    keys = extract_vehicle_keys("went to the District Court in their nephew's car bearing number UP 70 FB 5433.")
    assert list(keys) == ["UP70FB5433"]


def test_phone_counts_only_with_telecom_context():
    assert list(extract_phone_keys("The accused used mobile 9876543210 to call the co-accused.")) == ["+919876543210"]
    assert extract_phone_keys("The seized register carried the entry 9876543210 on page 4.") == {}
