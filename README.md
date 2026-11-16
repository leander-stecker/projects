# Personal finance & file tools

Small Python scripts for:

- **Bank analysis**: collect CSV exports from two German banks, merge them into
  one table, sort transactions into categories and plot spending over time.
- **Backup**: incremental backup of folders to an external drive (Windows / WSL).
- **Folder analyzer**: find out which folders use the most disk space.

## Requirements

- Python 3.10 or newer
- `pandas` and `matplotlib` for the bank scripts: `pip install pandas matplotlib`
- `backup.py` and `folder_analyzer.py` only need the standard library.

## Setup: fill in the blanks

Scripts with personal settings have a **SETUP block** at the top, marked with
`# ===== SETUP =====`. Fill in the blanks there before the first run. The
scripts stop with a clear message if a needed value is still empty.

| Script | Setting | What to put in |
|---|---|---|
| `update_transactions.py` | `DOWNLOADS_FOLDER` | Folder your browser saves bank exports to, e.g. `"/mnt/c/Users/<you>/Downloads"` (WSL) or `r"C:\Users\<you>\Downloads"` (Windows). |
| | `BANK1_PATTERN` | Filename pattern of bank 1's export, usually containing your account number, e.g. `"*1234567890*.CSV"`. `*` = any characters. Case-sensitive on Linux. `""` = not used. |
| | `BANK2_PATTERN` | Filename pattern of bank 2's export. Default `"*_Umsatzliste_Girokonto_*.csv"`. `""` = not used. |
| `update_banking.py` | `KONTO_BANK1`, `KONTO_BANK2` | A label per account, written into the `Konto` column (your IBAN, last digits, or a nickname like `"Giro"`). Choose once and keep it, otherwise old and new rows aren't recognized as duplicates. |
| `categorize.py` | `OWN_NAMES` | Your surname / family names, to recognize transfers between your own or family accounts, e.g. `[" mustermann "]`. |
| | `LANDLORDS` | Name(s) of your landlord or property management, e.g. `[" erika musterfrau "]`. |
| | `EMPLOYERS` | Your employer(s) or other income sources, e.g. `["muster gmbh"]`. |
| `backup.py` | `SOURCE_A`, `BACKUP_A` | List of folders backed up with `--setA`, and the folder their backups go into. |
| | `SOURCE_B`, `BACKUP_B` | The same for `--setB`. `BACKUP_B` is also used for folders given on the command line. |
| | `WSL_DISTRO` | Name of your WSL distribution (default `"Ubuntu"`, check with `wsl -l`). Only matters when running on Windows. |

Keywords in `categorize.py` are written in lowercase, with `ae/oe/ue/ss`
instead of umlauts. Spaces around a keyword mean "whole word only". The
`CATEGORIES` lists below the SETUP block are a generic starting point: add
the shops, restaurants and services you use. The docstring at the top of the
file explains the matching rules.

`label_other.py`, `plot_spending.py` and `folder_analyzer.py` have no
personal settings.

## Bank analysis

The bank scripts expect two export formats:

- **Bank 1**: `;`-separated, latin1, columns `Buchungstag`, `Valutadatum`,
  `Beguenstigter/Zahlungspflichtiger`, `Kundenreferenz (End-to-End)`, ...
- **Bank 2**: `DATE_Umsatzliste_Girokonto_IBAN.csv`, UTF-8, some metadata lines
  on top, columns `Buchungsdatum`, `Wertstellung`, `Status`, `Betrag (€)`, ...

Other banks need their own `load_bankX()` function in `update_banking.py`.

| Script | What it does |
|---|---|
| `update_transactions.py` | Finds the newest export of each bank in your Downloads folder, copies it next to the scripts, then runs `update_banking.py`. |
| `update_banking.py` | Converts both exports into one format and merges them into `transactions.csv` (duplicates removed). |
| `categorize.py` | Assigns a category to each transaction from keyword rules. `python categorize.py` categorizes `Empf.csv` (a table with an `Empfänger` column) and lists unmatched recipients. In your own code: `df["Category"] = categorize_df(df)`. |
| `label_other.py` | Goes through the recipients that ended up in "Other" and asks you for a category code. Saves your answers to `manual_categories.csv`, which `categorize.py` reads first. |
| `plot_spending.py` | `plot_rolling_all(df)` plots the rolling 28-day sum per category (spending and income). Use it from a notebook. |

Typical run:

```bash
python update_transactions.py
```

Then, in a notebook:

```python
import pandas as pd
from categorize import categorize_df
from plot_spending import plot_rolling_all

df = pd.read_csv("transactions.csv", parse_dates=["Tag"])
df["Category"] = categorize_df(df)
fig, axes = plot_rolling_all(df, start="2026-01-01")
```

## Backup

```bash
python3 backup.py --setA --dry-run   # show what would be copied
python3 backup.py --setA --setB      # back up both sets
python3 backup.py /path/to/folder    # back up one folder into BACKUP_B
```

New and changed files are copied; nothing is ever deleted from the backup.
On Windows drives, running it with Windows Python (`py backup.py ...`) is much
faster than from WSL.

## Folder analyzer

```bash
python folder_analyzer.py /path/to/folder
```

Shows the subfolders sorted by size; type a number to open one, `b` to go back.

## Privacy

Your bank exports and all generated CSV files (`transactions.csv`,
`manual_categories.csv`, ...) contain your financial data. The `.gitignore` in
this folder keeps every `*.csv` out of git. Don't remove it.
