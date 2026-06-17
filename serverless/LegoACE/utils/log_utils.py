"""Utilities for snapshotting source code into a training output directory."""

import os
import shutil
import subprocess


def get_file_list():
    """Return tracked + untracked-but-not-ignored files for the current git repo."""
    tracked = subprocess.check_output(["git", "ls-files"]).splitlines()
    untracked = subprocess.check_output(
        ["git", "ls-files", "--others", "--exclude-standard"]
    ).splitlines()
    return [b.decode() for b in set(tracked) | set(untracked)]


def save_code_snapshot(savedir):
    """Copy every git-tracked source file under ``savedir`` for reproducibility."""
    os.makedirs(savedir, exist_ok=True)
    for f in get_file_list():
        if not os.path.exists(f) or os.path.isdir(f):
            continue
        os.makedirs(os.path.join(savedir, os.path.dirname(f)), exist_ok=True)
        shutil.copyfile(f, os.path.join(savedir, f))
