"""Contextual legal-role filter for Indian court judgments.

Filters out judicial and legal personnel who are not network targets:
- Judges, Justices, Magistrates
- Advocates, Counsels, Senior Counsels, Amicus Curiae
- Public Prosecutors, APPs, SPPs, Defence Counsels

Conservative:
- Distinguishes "Advocate Rajesh Sharma appeared for the accused" from "Rajesh Sharma met A-1 near the station"
- When ambiguous, favors retention (avoids false rejections of actual participants)
"""

from __future__ import annotations

import re
from typing import Any

# Specific judicial title prefixes attached directly to names
JUDICIAL_TITLE_PREFIXES = [
    r"hon(?:'|\s*)ble\s+(?:mr\.?\s+|ms\.?\s+|mrs\.?\s+|dr\.?\s+)?justice",
    r"hon(?:'|\s*)ble\s+the\s+chief\s+justice",
    r"mr\.?\s+justice",
    r"ms\.?\s+justice",
    r"chief\s+justice",
    r"justice",
    r"sessions\s+judge",
    r"additional\s+sessions\s+judge",
    r"addl\.?\s+sessions\s+judge",
    r"district\s+judge",
    r"metropolitan\s+magistrate",
    r"judicial\s+magistrate",
    r"special\s+judge",
]

# Specific legal counsel title prefixes attached directly to names
COUNSEL_TITLE_PREFIXES = [
    r"learned\s+(?:senior\s+)?counsel",
    r"learned\s+(?:special\s+)?public\s+prosecutor",
    r"learned\s+(?:addl\.?\s+|additional\s+)?app",
    r"senior\s+counsel",
    r"senior\s+advocate",
    r"special\s+public\s+prosecutor",
    r"public\s+prosecutor",
    r"additional\s+public\s+prosecutor",
    r"amicus\s+curiae",
    r"defence\s+counsel",
    r"defense\s+counsel",
    r"standing\s+counsel",
    r"government\s+pleader",
    r"advocate\s+general",
    r"solicitor\s+general",
    r"additional\s+solicitor\s+general",
    r"advocate",
    r"adv\.",
]

# Patterns for judicial titles preceding a name within ~40 chars
PRE_JUDICIAL_REGEX = re.compile(
    r"(?:" + "|".join(JUDICIAL_TITLE_PREFIXES) + r")\s+(?:[A-Z][a-z]+\s+)?$",
    re.IGNORECASE,
)

# Patterns for counsel titles preceding a name within ~40 chars
PRE_COUNSEL_REGEX = re.compile(
    r"(?:" + "|".join(COUNSEL_TITLE_PREFIXES) + r")\s+(?:for\s+(?:the\s+)?\w+\s+)?(?:mr\.?|ms\.?|shri|dr\.?)?\s*$",
    re.IGNORECASE,
)

# Patterns for appearance/court blocks (e.g. "For the Appellant: Mr. X")
PRE_APPEARANCE_REGEX = re.compile(
    r"(?:for\s+(?:the\s+)?(?:appellant|petitioner|respondent|state|prosecution|accused|applicant|opposite\s+party)|coram|before)\s*[:–-]\s*(?:mr\.?|ms\.?|shri|dr\.?)?\s*$",
    re.IGNORECASE,
)

# Patterns for judicial or counsel titles immediately following a name within ~40 chars
POST_JUDICIAL_REGEX = re.compile(
    r"^\s*,\s*(?:(?:hon(?:'|\s*)ble\s+)?justice|j\.|c\.?j\.?|chief\s+justice|(?:sessions\s+|special\s+)?judge|magistrate)\b",
    re.IGNORECASE,
)

POST_COUNSEL_REGEX = re.compile(
    r"^\s*,\s*(?:learned\s+)?(?:(?:senior\s+)?counsel|advocate|adv\.|public\s+prosecutor|app|special\s+public\s+prosecutor|amicus\s+curiae|standing\s+counsel|government\s+pleader)\b",
    re.IGNORECASE,
)

