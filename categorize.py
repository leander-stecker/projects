"""
categorize.py
-------------
Assigns a category (groceries, rent, ...) to every transaction, based on
keywords in the recipient ("Empfänger") and the purpose ("Verwendungszweck").

Run it directly to categorize Empf.csv (a table with an "Empfänger" column)
and see which recipients are still unmatched:
    python categorize.py
Or import categorize_df() in your own code to categorize a transactions table.

Before the first run, fill in the SETUP block below. The keyword lists in
CATEGORIES are a generic starting point: add the shops and places you use.

HOW THE KEYWORDS WORK
- Text is lowercased, umlauts become ae/oe/ue/ss, and every character that
  is not a letter or digit becomes a space. "REWE SAGT DANKE. 1234/Musterstadt"
  becomes " rewe sagt danke 1234 musterstadt ".
- A keyword matches if it appears anywhere in that text.
- Spaces in a keyword mark word borders:
    "burger"   matches "Hamburger Sparkasse"  (anywhere inside a word)
    " burger"  matches "Burgermeister", not "Hamburger"  (word must START with it)
    " bar "    matches "Gran Bar", not "Barbershop"     (whole word only)
- Categories are checked from top to bottom and the FIRST match wins,
  so put specific categories above general ones.
"""

from pathlib import Path
import re
import unicodedata

import pandas as pd

# ============================== SETUP ==============================
# Write all keywords in lowercase, with ae/oe/ue/ss instead of umlauts, and
# with spaces around them to match whole words only (see HOW THE KEYWORDS
# WORK above). Empty lists are fine: the rule is then simply never used.

# Your own surname and those of family members, so that transfers between
# your own accounts or within the family are recognized.
#   Example: [" mustermann "]
OWN_NAMES = []

# Your landlord(s) or property management, as they appear on the statement.
#   Example: [" erika musterfrau ", "musterhaus immobilien"]
LANDLORDS = []

# Your employer(s) or other regular sources of income, as they appear on
# the statement. Only used for money coming IN.
#   Example: ["muster gmbh", "universitaet musterstadt"]
EMPLOYERS = []
# ===================================================================

OTHER = "Other"
INCOME = "Income"
PAYMENT_PROVIDER = "Payment service (unclear)"
PRIVATE = "Private persons"
RENT = "Rent & Housing"

# Words that show a recipient is a company, not a person.
COMPANY_WORDS = {
    "gmbh", "ag", "kg", "ohg", "ug", "ev", "gbr", "se", "sa", "srl", "srls", "spa",
    "lda", "unip", "ltd", "inc", "llc", "bv", "co", "bank", "sagt", "dankt", "danke",
}

# Only checked for money coming IN (amount > 0).
INCOME_KEYWORDS = EMPLOYERS + [
    " gehalt", " lohn", "bezuege",
]

# Checked top to bottom, first match wins.
CATEGORIES = {
    "Cash": [
        " ga nr", "geldautomat", "bargeld",
    ],
    "Transfers (own/family)": OWN_NAMES,
    RENT: LANDLORDS + [
        "miet", " rent ", "kaution", "wohnung", "vermiet", "hausverwaltung", "nebenkosten",
    ],
    "Utilities & Telecom": [
        "telefonica", "telecom", "telekom", "vodafone", "1und1",
        "stadtwerke", " strom", "rundfunk",
    ],
    "Insurance": [
        "versicherung", "krankenkasse", " allianz", " huk", " ergo ",
    ],
    "Taxes & Fees": [
        "finanzamt", "bundesamt", "bundeskasse", "landeskasse", "hauptkasse", "gebuehr",
    ],
    "Subscriptions": [
        "netflix", "spotify", "disney",
    ],
    "Transport": [
        "deutsche bahn", " db ", "flixbus", "verkehrsbetriebe",
        " bvg", " mvg", " hvv", " kvb",
        " uber ", " bolt ", " taxi ", "parken", "parking", "sixt", "europcar",
        " aral ", " shell ", " esso ", "tankstelle",
    ],
    "Travel (flights & hotels)": [
        "lufthan", "airline", "airways", "ryanair", "easyjet", "eurowings",
        "booking", "airbnb", "hotel", "hostel", "airport", "flughafen",
    ],
    "Groceries": [
        " rewe ", "edeka", " aldi ", " lidl ", " penny ", " netto ", "kaufland",
        "biomarkt", " denns", "alnatura", "flaschenpost", "metzgerei",
    ],
    "Bakery & Café": [
        "baeck", "backer", "bakery", "backwerk", "konditorei",
        "cafe", "caffe", "coffee", "kaffee", "starbucks", "tchibo", "kamps",
    ],
    "Restaurants & Takeaway": [
        " restaur", "ristorante", "osteria", "trattoria", "pizz", "sushi", " burger",
        "kebab", "kebap", "doner", "falafel", "grill", "bistro", "mensa",
        "studentenwerk", "studierendenwerk", "mcdonald", " kfc ", "subway",
        "lieferando", "wolt", " bar ", " pub ", "imbiss",
        " tst ",  # "TST" = Toast, a payment system used almost only by restaurants
    ],
    "Drugstore, Health & Care": [
        "dm drogerie", "rossmann", "mueller sagt", "apothe", "pharma", "arzt",
        "optik", "friseur",
    ],
    "Games & Hobbies": [
        "spiel", "games", "steam", " verein",
    ],
    "Shopping": [
        "amazon", "mediamarkt", "saturn", "ikea", " obi ", "bauhaus", "thalia",
        "decathlon", "zalando", "deutsche post", " dhl ",
    ],
    "Leisure, Culture & Sport": [
        "museum", " zoo ", " kino", "cinema", "theater", "konzert", "ticket", "eventim",
    ],
    "Work & Education": EMPLOYERS + [
        "universit", "hochschul",
    ],
    # Kept last: payment services hide the real shop. If the purpose text
    # names the shop, that is used instead (see categorize()).
    PAYMENT_PROVIDER: [
        "paypal", "klarna", "adyen", "payone", "sumup", "zettle",
        " sq ",  # Square card terminals
    ],
}


