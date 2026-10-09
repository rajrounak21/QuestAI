"""Resolve a place the user typed into an IATA airport code.

The trip stores whatever the user said ("Mumbai", "Bali"), but
google_flights requires 3-letter IATA codes for departure_id/arrival_id.

This used to be done by the flight-extraction LLM. That call was removed from
the trip path because it round-tripped values the trip already had - but it was
also silently doing this conversion, so sending "Mumbai" straight to SerpApi
produced a 400 on every search. A static table resolves it instantly and
deterministically instead.

Returns None when the place is unknown, so the caller can ask the user rather
than spend a search on a request that can only fail.
"""

from __future__ import annotations

# Primary airport per city. For multi-airport cities the main one is chosen:
# the trip is city-level, not airport-level.
CITY_TO_IATA: dict[str, str] = {
    # --- India ---
    "mumbai": "BOM", "bombay": "BOM",
    "delhi": "DEL", "new delhi": "DEL", "delhi ncr": "DEL",
    "bangalore": "BLR", "bengaluru": "BLR",
    "hyderabad": "HYD", "chennai": "MAA", "madras": "MAA",
    "kolkata": "CCU", "calcutta": "CCU", "pune": "PNQ",
    "ahmedabad": "AMD", "jaipur": "JAI", "goa": "GOI",
    "kochi": "COK", "cochin": "COK", "lucknow": "LKO",
    "chandigarh": "IXC", "guwahati": "GAU", "patna": "PAT",
    "bhubaneswar": "BBI", "varanasi": "VNS", "agra": "AGR",
    "amritsar": "ATQ", "udaipur": "UDR", "jodhpur": "JOD",
    "leh": "IXL", "srinagar": "SXR", "port blair": "IXB",
    "dehradun": "DED", "ranchi": "IXR", "bhubaneswar odisha": "BBI",
    # --- South / Southeast Asia ---
    "bali": "DPS", "denpasar": "DPS", "kuta": "DPS", "ubud": "DPS",
    "jakarta": "CGK", "bangkok": "BKK", "phuket": "HKT", "krabi": "KBV",
    "singapore": "SIN", "kuala lumpur": "KUL", "kl": "KUL",
    "hong kong": "HKG", "macau": "MFM",
    "penang": "PEN", "bali denpasar": "DPS", "gili islands": "LOP",
    "johor bahru": "JHB", "batam": "BTH", "lombok": "LOP",
    "manila": "MNL", "hanoi": "HAN", "ho chi minh city": "SGN",
    "phnom penh": "PNH", "yangon": "RGN", "chiang mai": "CNX",
    "siem reap": "SAI", "luang prabang": "LPQ",
    # --- Middle East ---
    "dubai": "DXB", "abu dhabi": "AUH", "doha": "DOH", "riyadh": "RUH",
    "jeddah": "JED", "muscat": "MCT", "kuwait city": "KWI",
    "bahrain": "BAH", "manama": "BAH", "amman": "AMM", "beirut": "BEY",
    "tel aviv": "TLV", "istanbul": "IST", "antalya": "AYT",
    # --- Europe ---
    "london": "LHR", "manchester": "MAN", "edinburgh": "EDI",
    "paris": "CDG", "lyon": "LYS", "nice": "NCE",
    "rome": "FCO", "milan": "MXP", "venice": "VCE", "florence": "FLR",
    "naples": "NAP",
    "barcelona": "BCN", "madrid": "MAD", "seville": "SVQ",
    "lisbon": "LIS", "porto": "OPO",
    "berlin": "BER", "munich": "MUC", "münchen": "MUC", "hamburg": "HAM",
    "frankfurt": "FRA", "cologne": "CGN", "düsseldorf": "DUS",
    "amsterdam": "AMS", "brussels": "BRU", "zurich": "ZRH",
    "geneva": "GVA", "vienna": "VIE", "prague": "PRG", "budapest": "BUD",
    "athens": "ATH", "santorini": "JTR", "mykonos": "JMK",
    "istanbul tan": "IST", "copenhagen": "CPH", "stockholm": "ARN",
    "oslo": "OSL", "helsinki": "HEL", "dublin": "DUB", "edinburgh sco": "EDI",
    "warsaw": "WAW", "krakow": "KRK", "budapest hu": "BUD",
    # --- Americas ---
    "new york": "JFK", "new york city": "JFK", "nyc": "JFK",
    "los angeles": "LAX", "san francisco": "SFO", "chicago": "ORD",
    "miami": "MIA", "orlando": "MCO", "las vegas": "LAS",
    "seattle": "SEA", "boston": "BOS", "washington dc": "IAD",
    "san diego": "SAN", "denver": "DEN", "austin": "AUS",
    "honolulu": "HNL", "anchorage": "ANC",
    "toronto": "YTO", "vancouver": "YVR", "montreal": "YUL",
    "mexico city": "MEX", "cancun": "CUN", "tijuana": "TIJ",
    "rio de janeiro": "GIG", "sao paulo": "GRU", "buenos aires": "EZE",
    "lima": "LIM", "bogota": "BOG", "medellin": "MDE", "santiago": "SCL",
    # --- Oceania / Africa ---
    "sydney": "SYD", "melbourne": "MEL", "brisbane": "BNE",
    "perth": "PER", "adelaide": "ADL", "auckland": "AKL",
    "queenstown": "ZQN", "wellington": "WLG", "fiji": "NAN",
    "dubai uae": "DXB",
    "cairo": "CAI", "marrakech": "RAK", "cape town": "CPT",
    "johannesburg": "JNB", "nairobi": "NBO", "lagos": "LOS",
    "casablanca": "CMN", "tunis": "TUN", "algiers": "ALG",
}