# Action verbs commonly following counsel names
COUNSEL_ACTION_REGEX = re.compile(
    r"^\s+(?:appeared\s+(?:for|on\s+behalf\s+of)|argued\s+the|submitted\s+that|contended\s+that|learned\s+counsel)\b",
    re.IGNORECASE,
)

# General boilerplate non-person terms that spaCy sometimes misclassifies as PERSON/ORG
NON_PERSON_TOKENS = {
    "appellant",
    "appellants",
    "respondent",
    "respondents",
    "petitioner",
    "petitioners",
    "complainant",
    "accused",
    "witness",
    "prosecution",
    "state",
    "court",
    "high court",
    "supreme court",
    "police",
    "coram",
    "bench",
    "tribunal",
    "session",
    "judgment",
    "order",
    "indian penal code",
    "crpc",
    "ipc",
}


def is_legal_role(
    name: str,
    text: str,
    start_char: int,
    end_char: int,
) -> tuple[bool, str | None]:
    """Determine whether an extracted entity refers to a legal role (judge or counsel).

    Returns:
        (True, reason) if entity should be filtered out.
        (False, None) if entity should be retained.
    """
    clean_name = name.strip()
    name_lower = clean_name.lower()

    # 1. Exact non-person or procedural token match
    if name_lower in NON_PERSON_TOKENS:
        return True, f"generic_legal_token:{name_lower}"

    # 2. Name itself starts with judicial title
    for pat in JUDICIAL_TITLE_PREFIXES:
        if re.match(r"^" + pat + r"\b", name_lower):
            return True, f"judicial_title_in_name:{pat}"

    # 3. Name itself starts with counsel title
    for pat in COUNSEL_TITLE_PREFIXES:
        if re.match(r"^" + pat + r"\b", name_lower):
            return True, f"counsel_title_in_name:{pat}"

    # 4. Judicial suffix in name itself (e.g. "R.F. Nariman, J." or "Chandrachud, CJ")
    if re.search(r",?\s+(?:J\.|CJ|CJI)$", clean_name):
        return True, "judicial_suffix_in_name"

    # Contextual analysis around character span in the source text
    if 0 <= start_char <= len(text) and 0 <= end_char <= len(text):
        window_pre = text[max(0, start_char - 60) : start_char]
        window_post = text[end_char : min(len(text), end_char + 60)]

        # Check appearance line context (e.g., "For the Appellant: Mr. Rajesh Sharma")
        if PRE_APPEARANCE_REGEX.search(window_pre):
            return True, "appearance_roster_context"

        # Check pre-context for judicial titles
        if PRE_JUDICIAL_REGEX.search(window_pre):
            return True, "judicial_title_preceding"

        # Check pre-context for counsel titles
        if PRE_COUNSEL_REGEX.search(window_pre):
            return True, "counsel_title_preceding"

        # Check post-context for judicial suffix (e.g., "Rajesh Kumar, J.")
        if POST_JUDICIAL_REGEX.search(window_post):
            return True, "judicial_title_following"

        # Check post-context for counsel suffix (e.g., "Rajesh Kumar, learned counsel")
        if POST_COUNSEL_REGEX.search(window_post):
            return True, "counsel_title_following"

        # Check counsel argument context (e.g., "Rajesh Kumar appeared for the appellant")
        if COUNSEL_ACTION_REGEX.search(window_post):
            return True, "counsel_action_following"

    return False, None


def filter_legal_roles(
    entities: list[dict[str, Any]],
    text: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Partition candidate entities into accepted entities and filtered legal roles.

    Returns:
        (accepted_entities, filtered_entities)
    """
    accepted: list[dict[str, Any]] = []
    filtered: list[dict[str, Any]] = []

    for entity in entities:
        # Only PERSON entities need legal-role filtering
        if entity.get("entity_type") not in {"PERSON", "ACCUSED"}:
            accepted.append(entity)
            continue

        name = entity.get("name", "")
        start_char = entity.get("start_char", -1)
        end_char = entity.get("end_char", -1)

        is_filtered, reason = is_legal_role(name, text, start_char, end_char)
        if is_filtered:
            filtered_record = dict(entity)
            filtered_record["filter_reason"] = reason
            filtered.append(filtered_record)
        else:
            accepted.append(entity)

    return accepted, filtered
