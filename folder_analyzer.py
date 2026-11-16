"""
Folder Analyzer
---------------
Shows the subfolders of a folder and how much space each one uses.
You can then step into a subfolder to see its contents, and go back up again.

Usage:
    python folder_analyzer.py <path>

Example:
    python folder_analyzer.py /mnt/c/Users/me/Documents
"""

import os
import sys
import time

# Remember sizes we already calculated, so going back and forth is fast.
size_cache = {}

# How many files we've looked at so far (for the progress display).
files_scanned = 0


def show_progress():
    """Overwrite the same line with the current file count."""
    print(f"\r  Scanned {files_scanned:,} files...", end="", flush=True)


def format_size(num_bytes):
    """Turn a number of bytes into something readable, like '4.2 MB'."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if num_bytes < 1024:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024
    return f"{num_bytes:.1f} PB"


def folder_size(path):
    """Add up the size of every file inside a folder (including all subfolders)."""
    global files_scanned
    if path in size_cache:
        return size_cache[path]

    total = 0
    try:
        with os.scandir(path) as entries:
            for entry in entries:
                try:
                    # follow_symlinks=False: don't count linked folders twice
                    if entry.is_file(follow_symlinks=False):
                        total += entry.stat(follow_symlinks=False).st_size
                        files_scanned += 1
                        if files_scanned % 500 == 0:
                            show_progress()
                    elif entry.is_dir(follow_symlinks=False):
                        total += folder_size(entry.path)
                except OSError:
                    pass  # file vanished or can't be read: skip it
    except PermissionError:
        pass  # no access to this folder: count it as 0

    size_cache[path] = total
    return total


def list_contents(path):
    """Return (list of (name, size) for subfolders, total size of loose files)."""
    subfolders = []
    files_total = 0
    try:
        with os.scandir(path) as entries:
            for entry in entries:
                try:
                    if entry.is_dir(follow_symlinks=False):
                        subfolders.append((entry.name, folder_size(entry.path)))
                    elif entry.is_file(follow_symlinks=False):
                        files_total += entry.stat(follow_symlinks=False).st_size
                except OSError:
                    pass
    except PermissionError:
        print("  (No permission to read this folder)")

    # Biggest folders first
    subfolders.sort(key=lambda item: item[1], reverse=True)
    return subfolders, files_total


def show_folder(path, subfolders, files_total):
    """Print a table of the subfolders and their sizes."""
    total = sum(size for _, size in subfolders) + files_total

    print()
    print("=" * 70)
    print(f"Folder: {path}")
    print(f"Total size: {format_size(total)}")
    print("=" * 70)

    if not subfolders:
        print("  (no subfolders)")

    for number, (name, size) in enumerate(subfolders, start=1):
        percent = (size / total * 100) if total else 0
        bar = "#" * int(percent / 5)  # one '#' per 5 %
        print(f"  [{number:>3}] {format_size(size):>10}  {percent:5.1f}%  {bar:<20} {name}")

    if files_total:
        print(f"        {format_size(files_total):>10}  (files directly in this folder)")
    print()


def main():
    if len(sys.argv) != 2:
        print("Usage: python folder_analyzer.py <path>")
        sys.exit(1)

    start_path = os.path.abspath(sys.argv[1])
    if not os.path.isdir(start_path):
        print(f"Error: '{start_path}' is not a folder.")
        sys.exit(1)

    print("Calculating sizes, this can take a moment for big folders...")
    current = start_path

    while True:
        start_count = files_scanned
        start_time = time.time()
        subfolders, files_total = list_contents(current)
        if files_scanned > start_count:  # only report when something new was scanned
            show_progress()
            print(f" done in {time.time() - start_time:.1f} s")
        show_folder(current, subfolders, files_total)

        print("Type a number to open that folder, 'b' to go back, 'q' to quit.")
        choice = input("> ").strip().lower()

        if choice == "q":
            break
        elif choice == "b":
            if current == start_path:
                print("You're already at the starting folder.")
            else:
                current = os.path.dirname(current)
        elif choice.isdigit() and 1 <= int(choice) <= len(subfolders):
            name = subfolders[int(choice) - 1][0]
            current = os.path.join(current, name)
        else:
            print("Invalid input, try again.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:  # Ctrl+C quits cleanly
        print("\nBye!")
