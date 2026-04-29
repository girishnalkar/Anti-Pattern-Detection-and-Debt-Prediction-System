import os
import shutil
import stat
import sys
import tempfile
import git  # From gitpython library

# Force stdout to use UTF-8 so emoji in print() don't crash on Windows cp1252
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def on_rm_error(func, path, exc_info):
    """
    Error handler for shutil.rmtree.
    If the error is due to an access error (read only file),
    it changes the file to be readable/writable and then attempts deletion.
    """
    os.chmod(path, stat.S_IWRITE)
    os.unlink(path)


def clone_repo(repo_url, target_dir=None):
    """
    Clones a GitHub repository to a local directory.
    If the directory exists, it cleans it up first.
    """
    if target_dir is None:
        target_dir = os.path.join(tempfile.gettempdir(), "anti_pattern_temp_repo")

    print(f"[*] Cloning repository: {repo_url}...")

    # 1. Clean up previous analysis if exists
    if os.path.exists(target_dir):
        try:
            shutil.rmtree(target_dir, onerror=on_rm_error)
        except Exception as e:
            print(f"[!] Could not delete old folder: {e}")
            return None

    # 2. Clone the repo
    try:
        git.Repo.clone_from(repo_url, target_dir, depth=1)  # shallow clone: latest commit only
        print("[+] Repository cloned successfully!")
        return target_dir
    except Exception as e:
        print(f"[-] Error cloning repository: {e}")
        return None