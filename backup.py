"""Incremental backup: copy new and changed files from a source folder to a backup folder.

Before the first run, fill in the SETUP block below.

Usage:
    python3 backup.py --setA                   # each folder in SOURCE_A -> BACKUP_A/<folder name>
    python3 backup.py --setB                   # each folder in SOURCE_B -> BACKUP_B/<folder name>
    python3 backup.py FOLDER [FOLDER ...]      # each FOLDER -> BACKUP_B/<folder name>
    python3 backup.py --setA --setB FOLDER     # any combination
    add --dry-run to only show what would be copied
    add --show to list every copied file (by default only a summary is shown)

    In Windows (much faster for Windows drives) use "py backup.py ..." instead.
    Paths can be written as C:\\Users\\... or /mnt/c/Users/... on both systems.

Rules:
    - A file is copied if it is missing in the backup, or if its size differs,
      or if the source file is newer than the backup copy.
    - Changed files overwrite the old backup copy.
    - Nothing is ever deleted from the backup.

In WSL, Windows drives are under /mnt, e.g. D:\\Photos is /mnt/d/Photos.
"""

import argparse
import re
import shutil
import sys
from pathlib import Path

# ============================== SETUP ==============================
# Fill in the blanks before the first run. Either path style works on both
# systems: "/mnt/c/Users/me/Pictures" or r"C:\Users\me\Pictures"
# (for Windows-style paths, put an r in front of the quotes).

# Set A: a list of folders to back up with --setA, and the folder their
# backups go into. Each folder gets its own subfolder there, named after it:
#   SOURCE_A = ["/mnt/c/Users/me/Pictures", "/mnt/c/Users/me/Desktop/Photos"]
#   BACKUP_A = "/mnt/d/Backup/Photos"
#   -> /mnt/d/Backup/Photos/Pictures and /mnt/d/Backup/Photos/Photos
SOURCE_A = []
BACKUP_A = ""

# Set B: the same for --setB. BACKUP_B is also where folders given on the
# command line (python3 backup.py FOLDER) are backed up to.
#   SOURCE_B = ["/mnt/c/Users/me/Documents", "/home/me/projects"]
#   BACKUP_B = "/mnt/d/Backup/Data"
SOURCE_B = []
BACKUP_B = ""

# Only needed when running on Windows and backing up folders inside WSL:
# the name of your WSL distribution (run "wsl -l" in Windows to see it).
WSL_DISTRO = "Ubuntu"
# ===================================================================

# FAT32/exFAT drives (common on USB sticks and external disks) store file
# times with only 2-second precision, so allow a little slack when comparing.
TIME_TOLERANCE_SECONDS = 2

# Windows sometimes leaves these metadata files next to downloads; skip them.
SKIP_SUFFIXES = (":Zone.Identifier",)

# How often (in files) to update the progress line when the file list is hidden.
PROGRESS_EVERY = 200


def local_path(text: str) -> Path:
    """Accept a path in Windows style (C:\\Users, \\\\wsl.localhost\\Ubuntu\\home)
    or WSL style (/mnt/c/Users, /home/me) and convert it to the style of
    the system the script is running on."""
    text = str(text)
    if sys.platform == "win32":
        text = text.replace("\\", "/")
        match = re.match(r"/mnt/([a-z])(/.*)?$", text, re.IGNORECASE)
        if match:
            # Windows drive seen from WSL: /mnt/c/Users -> C:/Users
            drive, rest = match.group(1), match.group(2)
            text = f"{drive.upper()}:{rest or '/'}"
        elif text.startswith("/") and not text.startswith("//"):
            # Any other Linux path is inside WSL:
            # /home/me -> //wsl.localhost/Ubuntu/home/me
            text = f"//wsl.localhost/{WSL_DISTRO}{text}"
        elif re.fullmatch(r"[a-z]:", text, re.IGNORECASE):
            # A bare "D:" means the current folder on D:, so make it D:/ (the top).
            text += "/"
    else:
        match = re.match(r"([a-z]):[\\/]?(.*)$", text, re.IGNORECASE)
        if match:
            # Windows drive: C:\Users or C:/Users -> /mnt/c/Users
            drive, rest = match.group(1), match.group(2)
            text = f"/mnt/{drive.lower()}/" + rest.replace("\\", "/")
        match = re.match(r"[\\/]{2}wsl(?:\.localhost|\$)[\\/][^\\/]+(.*)$", text,
                         re.IGNORECASE)
        if match:
            # WSL seen from Windows: \\wsl.localhost\Ubuntu\home -> /home
            text = match.group(1).replace("\\", "/") or "/"
    return Path(text)

def needs_copy(source_file: Path, backup_file: Path) -> str | None:
    """Return the reason the file should be copied ('new' or 'changed'), or None."""
    if not backup_file.exists():
        return "new"

    src = source_file.stat()
    dst = backup_file.stat()
    if src.st_size != dst.st_size:
        return "changed"
    if src.st_mtime > dst.st_mtime + TIME_TOLERANCE_SECONDS:
        return "changed"
    return None


