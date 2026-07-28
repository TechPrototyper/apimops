import os
import sys
import yaml
import subprocess
import getpass
import platform
import argparse
from github import Github
from github.Repository import Repository
from azure.identity import ClientSecretCredential
from azure.mgmt.apimanagement import ApiManagementClient
import threading
import time
from colorama import init, Fore, Style

# --- PyInstaller/Standalone Compatibility ---
if getattr(sys, "frozen", False):
    _meipass = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(sys.executable)))
    if _meipass not in sys.path:
        sys.path.insert(0, _meipass)
    _setup_base = _meipass
else:
    _setup_base = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    _common_dir = os.path.join(_setup_base, "scripts", "common")
    if _common_dir not in sys.path:
        sys.path.insert(0, _common_dir)

try:
    from apimops_utils import find_config_path
except ImportError:
    from scripts.common.apimops_utils import find_config_path

# Constants
VERSION = "1.0.0"

# Define script arguments
parser = argparse.ArgumentParser(description="Setup script for apimops.", add_help=True)
parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output")
parser.add_argument("--debug!", dest="debug", action="store_true", help=argparse.SUPPRESS)
args = parser.parse_args()

verbose = args.verbose
debug = args.debug

# Initialize Colorama
init(autoreset=True)

def log(message):
    """Logging function for verbose output."""
    if verbose:
        print(message)

def warning(message):
    """Print a warning message in yellow."""
    print(Fore.YELLOW + message)

class Spinner:
    """A class to display a spinning cursor as a progress indicator."""
    
    busy = False
    delay = 0.1

    @staticmethod
    def spinning_cursor():
        while 1:
            for cursor in "|/-\\":
                yield cursor

    def __init__(self, delay=None):
        self.spinner_generator = self.spinning_cursor()
        if delay and float(delay):
            self.delay = delay

    def spinner_task(self):
        while self.busy:
            sys.stdout.write(next(self.spinner_generator))
            sys.stdout.flush()
            time.sleep(self.delay)
            sys.stdout.write("\b")
            sys.stdout.flush()

    def __enter__(self):
        self.busy = True
        threading.Thread(target=self.spinner_task).start()

    def __exit__(self, exception, value, tb):
        self.busy = False
        time.sleep(self.delay)
        if exception is not None:
            return False

class Task(threading.Thread):
    def __init__(self, target):
        super().__init__(target=self.run_with_exception_handling)
        self.target = target
        self.exception = None
        self.result = None

    def run_with_exception_handling(self):
        try:
            self.result = self.target()
        except Exception as e:
            self.exception = e

def run_with_spinner(task, message, final_message=None):
    """Run a task with a spinner."""
    spin = Spinner()
    sys.stdout.write(message + " ")
    sys.stdout.flush()
    task.start()
    while task.is_alive():
        sys.stdout.write(next(spin.spinner_generator))
        sys.stdout.flush()
        time.sleep(0.1)
        sys.stdout.write("\b")
        sys.stdout.flush()
    task.join()
    if task.exception:
        sys.stdout.write(Fore.RED + " --> Failed ✘\n")
        print(Fore.RED + str(task.exception))
    else:
        if final_message:
            sys.stdout.write(Fore.GREEN + final_message + "\n")
        else:
            sys.stdout.write(Fore.GREEN + " --> Ok ✔\n")
    return task.result

def load_config():
    config_path = find_config_path(
        cli_arg=None,  # setup.py currently does not support --config, could be extended
        verbose=globals().get('verbose', False)
    )
    with open(config_path, "r") as file:
        return yaml.safe_load(file)

def check_minimum_requirements(config):
    """Check if the minimum required fields are present in the configuration."""
    required_fields = [
        "github_solution",
        "github_data",
        "azure_default"
    ]
    missing_fields = []
    for field in required_fields:
        if field not in config["general"]:
            missing_fields.append(field)
    return missing_fields

