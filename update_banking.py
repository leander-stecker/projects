"""
update_banking.py
-----------------
Reads the latest exports of both banks, brings them into one common
format and merges them into transactions.csv (removing duplicates).

Before the first run, fill in the SETUP block below.
"""

from pathlib import Path
import sys

import pandas as pd

# ============================== SETUP ==============================
# A label for each of your accounts. It is written into the "Konto" column
# of every row, so you can always tell which account a transaction belongs
# to. Any text works: your IBAN, the last digits of the account number, or a
# nickname like "Giro" or "Savings".
# Choose it once and keep it: if you change it later, old and new rows
# no longer count as duplicates of each other.
# Leave a label "" only if you don't use that bank.
KONTO_BANK1 = ""
KONTO_BANK2 = ""
# ===================================================================

SCRIPT_DIR = Path(__file__).parent

BANK1_FILE = SCRIPT_DIR / "umsatz_neu.CSV"
BANK2_FILE = SCRIPT_DIR / "umsatz_neu_bank2.csv"
TRANSACTIONS_FILE = SCRIPT_DIR / "transactions.csv"

# The common format every bank gets converted into (column order of the output).
COLUMNS = ["Konto", "Betrag", "Tag", "Buchungstext", "Verwendungszweck", "Empfänger",
           "Kontonummer/IBAN", "BIC (SWIFT-Code)", "Waehrung", "Referenz"]


def parse_ddmmyy(series):
    """Turn dates like '07.10.26', '071026' or 71026 into real dates.

    Removing the dots and padding with zeros to 6 digits makes all three
    variants look like '071026', which we can then parse as day-month-year.
    """
    cleaned = series.astype(str).str.replace(".", "", regex=False).str.zfill(6)
    return pd.to_datetime(cleaned, format="%d%m%y")


# ---------- BANK 1 ----------
# Format: CSV export with ";" separators, latin1 encoding and the columns
# Buchungstag, Valutadatum, Beguenstigter/Zahlungspflichtiger, ...

def load_bank1(path):
    df = pd.read_csv(path, encoding="latin1", sep=";", decimal=",", thousands=".")
    df["Buchungstag"] = parse_ddmmyy(df["Buchungstag"])
    df = df.dropna(subset=["Valutadatum"])  # rows without Valutadatum are still pending
    df = df.rename(columns={"Beguenstigter/Zahlungspflichtiger": "Empfänger",
                            "Buchungstag": "Tag",
                            "Kundenreferenz (End-to-End)": "Referenz"})
    df["Konto"] = KONTO_BANK1
    return df[COLUMNS]


# ---------- BANK 2 ----------
# Format: "DATE_Umsatzliste_Girokonto_IBAN.csv", UTF-8, a few metadata lines
# on top, then the columns Buchungsdatum, Wertstellung, Status, ...

def find_header_line(path, first_column="Buchungsdatum"):
    """Return the line number where the real table starts.

    The export starts with a few metadata lines (account, balance, ...).
    Instead of hardcoding how many, we look for the line containing the
    first column name, so it keeps working if the bank adds a line.
    """
    with open(path, encoding="utf-8-sig") as f:
        for number, line in enumerate(f):
            if first_column in line:
                return number
    raise ValueError(f"No header line with '{first_column}' found in {path}")


def load_bank2(path):
    df = pd.read_csv(path, encoding="utf-8-sig", sep=";", decimal=",", thousands=".",
                     skiprows=find_header_line(path),
                     # Read these as text so they are not turned into numbers
                     # (dates would lose their dots, references would get '.0').
                     dtype={"Buchungsdatum": str, "Wertstellung": str,
                            "IBAN": str, "Kundenreferenz": str})
    df = df[df["Status"] == "Gebucht"]  # skip pending transactions

    # The other party depends on the direction of the money:
    # outgoing -> who received it, incoming -> who paid it.
    outgoing = df["Betrag (€)"] < 0
    empfaenger = df["Zahlungsempfänger*in"].where(outgoing, df["Zahlungspflichtige*r"])

    # Build the common format column by column.
    return pd.DataFrame({
        "Konto": KONTO_BANK2,
        "Betrag": df["Betrag (€)"],
        "Tag": parse_ddmmyy(df["Buchungsdatum"]),
        "Buchungstext": df["Umsatztyp"],
        "Verwendungszweck": df["Verwendungszweck"],
        "Empfänger": empfaenger,
        "Kontonummer/IBAN": df["IBAN"],  # for card payments this is a clearing account
        "BIC (SWIFT-Code)": pd.NA,       # not included in this bank's export
        "Waehrung": "EUR",
        "Referenz": df["Kundenreferenz"],
    })[COLUMNS]


# ---------- MERGE ----------

def check_setup():
    """Stop with a clear message if a bank file exists but has no label."""
    if BANK1_FILE.is_file() and not KONTO_BANK1:
        sys.exit("Please set KONTO_BANK1 in the SETUP block at the top of this script.")
    if BANK2_FILE.is_file() and not KONTO_BANK2:
        sys.exit("Please set KONTO_BANK2 in the SETUP block at the top of this script.")


def main():
    check_setup()

    new_parts = []
    if BANK1_FILE.is_file():
        new_parts.append(load_bank1(BANK1_FILE))
    if BANK2_FILE.is_file():
        new_parts.append(load_bank2(BANK2_FILE))

    if TRANSACTIONS_FILE.is_file():
        old = pd.read_csv(TRANSACTIONS_FILE, dtype={"Referenz": str, "Kontonummer/IBAN": str})
        old["Tag"] = pd.to_datetime(old["Tag"])
        # Rows saved before the Konto column existed all came from bank 1.
        if "Konto" not in old.columns:
            old["Konto"] = KONTO_BANK1
        old["Konto"] = old["Konto"].fillna(KONTO_BANK1)
        new_parts.append(old[COLUMNS])

    if not new_parts:
        sys.exit("No bank export and no transactions.csv found - nothing to do.")

    transactions = pd.concat(new_parts, ignore_index=True)
    before = len(transactions)
    transactions = transactions.drop_duplicates()
    transactions = transactions.sort_values("Tag", ascending=False)
    transactions.to_csv(TRANSACTIONS_FILE, index=False)
    print(f"{len(transactions)} transactions saved ({before - len(transactions)} duplicates removed).")


if __name__ == "__main__":
    main()