def format_size(num_bytes: int) -> str:
    """Turn a byte count into something readable like '3.4 MB'."""
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def run_backup(source: Path, backup: Path, dry_run: bool, show: bool) -> int:
    """Copy new/changed files from source to backup. Returns the number of errors."""
    copied = {"new": 0, "changed": 0}
    copied_bytes = 0
    unchanged = 0
    errors = 0
    checked = 0

    # rglob("*") walks through every file and subfolder of the source.
    for source_file in sorted(source.rglob("*")):
        if not source_file.is_file() or source_file.is_symlink():
            continue
        if source_file.name.endswith(SKIP_SUFFIXES):
            continue

        checked += 1
        if not show and checked % PROGRESS_EVERY == 0:
            # end="\r" moves the cursor back to the start of the line, so the
            # next progress update overwrites this one instead of adding a line.
            print(f"  checked {checked} files ...", end="\r", flush=True)

        # Same relative path inside the backup folder.
        relative_path = source_file.relative_to(source)
        backup_file = backup / relative_path

        try:
            reason = needs_copy(source_file, backup_file)
            if reason is None:
                unchanged += 1
                continue

            if show:
                print(f"[{reason:7}] {relative_path}")
            if not dry_run:
                backup_file.parent.mkdir(parents=True, exist_ok=True)
                # copy2 also copies the modification time, which the next
                # run needs to tell whether the file has changed.
                shutil.copy2(source_file, backup_file)

            copied[reason] += 1
            copied_bytes += source_file.stat().st_size
        except OSError as error:
            # Don't stop the whole backup because of one bad file.
            print(f"[ERROR  ] {relative_path}: {error}", file=sys.stderr)
            errors += 1

    if show:
        print()
    else:
        # Blank out the progress line before printing the summary.
        print(" " * 40, end="\r")
    verb = "Would copy" if dry_run else "Copied"
    print(f"{verb}: {copied['new']} new, {copied['changed']} changed "
          f"({format_size(copied_bytes)})")
    print(f"Unchanged: {unchanged}")
    if errors:
        print(f"Errors: {errors}")
    return errors


def backup_folder(source: Path, backup: Path, dry_run: bool, show: bool) -> int:
    """Check the paths, then back up one folder. Returns the number of errors."""
    source = source.resolve()
    backup = backup.resolve()

    print(f"Source: {source}")
    print(f"Backup: {backup}")

    # A problem with one folder is reported, but the other folders still run.
    if not source.is_dir():
        print(f"Source folder not found: {source}", file=sys.stderr)
        return 1
    if backup == source or source in backup.parents:
        print("The backup folder must not be the source folder or inside it.",
              file=sys.stderr)
        return 1
    if not backup.parent.is_dir():
        # Protects against typos and an unplugged backup drive.
        print(f"Backup location not found: {backup.parent} (is the drive connected?)",
              file=sys.stderr)
        return 1

    print()
    return run_backup(source, backup, dry_run, show)


def add_jobs(jobs: list, sources: list, backup_root: Path) -> None:
    """Add a (source, backup) pair to jobs for every source folder.
    Each folder gets its own subfolder in backup_root, named after the folder."""
    for folder in sources:
        # .name is the last part of the path, e.g. "Fotos" for /mnt/c/Fotos.
        folder = folder.resolve()
        jobs.append((folder, backup_root / folder.name))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Copy new and changed files to the backup drive.")
    parser.add_argument("--setA", action="store_true",
                        help=f"back up {', '.join(SOURCE_A) or 'SOURCE_A'} into {BACKUP_A or 'BACKUP_A'}")
    parser.add_argument("--setB", action="store_true",
                        help=f"back up {', '.join(SOURCE_B) or 'SOURCE_B'} into {BACKUP_B or 'BACKUP_B'}")
    # nargs="*" means: zero or more folders.
    parser.add_argument("folders", nargs="*", type=local_path,
                        help=f"other folders to back up, each into {BACKUP_B or 'BACKUP_B'}/<folder name>")
    parser.add_argument("--dry-run", action="store_true",
                        help="only show what would be copied, don't copy anything")
    parser.add_argument("--show", action="store_true",
                        help="list every copied file (default: only a summary)")
    args = parser.parse_args()

    # Collect every (source, backup) pair we were asked to do.
    # The standard folders are plain text, so convert each one with local_path().
    # Stop early with a clear message if the SETUP block was not filled in.
    if args.setA and not (SOURCE_A and BACKUP_A):
        parser.error("--setA needs SOURCE_A and BACKUP_A in the SETUP block")
    if args.setB and not (SOURCE_B and BACKUP_B):
        parser.error("--setB needs SOURCE_B and BACKUP_B in the SETUP block")
    if args.folders and not BACKUP_B:
        parser.error("backing up FOLDERs needs BACKUP_B in the SETUP block")

    jobs = []
    if args.setA:
        add_jobs(jobs, [local_path(folder) for folder in SOURCE_A], local_path(BACKUP_A))
    if args.setB:
        add_jobs(jobs, [local_path(folder) for folder in SOURCE_B], local_path(BACKUP_B))
    if args.folders:
        add_jobs(jobs, args.folders, local_path(BACKUP_B))

    if not jobs:
        parser.error("nothing to do - use --setA, --setB and/or give folders")

    # Two source folders with the same name would end up mixed in one backup folder.
    backups = [backup for source, backup in jobs]
    for backup in backups:
        if backups.count(backup) > 1:
            parser.error(f"two source folders would both be backed up into {backup} - "
                         "rename one of them")

    if args.dry_run:
        print("DRY RUN - nothing will be copied")

    errors = 0
    for source, backup in jobs:
        print()
        print("=" * 60)
        errors += backup_folder(source, backup, args.dry_run, args.show)

    print()
    print("=" * 60)
    print(f"Done: {len(jobs)} folder(s), {errors} error(s)")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
