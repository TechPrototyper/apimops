import os
import sys
from pathlib import Path
import subprocess
import yaml

def get_git_global_config(key):
    """
    Retrieves the global git configuration value for a given key.

    Args:
        key (str): The git config key to retrieve.

    Returns:
        str: The value of the git config key, or an empty string if not set.
    """
    result = subprocess.run(['git', 'config', '--global', key], capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else ""

def set_git_global_config(key, value):
    """
    Sets the global git configuration value for a given key.

    Args:
        key (str): The git config key to set.
        value (str): The value to set for the key.
    """
    subprocess.run(['git', 'config', '--global', key, value])

def unset_git_global_config(key):
    """
    Unsets the global git configuration value for a given key.

    Args:
        key (str): The git config key to unset.
    """
    subprocess.run(['git', 'config', '--global', '--unset', key])

def set_and_verify_git_identity_global(config_path):
    """
    Sets and verifies the global git identity (user.name, user.email, etc.) from a config YAML file.
    Restores previous values on exit.

    Args:
        config_path (str): Path to the YAML configuration file.

    Raises:
        SystemExit: If setting the git config fails.
    """
    import atexit
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    adminuser = config.get("adminuser", {})
    firstname = adminuser.get("firstname", "")
    lastname = adminuser.get("lastname", "")
    email = adminuser.get("email", "")
    git_username = adminuser.get("git_username", "")
    name = git_username or f"{firstname} {lastname}".strip()
    # Store old values for restoration
    keys = ["user.name", "user.email", "user.firstname", "user.lastname", "user.github"]
    old = {k: get_git_global_config(k) for k in keys}
    # Set new values
    set_git_global_config("user.name", name)
    set_git_global_config("user.email", email)
    set_git_global_config("user.firstname", firstname)
    set_git_global_config("user.lastname", lastname)
    set_git_global_config("user.github", git_username)
    # Verify
    failed = []
    expected = {
        "user.name": name,
        "user.email": email,
        "user.firstname": firstname,
        "user.lastname": lastname,
        "user.github": git_username
    }
    for k, v in expected.items():
        if get_git_global_config(k) != v:
            failed.append((k, v))
    if failed:
        print("\nFATAL: Failed to set global git config for:", failed)
        print("Please run the following commands manually:")
        for k, v in failed:
            print(f"git config --global {k} \"{v}\"")
        exit(1)
    # Register restore
    def restore():
        for k, v in old.items():
            if v:
                set_git_global_config(k, v)
            else:
                unset_git_global_config(k)
    atexit.register(restore)

def find_config_path(cli_arg=None, verbose=False):
    """
    Finds the path to the config.yaml file using several strategies.

    Args:
        cli_arg (str, optional): Path provided via --config argument.
        verbose (bool, optional): If True, prints the search process.

    Returns:
        str: Path to the found config.yaml file.

    Raises:
        SystemExit: If no config.yaml is found.
    """
    # 1. --config Argument (highest priority)
    if cli_arg and os.path.isfile(cli_arg):
        if verbose:
            print(f"Config file expected (from --config): {cli_arg}")
        return cli_arg

    # 2. APIMOPSCONFIG env var (directory, not file)
    env_dir = os.environ.get("APIMOPSCONFIG")
    if env_dir:
        candidate = os.path.join(env_dir, "config.yaml")
        if os.path.isfile(candidate):
            if verbose:
                print(f"Config file expected (from $APIMOPSCONFIG): {candidate}")
            return candidate

    # 3. Current working directory
    cwd_candidate = os.path.join(os.getcwd(), "config.yaml")
    if os.path.isfile(cwd_candidate):
        if verbose:
            print(f"Config file expected (from current working directory): {cwd_candidate}")
        return cwd_candidate

    # 4. Two directories above the script
    try:
        script_dir = Path(__file__).resolve().parent
        candidate = script_dir.parent.parent / "config.yaml"
        if candidate.is_file():
            if verbose:
                print(f"Config file expected (two directories above script): {candidate}")
            return str(candidate)
    except Exception:
        pass

    # 5. Error message
    print(
        "Error: Could not find config.yaml!\n"
        "Searched in the following order:\n"
        "  1. --config argument (if provided)\n"
        "  2. Directory specified by $APIMOPSCONFIG environment variable\n"
        "  3. Current working directory\n"
        "  4. Two directories above the script location\n"
        "\n"
        "Please provide a config.yaml in one of these locations or set $APIMOPSCONFIG.\n"
        "Usage: apimops-tool [--config /path/to/config.yaml] ...\n"
    )
    sys.exit(1)
