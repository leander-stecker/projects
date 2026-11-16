"""
label_other.py
--------------
Goes through every recipient in Empf.csv that categorize.py puts into
"Other" and asks you for a category shorthand.

    Enter      -> skip (stays "Other")
    a code     -> saved to manual_categories.csv
    ?          -> show the list of codes again
    q          -> quit (everything typed so far is already saved)

Each answer is saved immediately, so you can stop at any time. Recipients
already in manual_categories.csv are not asked again.
"""

from pathlib import Path
import csv

import pandas as pd

from categorize import categorize, OTHER, PRIVATE, INCOME, PAYMENT_PROVIDER, CATEGORIES

FOLDER = Path(__file__).parent
RECIPIENTS_FILE = FOLDER / "Empf.csv"
MANUAL_FILE = FOLDER / "manual_categories.csv"

# Shorthand -> category. Change the codes to whatever you find easy to type.
SHORTCUTS = {
    "re": "Restaurants & Takeaway",
    "cf": "Bakery & Café",
    "gr": "Groceries",
    "sh": "Shopping",
    "tr": "Transport",
    "tv": "Travel (flights & hotels)",
    "le": "Leisure, Culture & Sport",
    "ga": "Games & Hobbies",
    "he": "Drugstore, Health & Care",
    "rt": "Rent & Housing",
    "ut": "Utilities & Telecom",
    "in": "Insurance",
    "tx": "Taxes & Fees",
    "su": "Subscriptions",
    "wo": "Work & Education",
    "cs": "Cash",
    "fa": "Transfers (own/family)",
    "pp": PRIVATE,
    "inc": INCOME,
    "pay": PAYMENT_PROVIDER,
}


def check_shortcuts():
    """Warn if a shortcut points to a category that categorize.py doesn't know.

    That happens if you rename a category in categorize.py but not here.
    """
    known = set(CATEGORIES) | {PRIVATE, INCOME}
    for code, category in SHORTCUTS.items():
        if category not in known:
            print(f"Warning: shortcut '{code}' -> '{category}' is not a category in categorize.py")


def print_legend():
    print("\nCodes:")
    for code, category in SHORTCUTS.items():
        print(f"  {code:4} {category}")
    print("  Enter = skip, ? = show codes, q = quit\n")


def load_done():
    """Return the set of recipients that already have a manual category."""
    if not MANUAL_FILE.is_file():
        return set()
    return set(pd.read_csv(MANUAL_FILE)["Empfänger"])


def save(empfaenger, category):
    """Append one line to manual_categories.csv (with header if the file is new)."""
    is_new = not MANUAL_FILE.is_file()
    # "a" = append mode: adds to the end instead of overwriting the file.
    with open(MANUAL_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if is_new:
            writer.writerow(["Empfänger", "Kategorie"])
        writer.writerow([empfaenger, category])


def main():
    check_shortcuts()

    recipients = pd.read_csv(RECIPIENTS_FILE, index_col=0)["Empfänger"].dropna().unique()
    done = load_done()
    todo = [e for e in recipients if categorize(e) == OTHER and e not in done]

    if not todo:
        print("Nothing left in 'Other'.")
        return

    print(f"{len(todo)} recipients in 'Other'.")
    print_legend()

    saved = 0
    for number, empfaenger in enumerate(todo, start=1):
        # " ".join(text.split()) squeezes long runs of spaces for display.
        shown = " ".join(empfaenger.split())
        while True:
            answer = input(f"[{number}/{len(todo)}] {shown}\n  > ").strip().lower()
            if answer == "":
                break
            if answer == "q":
                print(f"\nStopped. {saved} saved to {MANUAL_FILE.name}.")
                return
            if answer == "?":
                print_legend()
                continue
            if answer in SHORTCUTS:
                save(empfaenger, SHORTCUTS[answer])
                saved += 1
                print(f"  -> {SHORTCUTS[answer]}")
                break
            print("  Unknown code, type ? for the list.")

    print(f"\nDone. {saved} saved to {MANUAL_FILE.name}.")


if __name__ == "__main__":
    main()
