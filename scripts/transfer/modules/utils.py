import os
import shutil
import stat
import sys
import threading
import time
from pathlib import Path


def spinner(label="Working..."):
    """Start a spinner thread. Returns (done_event, thread)."""
    done_event = threading.Event()

    def _run():
        chars = "|/-\\"
        idx = 0
        while not done_event.is_set():
            print(f"\r{label} {chars[idx % len(chars)]}", end="", flush=True)
            idx += 1
            time.sleep(0.1)
        print("\r", end="", flush=True)

    thread = threading.Thread(target=_run)
    thread.start()
    return done_event, thread


def exit_with_error(message: str):
    print(f"Error: {message}")
    sys.exit(1)


def on_rm_error(func, path, exc_info):
    if not os.access(path, os.W_OK):
        os.chmod(path, stat.S_IWUSR)
        func(path)
    else:
        print(f"Error deleting {path}: {exc_info[1]}")


def prompt_and_cleanup_temp_dirs(source_repo_dir, temp_data_repo_dir):
    dirs_to_check = [source_repo_dir, temp_data_repo_dir]
    existing = [d for d in dirs_to_check if os.path.exists(d)]
    if existing:
        print(f"Warning: The following temp directories already exist: {', '.join(existing)}")
        resp = input("Delete these temp directories? [Y/n]: ").strip().lower()
        if resp in ("n", "no"):
            print("Warning: Temp directories were NOT purged. Proceeding, but creation may fail if directories already exist.")
            return False
        for directory in existing:
            try:
                shutil.rmtree(directory)
                print(f"Info: Deleted temp directory {directory}")
            except Exception as e:
                print(f"Error deleting {directory}: {e}")
        print("Info: Temp directories have been purged.")
    return True


def cleanup_repo_directories(base_dir, verbose=False):
    os.chdir(base_dir)
    working_dir = Path(base_dir)
    for directory in ("source_repo", "temp_data_repo"):
        path = Path(working_dir / directory)
        try:
            if path.exists() and path.is_dir():
                shutil.rmtree(path, onerror=on_rm_error)
                if verbose:
                    print(f"{path} successfully deleted.")
            elif verbose:
                print(f"{path} does not exist or is not a directory.")
        except Exception as e:
            print(f"Error deleting {path}: {e}")

