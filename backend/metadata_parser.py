import re


# Common retailer names to detect in file names
RETAILERS = {
    "ah": "Albert Heijn",
    "albert heijn": "Albert Heijn",
    "albert_heijn": "Albert Heijn",
    "jumbo": "Jumbo",
    "lidl": "Lidl",
    "aldi": "Aldi",
    "plus": "Plus",
    "dirk": "Dirk",
    "coop": "Coop",
    "ekoplaza": "Ekoplaza",
    "tesco": "Tesco",
    "sainsburys": "Sainsbury's",
    "sainsbury": "Sainsbury's",
    "waitrose": "Waitrose",
    "morrisons": "Morrisons",
    "asda": "Asda",
    "rewe": "REWE",
    "edeka": "Edeka",
    "ica": "ICA",
    "coop": "Coop",
    "carrefour": "Carrefour",
    "monoprix": "Monoprix",
    "delhaize": "Delhaize",
    "colruyt": "Colruyt",
    "migros": "Migros",
    "spar": "Spar",
    "netto": "Netto",
    "irma": "Irma",
}

# Country/city patterns
COUNTRIES = {
    "nl": ("Netherlands", "EUR"),
    "netherlands": ("Netherlands", "EUR"),
    "uk": ("United Kingdom", "GBP"),
    "gb": ("United Kingdom", "GBP"),
    "de": ("Germany", "EUR"),
    "germany": ("Germany", "EUR"),
    "fr": ("France", "EUR"),
    "france": ("France", "EUR"),
    "be": ("Belgium", "EUR"),
    "belgium": ("Belgium", "EUR"),
    "se": ("Sweden", "SEK"),
    "sweden": ("Sweden", "SEK"),
    "dk": ("Denmark", "DKK"),
    "denmark": ("Denmark", "DKK"),
    "ch": ("Switzerland", "CHF"),
    "switzerland": ("Switzerland", "CHF"),
    "no": ("Norway", "NOK"),
    "norway": ("Norway", "NOK"),
}

CITIES = {
    "amsterdam": ("Amsterdam", "Netherlands", "EUR"),
    "rotterdam": ("Rotterdam", "Netherlands", "EUR"),
    "utrecht": ("Utrecht", "Netherlands", "EUR"),
    "den_haag": ("The Hague", "Netherlands", "EUR"),
    "the_hague": ("The Hague", "Netherlands", "EUR"),
    "london": ("London", "United Kingdom", "GBP"),
    "paris": ("Paris", "France", "EUR"),
    "berlin": ("Berlin", "Germany", "EUR"),
    "munich": ("Munich", "Germany", "EUR"),
    "brussels": ("Brussels", "Belgium", "EUR"),
    "antwerp": ("Antwerp", "Belgium", "EUR"),
    "copenhagen": ("Copenhagen", "Denmark", "DKK"),
    "stockholm": ("Stockholm", "Sweden", "SEK"),
    "zurich": ("Zurich", "Switzerland", "CHF"),
    "oslo": ("Oslo", "Norway", "NOK"),
}

SHELF_LOCATIONS = {
    "juice": "Juice Aisle — Chilled",
    "chilled": "Chilled Section",
    "dairy": "Dairy Section — Chilled",
    "health": "Health Food Section",
    "organic": "Organic Section",
    "smoothie": "Smoothie Section — Chilled",
    "fridge": "Chilled Section",
}

STORE_FORMATS = {
    "xl": "Hypermarket",
    "hyper": "Hypermarket",
    "super": "Supermarket",
    "express": "Express",
    "to go": "Convenience",
    "togo": "Convenience",
    "city": "Convenience",
    "mini": "Convenience",
    "compact": "Convenience",
}


def parse_metadata_from_filenames(filenames: list[str]) -> dict:
    """
    Extract store metadata from photo file names.
    Returns a dict with detected values (may be partial).
    """
    combined = " ".join(filenames).lower().replace("_", " ").replace("-", " ")

    result = {
        "country": "",
        "city": "",
        "retailer": "",
        "store_format": "",
        "store_name": "",
        "shelf_location": "",
        "currency": "",
    }

    # Detect retailer
    for key, name in RETAILERS.items():
        if key in combined:
            result["retailer"] = name
            break

    # Detect city (which also gives us country)
    for key, (city, country, currency) in CITIES.items():
        if key in combined:
            result["city"] = city
            result["country"] = country
            result["currency"] = currency
            break

    # If no city found, try country directly
    if not result["country"]:
        for key, (country, currency) in COUNTRIES.items():
            if key in combined:
                result["country"] = country
                result["currency"] = currency
                break

    # Detect shelf location
    for key, location in SHELF_LOCATIONS.items():
        if key in combined:
            result["shelf_location"] = location
            break

    # Detect store format
    for key, fmt in STORE_FORMATS.items():
        if key in combined:
            result["store_format"] = fmt
            break

    # Default store format if retailer is known but format isn't
    if result["retailer"] and not result["store_format"]:
        result["store_format"] = "Supermarket"

    return result
