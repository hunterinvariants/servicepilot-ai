ARTICLES = [
    {"title": "Emergency safety", "keywords": {"gas", "fire", "sparking", "smoke"},
     "text": "Leave the property if unsafe and contact local emergency services. Never wait for an online booking."},
    {"title": "Water leaks", "keywords": {"leak", "water", "pipe", "flooding"},
     "text": "If safe, close the nearest isolation valve and move valuables away from water."},
    {"title": "Heating", "keywords": {"boiler", "heating", "radiator", "furnace"},
     "text": "Check the thermostat and visible error code. Do not remove sealed appliance covers."},
]


def retrieve(query: str, limit: int = 2) -> list[dict]:
    words = set(query.lower().split())
    ranked = sorted(ARTICLES, key=lambda item: len(words & item["keywords"]), reverse=True)
    return [{"title": item["title"], "text": item["text"]} for item in ranked if words & item["keywords"]][:limit]
