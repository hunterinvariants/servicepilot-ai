import re


INJECTION_PATTERNS = [
    r"ignore (all|any|the) (previous|prior|system) instructions",
    r"reveal (your|the) (prompt|system message|secrets?)",
    r"call (the )?tool",
    r"developer mode",
    r"<\s*(system|assistant|tool)\s*>",
]


def inspect_untrusted_text(text: str) -> list[str]:
    flags = []
    lowered = text.lower()
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, lowered):
            flags.append("possible_prompt_injection")
            break
    if any(word in lowered for word in ("gas leak", "fire", "sparking", "carbon monoxide")):
        flags.append("life_safety_risk")
    return flags


def safe_excerpt(text: str, limit: int = 1000) -> str:
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)[:limit]