def normalize(text):
    """Make text easy to search: ' rewe sagt danke 1234 musterstadt '."""
    if not isinstance(text, str):
        return " "
    text = text.lower()
    for umlaut, replacement in {"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"}.items():
        text = text.replace(umlaut, replacement)
    # Remove other accents: "ż" -> "z", "é" -> "e".
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    # Everything that is not a letter or digit becomes a single space.
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return f" {text.strip()} "


def match_category(text):
    """Return the first category whose keyword appears in text, else None."""
    text = normalize(text)
    for category, keywords in CATEGORIES.items():
        if any(keyword in text for keyword in keywords):
            return category
    return None


def looks_like_person(empfaenger):
    """Guess whether a recipient is a private person, e.g. "Erika Mustermann".

    A person's name is 2 to 6 words that contain only letters (hyphens and
    dots are fine, e.g. "Anna-Lena", "Dr."). Shops usually have digits or a
    "/" (address), or a company word like GmbH.
    """
    if not isinstance(empfaenger, str):
        return False
    # International transfers pad the name with many spaces, followed by the
    # address: "ERIKA MUSTERMANN          MUSTERSTRASSE 1 BERLIN". Keep only the name.
    empfaenger = re.split(r" {3,}", empfaenger.strip())[0]
    # Split at spaces and commas: "Mustermann, Max" -> ["Mustermann", "Max"]
    words = [w for w in re.split(r"[ ,]+", empfaenger.strip()) if w]
    if not 2 <= len(words) <= 6:
        return False
    for word in words:
        bare = word.replace("-", "").replace(".", "")
        # isalpha() is True only if every character is a letter (umlauts count).
        if not bare.isalpha() or bare.lower() in COMPANY_WORDS:
            return False
    return True


def load_manual():
    """Read manual_categories.csv (made with label_other.py) into a dict.

    Returns {Empfänger: Kategorie}, or an empty dict if the file doesn't exist yet.
    """
    path = Path(__file__).parent / "manual_categories.csv"
    if not path.is_file():
        return {}
    manual = pd.read_csv(path)
    # zip() pairs up both columns: ("Beispiel GmbH", "Restaurants & Takeaway"), ...
    return {e.strip(): k for e, k in zip(manual["Empfänger"], manual["Kategorie"])}


# Loaded once when the script starts (or is imported), not for every row.
MANUAL = load_manual()


def categorize(empfaenger, verwendungszweck="", betrag=None):
    """Return the category for one transaction."""
    # Your manual choices win over all keyword rules.
    if isinstance(empfaenger, str) and empfaenger.strip() in MANUAL:
        return MANUAL[empfaenger.strip()]

    if betrag is not None and betrag > 0:
        both = normalize(empfaenger) + normalize(verwendungszweck)
        if any(keyword in both for keyword in INCOME_KEYWORDS):
            return INCOME

    category = match_category(empfaenger)

    # A private person: rent if the purpose says so, otherwise "Private persons".
    if category is None and looks_like_person(empfaenger):
        purpose = normalize(verwendungszweck)
        if any(keyword in purpose for keyword in CATEGORIES[RENT]):
            return RENT
        return PRIVATE

    # Recipient unknown, or just PayPal & co.? Then try the purpose text.
    if category in (None, PAYMENT_PROVIDER):
        category = match_category(verwendungszweck) or category

    if category is None:
        return OTHER
    return category


def categorize_df(df):
    """Return a Series with the category of every row of a transactions table."""
    return df.apply(
        lambda row: categorize(row["Empfänger"], row["Verwendungszweck"], row["Betrag"]),
        axis=1,
    )


# ---------- REVIEW MODE: python categorize.py ----------

if __name__ == "__main__":
    folder = Path(__file__).parent
    recipients = pd.read_csv(folder / "Empf.csv", index_col=0)
    recipients["Kategorie"] = recipients["Empfänger"].apply(categorize)
    recipients.to_csv(folder / "Empf_kategorien.csv", index=False)

    print(recipients["Kategorie"].value_counts().to_string(), "\n")
    print("Unmatched recipients:")
    print(recipients.loc[recipients["Kategorie"] == OTHER, "Empfänger"].to_string())