def prompt_for_missing_fields(missing_fields):
    """Prompt the user for missing configuration fields."""
    for field in missing_fields:
        if field == "github_solution":
            log("Prompting for Github Solution Repo Name")
            repo = input("Enter Github Solution Repo Name: ")
            log("Prompting for Github Solution Repo URL")
            url = input("Enter Github Solution Repo URL: ")
            log("Prompting for Github Solution Token")
            token = getpass.getpass("Enter Github Solution Token: ")
            config["general"]["github_solution"] = {"repo": repo, "url": url, "token": token}
        elif field == "github_data":
            log("Prompting for Github Data Repo Name")
            repo = input("Enter Github Data Repo Name: ")
            log("Prompting for Github Data Repo URL")
            url = input("Enter Github Data Repo URL: ")
            log("Prompting for Github Data Token")
            token = getpass.getpass("Enter Github Data Token: ")
            config["general"]["github_data"] = {"repo": repo, "url": url, "token": token}
        elif field == "azure_default":
            log("Prompting for Azure Tenant ID")
            tenant_id = input("Enter Azure Tenant ID: ")
            log("Prompting for Azure Subscription ID")
            subscription_id = input("Enter Azure Subscription ID: ")
            log("Prompting for Azure Resource Group")
            resource_group = input("Enter Azure Resource Group: ")
            log("Prompting for Azure Service Principal Client ID")
            sp_client_id = input("Enter Azure Service Principal Client ID: ")
            log("Prompting for Azure Service Principal Client Secret")
            sp_client_secret = getpass.getpass("Enter Azure Service Principal Client Secret: ")
            config["general"]["azure_default"] = {
                "tenant_id": tenant_id,
                "subscription_id": subscription_id,
                "resource_group": resource_group,
                "sp_client_id": sp_client_id,
                "sp_client_secret": sp_client_secret
            }

def create_virtual_envs():
    """Create virtual environments for the specified script directories."""
    script_dirs = ["asst", "transfer"]
    for script_dir in script_dirs:
        task = Task(target=lambda: create_virtual_env(script_dir))
        run_with_spinner(task, f"Creating virtual environment for {script_dir}")

