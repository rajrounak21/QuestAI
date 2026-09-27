from __future__ import annotations

import re

# Alias map: variant -> canonical (lowercase, no spaces)
ALIAS_MAP: dict[str, str] = {
    # core
    "fast api": "fastapi",
    "fast_api": "fastapi",
    "fast-api": "fastapi",
    "mongo db": "mongodb",
    "mongo_db": "mongodb",
    "mongo-db": "mongodb",
    "postgress": "postgresql",
    "postgres": "postgresql",
    "postgresql": "postgresql",
    "llms": "llm",
    "large language models": "llm",
    "large language model": "llm",
    "js": "javascript",
    "ts": "typescript",
    "k8s": "kubernetes",
    "k8": "kubernetes",
    "gcp": "google cloud",
    "google cloud platform": "google cloud",
    "reactjs": "react",
    "react js": "react",
    "nextjs": "nextjs",
    "next js": "nextjs",
    "node js": "nodejs",
    "node.js": "nodejs",
    "express js": "express",
    "tailwind": "tailwind",
    "tailwindcss": "tailwind",
    "pytorch": "pytorch",
    "tensorflow": "tensorflow",
    # extra common
    "scikit learn": "scikit-learn",
    "scikit-learn": "scikit-learn",
}

# Build reverse: for each canonical, list variants that map to it
CANONICAL_TO_ALIASES: dict[str, list[str]] = {}
for variant, canon in ALIAS_MAP.items():
    CANONICAL_TO_ALIASES.setdefault(canon, []).append(variant)
# Also canonical maps to itself
for canon in list(CANONICAL_TO_ALIASES.keys()):
    if canon not in CANONICAL_TO_ALIASES[canon]:
        CANONICAL_TO_ALIASES[canon].append(canon)
# Ensure canonicals that are not keys also self-map via function

def _clean(s: str) -> str:
    s = s.strip().lower()
    # collapse underscores/hyphens to space then single spaces
    s = s.replace("_", " ").replace("-", " ")
    s = re.sub(r"\s+", " ", s)
    return s.strip()

def normalize_skill(s: str) -> str:
    """Map any skill string to canonical lower form."""
    cleaned = _clean(s)
    # direct alias lookup
    if cleaned in ALIAS_MAP:
        return ALIAS_MAP[cleaned]
    # already canonical - remove internal spaces for single tokens like fastapi?
    # Keep as cleaned but without spaces for single-word skills: fast api -> fastapi handled above
    # For others, keep spaced form e.g. "google cloud" stays spaced
    return cleaned

def normalized_aliases(canonical: str) -> list[str]:
    """Return all variant strings for a canonical skill (including itself)."""
    canon = _clean(canonical)
    # canonical itself normalized
    base = normalize_skill(canon)
    # find aliases that map to base
    variants = set([base])
    # add explicit variants
    for variant, target in ALIAS_MAP.items():
        if target == base:
            variants.add(variant)
            variants.add(_clean(variant))
    # also add base with spaces removed if base has space (e.g. google cloud -> googlecloud? no, keep)
    return list(variants)

# Vocab for deterministic typo gate — common roles + locations
ROLE_VOCAB = [
    "python","developer","engineer","ai","backend","frontend","fullstack","intern","internship",
    "data","science","machine","learning","ml","genai","generative","robotics","software","java","nodejs","javascript","typescript","mumbai","delhi","bangalore","bengaluru","patna","pune","hyderabad","chennai","kolkata","gurgaon","gurugram","noida","haryana","rewa","gujarat","gujrat","bihar",
]
LOCATION_VOCAB = [
    "india","delhi","bangalore","bengaluru","patna","mumbai","pune","hyderabad","chennai","kolkata","gurgaon","gurugram","noida","greater noida","rewa","vasai-virar","navi mumbai","haryana","bihar","andhra pradesh","karnataka","gandhi nagar","ambala","hisar","austin","texas","remote","hybrid","onsite",
]
