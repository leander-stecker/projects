"""
update_transactions.py
-----------------------
Finds the most recent export of each bank in your Downloads folder, copies
them into the project folder under stable names, and then runs
update_banking.py.

Before the first run, fill in the SETUP block below.
"""

from pathlib import Path
import shutil
import subprocess
import sys

# ============================== SETUP ==============================
# Fill in the blanks ("") before the first run. Nothing else in this
# file needs to be changed.

# Folder your browser saves the bank exports to.
#   WSL (Linux inside Windows):  "/mnt/c/Users/<your Windows user name>/Downloads"
#   Windows:                     r"C:\Users\<your user name>\Downloads"
#   macOS / Linux:               "/home/<your user name>/Downloads"
DOWNLOADS_FOLDER = ""

# Filename pattern of bank 1's export. "*" is a wildcard for "any characters".
# Use the distinctive part of the filename, usually your account number:
#   "*1234567890*.CSV"  -> files containing that account number
#   "Umsatz*.csv"       -> files starting with "Umsatz"
# On Linux/WSL the pattern is case-sensitive (".CSV" is not ".csv").
# Leave it "" if you don't use bank 1.
BANK1_PATTERN = ""

# Filename pattern of bank 2's export. The default matches files named like
# "DATE_Umsatzliste_Girokonto_IBAN.csv". If you have several such accounts,
# replace the last * with your IBAN. Leave it "" if you don't use bank 2.
BANK2_PATTERN = "*_Umsatzliste_Girokonto_*.csv"
# ===================================================================

SCRIPT_DIR = Path(__file__).parent

# One entry per bank: (name, filename pattern, where the copy goes).
# The target names must match BANK1_FILE / BANK2_FILE in update_banking.py.
EXPORTS = [
    ("Bank 1", BANK1_PATTERN, SCRIPT_DIR / "umsatz_neu.CSV"),
    ("Bank 2", BANK2_PATTERN, SCRIPT_DIR / "umsatz_neu_bank2.csv"),
]

ANALYZER = SCRIPT_DIR / "update_banking.py"


# ---------- STEP 1: FIND THE NEWEST MATCHING FILE ----------

def find_newest_export(folder, pattern):
    """Return the most recently modified file in `folder` matching `pattern`."""
    if not folder.is_dir():
        raise FileNotFoundError(f"Downloads folder not found: {folder}")

    # glob() returns every path matching the pattern (a generator),
    # list() turns it into an actual list we can inspect.
    candidates = list(folder.glob(pattern))

    if not candidates:
        raise FileNotFoundError(
            f"No file matching '{pattern}' found in {folder}"
        )

    # st_mtime is the file's "last modified" timestamp. max() with a key
    # picks the file with the largest (= most recent) timestamp.
    # This is the same key=... idea as sorted(key=...).
    newest = max(candidates, key=lambda p: p.stat().st_mtime)
    return newest


# ---------- STEP 2: COPY IT INTO THE PROJECT ----------

def copy_export(source, target):
    """Copy the export into the project folder under a stable name."""
    # copy2 preserves the original timestamps; plain copy() would not.
    shutil.copy2(source, target)
    return target


# ---------- STEP 3: RUN THE ANALYZER ----------

def run_analyzer(script):
    """Run the analyzer script as a separate process."""
    if not script.is_file():
        raise FileNotFoundError(f"Analyzer script not found: {script}")

    # sys.executable is the path to the Python running THIS script,
    # so the analyzer runs in the same environment (same pandas install).
    result = subprocess.run([sys.executable, str(script)])
    return result.returncode


# ---------- MAIN ----------

def fetch_export(downloads, name, pattern, target):
    """Find, check and copy one bank's export. Returns True if copied."""
    import datetime

    if not pattern:
        print(f"[{name}] Skipped: no filename pattern set in the SETUP block.\n")
        return False

    try:
        newest = find_newest_export(downloads, pattern)
    except FileNotFoundError as e:
        print(f"[{name}] Skipped: {e}\n")
        return False

    # Show what was picked and how old it is, so a stale file is obvious.
    modified = datetime.datetime.fromtimestamp(newest.stat().st_mtime)
    print(f"[{name}] Found:    {newest.name}")
    print(f"[{name}] Modified: {modified:%Y-%m-%d %H:%M}")

    # Safety check: refuse silently using an obviously old file.
    age_days = (datetime.datetime.now() - modified).days
    if age_days > 7:
        answer = input(f"[{name}] That file is {age_days} days old. Use it anyway? [y/N] ")
        if answer.strip().lower() != "y":
            print(f"[{name}] Skipped.\n")
            return False

    copy_export(newest, target)
    print(f"[{name}] Copied to {target}\n")
    return True


def main():
    if not DOWNLOADS_FOLDER:
        print("Please set DOWNLOADS_FOLDER in the SETUP block at the top of this script.")
        return 1
    downloads = Path(DOWNLOADS_FOLDER)

    copied = [fetch_export(downloads, name, pattern, target)
              for name, pattern, target in EXPORTS]

    if not any(copied):
        print("No new exports copied. Nothing to do.")
        return 1

    try:
        return run_analyzer(ANALYZER)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