def create_virtual_env(script_dir):
    """Create a virtual environment for a specified script directory."""
    venv_path = os.path.join("scripts", script_dir, ".venv")
    requirements_path = os.path.join("scripts", script_dir, "requirements.txt")
    if not os.path.exists(venv_path):
        subprocess.run(["python3.12", "-m", "venv", venv_path])
        subprocess.run([os.path.join(venv_path, "bin", "pip"), "install", "--upgrade", "pip"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if os.path.exists(requirements_path):
        subprocess.run([os.path.join(venv_path, "bin", "pip"), "install", "-r", requirements_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def verify_azure_login(azure_config):
    """Verify Azure login using the provided credentials."""
    try:
        credentials = ClientSecretCredential(
            tenant_id=azure_config["tenant_id"],
            client_id=azure_config["sp_client_id"],
            client_secret=azure_config["sp_client_secret"]
        )
        client = ApiManagementClient(credentials, azure_config["subscription_id"])
        # Test call to verify credentials
        client.api_management_service.list()
    except Exception as e:
        raise Exception(f"Azure login failed: {e}")

def connect_to_github(github_config):
    """Connect to Github, supporting GitHub Enterprise and automatic repository creation."""
    from urllib.parse import urlparse
    parsed_url = urlparse(github_config["url"])
    path_parts = parsed_url.path.lstrip("/").rstrip(".git").split("/")
    if len(path_parts) != 2:
        raise Exception(f"Invalid GitHub URL: {github_config['url']}")
    owner, repo_name = path_parts

    token = github_config["token"]
    hostname = parsed_url.hostname or "github.com"

    try:
        if hostname.lower() in ("github.com", "www.github.com"):
            g = Github(token)
        else:
            base_url = f"https://{hostname}/api/v3"
            g = Github(base_url=base_url, login_or_token=token)

        # Try retrieving existing repo
        try:
            repo = g.get_repo(f"{owner}/{repo_name}")
        except Exception:
            log(f"Repository {owner}/{repo_name} not found. Attempting auto-creation...")
            user = g.get_user()
            if user.login.lower() == owner.lower():
                repo = user.create_repo(repo_name, private=True, auto_init=True, description="apimops repository")
            else:
                org = g.get_organization(owner)
                repo = org.create_repo(repo_name, private=True, auto_init=True, description="apimops repository")
            time.sleep(2)  # Allow GitHub backend to finalize repo creation

        # Verify main branch exists or initialize it
        try:
            repo.get_branch("main")
        except Exception:
            try:
                repo.create_file("README.md", "Initial commit for apimops", f"# {repo_name}\n\nManaged by apimops.")
                time.sleep(2)
            except Exception as init_err:
                log(f"Branch check notice: {init_err}")

        return repo
    except Exception as e:
        raise Exception(f"GitHub connection/creation failed for {github_config['url']}: {e}")

def check_github_branch(repo, branch_name):
    """Check if a branch exists in the Github repository."""
    try:
        repo.get_branch(branch_name)
    except Exception:
        create_branch(repo, branch_name)

def create_branch(repo, branch_name):
    """Create a branch in the Github repository."""
    try:
        master_ref = repo.get_git_ref("heads/main")
        repo.create_git_ref(ref=f"refs/heads/{branch_name}", sha=master_ref.object.sha)
        branch_exists = False
        for _ in range(5):  # Try 5 times
            try:
                repo.get_branch(branch_name)
                branch_exists = True
                break
            except:
                time.sleep(1)  # Wait 1 second and try again
        if not branch_exists:
            raise Exception(f"Branch {branch_name} was not found after creation.")
    except Exception as e:
        raise Exception(f"Error creating branch {branch_name}: {e}")

def create_or_update_secret(repo, secret_name, secret_value, environment=None):
    """Create or update a secret in a GitHub repository or environment."""
    try:
        if environment:
            repo.create_secret(secret_name, secret_value)  # Environment not supported in PyGithub, handle differently if required
        else:
            repo.create_secret(secret_name, secret_value)
    except Exception as e:
        if "Already exists" in str(e):
            try:
                if environment:
                    repo.update_secret(secret_name, secret_value)  # Environment not supported in PyGithub, handle differently if required
                else:
                    repo.update_secret(secret_name, secret_value)
            except Exception as update_error:
                raise Exception(f"Failed to update secret {secret_name}: {update_error}")
        else:
            raise Exception(f"Failed to create secret {secret_name}: {e}")

def create_or_update_variable(repo, var_name, var_value, environment=None):
    """Create or update a variable in a GitHub repository or environment."""
    try:
        if environment:
            existing_variable = repo.get_environment_variable(environment, var_name)
        else:
            existing_variable = repo.get_variable(var_name)

        if existing_variable:
            if environment:
                repo.delete_environment_variable(environment, var_name)
                repo.create_environment_variable(environment, var_name, var_value)
            else:
                repo.delete_variable(var_name)
                repo.create_variable(var_name, var_value)
        else:
            if environment:
                repo.create_environment_variable(environment, var_name, var_value)
            else:
                repo.create_variable(var_name, var_value)
    except Exception as e:
        raise Exception(f"Failed to create or update variable {var_name}: {e}")

def create_or_get_environment(repo, environment_name):
    """Create or get a GitHub environment."""
    try:
        env = repo.get_environment(environment_name)
        return env
    except Exception:
        try:
            repo.create_environment(environment_name)
            env = repo.get_environment(environment_name)
            return env
        except Exception as e:
            sys.stdout.write(Fore.RED + "Failed ✘\n")
            print(Fore.RED + str(e))
            print(Fore.YELLOW + f"Warning: Action to create Environment {environment_name} returned an error. We still believe the environment was set up and will check on that:")
            print(f"Verifying if environment {environment_name} exists: ", end="")
            try:
                with Spinner():
                    env = repo.get_environment(environment_name)
                sys.stdout.write(Fore.GREEN + " --> Exists after failure ✔\n")
                return env
            except Exception as final_verification_error:
                sys.stdout.write(Fore.RED + " --> Does not exist after failure ✘\n")
                print(Fore.RED + str(final_verification_error))
                return None

def set_git_identity_from_config(config_path, repo_path=None):
    """Set git user.name and user.email from config.yaml adminuser section."""
    import subprocess
    import yaml
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    adminuser = config.get("adminuser", {})
    name = adminuser.get("git_username") or (
        (adminuser.get("firstname") or "") + " " + (adminuser.get("lastname") or "")
    ).strip()
    email = adminuser.get("email")
    if name:
        subprocess.run(["git", "config", "--global", "user.name", name], cwd=repo_path)
    if email:
        subprocess.run(["git", "config", "--global", "user.email", email], cwd=repo_path)

def main():
    """Main function to execute the setup process."""
    print(f"apimops setup script version {VERSION}")
    if debug:
        warning("WARNING: The argument --debug! has been used; it will disclose secrets to stdout. Do you really want to continue? [y,N]: ")
        confirm = input().strip().lower()
        if confirm not in ("y", "yes"):
            print("Aborting.")
            sys.exit(1)

    config = load_config()
    # Set git identity from config.yaml adminuser section (explicit, only source of truth)
    config_path = find_config_path()
    set_git_identity_from_config(config_path)
    missing_fields = check_minimum_requirements(config)
    
    if missing_fields:
        print(f"Missing required fields: {', '.join(missing_fields)}")
        prompt_for_missing_fields(missing_fields)
    
    create_virtual_envs()
    
    for name, secret_provider in config.get("secret_providers", {}).items():
        task = Task(target=lambda: verify_azure_login(secret_provider))
        run_with_spinner(task, f"Secret Provider ({name}): {secret_provider['type']} Connectivity")

    azure_config = config["general"]["azure_default"]
    task = Task(target=lambda: verify_azure_login(azure_config))
    run_with_spinner(task, "Azure Connectivity")
    # BREAKPOINT: Hier nach Azure Connectivity single-steppen
    github_solution = config["general"]["github_solution"]
    repo_solution = connect_to_github(github_solution)
    
    github_data = config["general"]["github_data"]
    repo_data = connect_to_github(github_data)
    
    # Set GitHub secrets and variables
    for secret_name, secret_value in [
        ("AZURE_CLIENT_ID", azure_config["sp_client_id"]),
        ("AZURE_CLIENT_SECRET", azure_config["sp_client_secret"]),
        ("AZURE_RESOURCE_GROUP_NAME", azure_config["resource_group"]),
        ("AZURE_SUBSCRIPTION_ID", azure_config["subscription_id"]),
        ("AZURE_TENANT_ID", azure_config["tenant_id"]),
        ("GH_APIMOPS_REPO", github_solution["repo"]),
        ("GH_APIMOPS_URL", github_solution["url"]),
        ("GH_APIMOPS_TOKEN", github_solution["token"]),
        ("GH_APIMDATA_REPO", github_data["repo"]),
        ("GH_APIMDATA_URL", github_data["url"]),
        ("GH_APIMDATA_TOKEN", github_data["token"]),
        ("AI_API_KEY", config["general"].get("ai_assistant", {}).get("api_key", "")),
    ]:
        task = Task(target=lambda: create_or_update_secret(repo_solution, secret_name, secret_value))
        run_with_spinner(task, f"Setting GitHub secret {secret_name}")
    
    for var_name, var_value in [
        ("APIOPS_RELEASE_VERSION", config["general"]["apiops"]["release_version"]),
        ("API_SPECIFICATION_FORMAT", config["general"]["apiops"]["specification_format"]),
        ("AI_ENDPOINT", config["general"].get("ai_assistant", {}).get("endpoint", "")),
        ("AI_MODEL", config["general"].get("ai_assistant", {}).get("model", "")),
    ]:
        task = Task(target=lambda: create_or_update_variable(repo_solution, var_name, var_value))
        run_with_spinner(task, f"Setting GitHub variable {var_name}")

    
    for service_name, service_config in config["apim_services"].items():
        print(f"\nService: {service_name}")
        print("=" * len(f"Service: {service_name}"))
        
        azure_service_config = service_config.get("azure", azure_config)
        azure_service_config["service_name"] = service_name  # Ensure the service name is set
        task = Task(target=lambda: verify_azure_login(azure_service_config))
        run_with_spinner(task, f"Azure Connectivity for {service_name}")
        
        github_service_config = service_config.get("github", github_data)
        repo_service = connect_to_github(github_service_config)
        
        task = Task(target=lambda: check_github_branch(repo_service, service_name))
        run_with_spinner(task, f"Checking if branch {service_name} exists")
        
        # Create or get environment
        task = Task(target=lambda: create_or_get_environment(repo_solution, service_name))
        env = run_with_spinner(task, f"Checking environment {service_name}")

        if not env:
            continue

        # Set environment-specific secrets and variables for the service
        if "azure" in service_config or "github" in service_config:
            for secret_name, secret_value in [
                ("AZURE_CLIENT_ID", azure_service_config.get("sp_client_id", azure_config["sp_client_id"])),
                ("AZURE_CLIENT_SECRET", azure_service_config.get("sp_client_secret", azure_config["sp_client_secret"])),
                ("AZURE_RESOURCE_GROUP_NAME", azure_service_config.get("resource_group", azure_config["resource_group"])),
                ("AZURE_SUBSCRIPTION_ID", azure_service_config.get("subscription_id", azure_config["subscription_id"])),
                ("AZURE_TENANT_ID", azure_service_config.get("tenant_id", azure_config["tenant_id"])),
            ]:
                task = Task(target=lambda: create_or_update_secret(repo_service, secret_name, secret_value, environment=service_name))
                run_with_spinner(task, f"Setting GitHub secret {secret_name} for {service_name}")

            for var_name, var_value in [
                ("GH_APIMOPS_REPO", github_service_config.get("repo", github_solution["repo"])),
                ("GH_APIMOPS_URL", github_service_config.get("url", github_solution["url"])),
                ("GH_APIMOPS_TOKEN", github_service_config.get("token", github_solution["token"])),
            ]:
                task = Task(target=lambda: create_or_update_variable(repo_service, var_name, var_value, environment=service_name))
                run_with_spinner(task, f"Setting GitHub variable {var_name} for {service_name}")
    
    print("\nSetup completed. Summary:")
    print(f"{len(config['apim_services'])} API-Management nodes configured to run in apimops:")

    header = ["Service Name", "Tenant", "Subscription", "Resource Group", "Description", "Repo-Url"]
    table = []
    for service_name, service_config in config["apim_services"].items():
        azure_service_config = service_config.get("azure", azure_config)
        github_service_config = service_config.get("github", github_data)
        table.append([
            service_name,
            azure_service_config["tenant_id"],
            azure_service_config["subscription_id"],
            azure_service_config["resource_group"],
            service_config.get("name", ""),
            github_service_config["url"]
        ])

    # Calculate the maximum width for each column
    col_widths = [max(len(str(item)) for item in col) for col in zip(header, *table)]

    # Create the formatted table
    def format_row(row):
        return "  ".join(f"{item:<{col_widths[i]}}" for i, item in enumerate(row))

    # Print the table
    print(format_row(header))
    print(format_row(["-" * width for width in col_widths]))
    for row in table:
        print(format_row(row))

if __name__ == "__main__":
    """
    Entry point for the script. Handles initialization and executes the main function.
    """
    try:
        main()
    except Exception as e:
        print(f"\nError: {e}")