_ALIASES = {
    "ny": "JFK", "usa": "JFK", "uk": "LHR", "england": "LHR",
    "uae": "DXB", "thailand": "BKK", "indonesia": "DPS",
    "vietnam": "SGN", "nepal": "KTM", "sri lanka": "CMB",
    "malaysia": "KUL", "singapore sg": "SIN", "italy": "FCO",
    "france": "CDG", "spain": "BCN", "germany": "BER",
    "switzerland": "ZRH", "australia": "SYD", "canada": "YTO",
    "brazil": "GRU", "mexico": "MEX", "peru": "LIM", "chile": "SCL",
    "dubai city": "DXB", "new delhi india": "DEL", "mumbai india": "BOM",
    "goa india": "GOI", "bali indonesia": "DPS",
}


def _clean(place: str) -> str:
    return " ".join(str(place or "").strip().lower().split())


def resolve_iata(place: str) -> str | None:
    """Best-effort place -> IATA code. None when it cannot be resolved.

    Accepts an already-correct code unchanged, so callers do not have to know
    which form the value is in.
    """
    raw = _clean(place)
    if not raw:
        return None

    if raw in CITY_TO_IATA:
        return CITY_TO_IATA[raw]
    if raw in _ALIASES:
        return _ALIASES[raw]

    if len(raw) == 3 and raw.isalpha():
        return raw.upper()

    # "Bali (Indonesia)", "Mumbai, India", "JFK, New York" -> try the head.
    for sep in (",", "("):
        head = _clean(raw.split(sep)[0])
        if head and head != raw:
            if head in CITY_TO_IATA:
                return CITY_TO_IATA[head]
            if head in _ALIASES:
                return _ALIASES[head]
            if len(head) == 3 and head.isalpha():
                return head.upper()

    # Last resort: scan for any known place inside a longer phrase.
    parts = raw.replace("-", " ").split()
    for size in (2, 1):
        for i in range(len(parts) - size + 1):
            window = " ".join(parts[i : i + size])
            if window in CITY_TO_IATA:
                return CITY_TO_IATA[window]
    return None
