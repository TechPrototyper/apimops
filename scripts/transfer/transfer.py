import asyncio
import logging
import os
import re
import sys

import yaml

# --- PyInstaller/Standalone Compatibility ---
# Resolve paths so imports work both from source tree and from PyInstaller --onefile.
if getattr(sys, "frozen", False):
    # Running as PyInstaller binary: files extracted to sys._MEIPASS
    _base = sys._MEIPASS
else:
    # Running as script: __file__ points to scripts/transfer/transfer.py
    _base = os.path.dirname(os.path.abspath(__file__))

# scripts/common contains apimops_utils.py
_common = os.path.join(os.path.dirname(_base), "common")
if _common not in sys.path:
    sys.path.insert(0, _common)

# scripts/transfer contains modules/ and v6_adapter.py
_transfer_dir = _base
if _transfer_dir not in sys.path:
    sys.path.insert(0, _transfer_dir)

from apimops_utils import find_config_path, set_and_verify_git_identity_global
from modules import artifacts, config as transfer_config, git_ops, github_api, workflow
from modules.cli import ArgumentParseError, parse_arguments
from modules.utils import cleanup_repo_directories, exit_with_error, on_rm_error, prompt_and_cleanup_temp_dirs


def print_summary(args, source_config: dict, destination_config: dict):
    source_rg = source_config.get("resource_group", "Unknown")
    source_repo = source_config["github"]["repo"]
    source_branch = args.source
    destination_rg = destination_config.get("resource_group", "Unknown")
    destination_repo = destination_config["github"]["repo"]
    destination_branch = args.destination

    artifact_labels = []
    if args.api:
        artifact_labels.append(f"API {args.api}")
    if args.apis:
        artifact_labels.append(f"APIs {args.apis}")
    if args.backends:
        artifact_labels.append(f"Backends {args.backends}")
    if args.diagnostics:
        artifact_labels.append(f"Diagnostics {args.diagnostics}")
    if args.loggers:
        artifact_labels.append(f"Loggers {args.loggers}")
    if args.namedvalues:
        artifact_labels.append(f"NamedValues {args.namedvalues}")
    if args.products:
        artifact_labels.append(f"Products {args.products}")
    if args.subscriptions:
        artifact_labels.append(f"Subscriptions {args.subscriptions}")
    if args.tags:
        artifact_labels.append(f"Tags {args.tags}")
    if args.versionsets:
        artifact_labels.append(f"VersionSets {args.versionsets}")

    artifacts_str = ", ".join(artifact_labels)
    if source_repo == destination_repo and source_rg == destination_rg:
        print(
            f"Transferring {artifacts_str} from service {args.source} in Branch {source_branch} "
            f"to {args.destination} in Branch {destination_branch}."
        )
    else:
        print(
            f"Transferring {artifacts_str} from service {args.source} on Azure in Resource Group {source_rg} "
            f"stored in Github Repo {source_repo} in Branch {source_branch} to {args.destination} on Azure "
            f"in Resource Group {destination_rg} stored in Github Repo {destination_repo} in Branch {destination_branch}."
        )


class APIMigrationTool:
    def __init__(self, args):
        self.args = args
        self.logger = logging.getLogger("transfer.apim_migration")
        # Resolve base_dir (project root) — use directory containing config.yaml
        # so temp dirs (source_repo, temp_data_repo) are created next to config.yaml
        config_path = find_config_path(cli_arg=getattr(args, "config", None), verbose=getattr(args, "verbose", False))
        self.base_dir = os.path.dirname(os.path.abspath(config_path))
        self.source_repo_dir = os.path.join(self.base_dir, "source_repo")
        self.config_file = os.path.join(self.base_dir, "config.yaml")
        self.transfer_set = args.transferset
        self.commit_id = args.commitid
        self.api = args.api
        self.apis = args.apis.split(",") if args.apis else []
        self.backends = args.backends.split(",") if args.backends else []
        self.diagnostics = args.diagnostics.split(",") if args.diagnostics else []
        self.loggers = args.loggers.split(",") if args.loggers else []
        self.named_values = args.namedvalues.split(",") if args.namedvalues else []
        self.products = args.products.split(",") if args.products else []
        self.subscriptions = args.subscriptions.split(",") if args.subscriptions else []
        self.tags = args.tags.split(",") if args.tags else []
        self.version_sets = args.versionsets.split(",") if args.versionsets else []
        self.source = args.source
        self.destination = args.destination
        self.use_pull_request = args.pullrequest
        self.verbose = args.verbose
        self.debug = args.debug
        self.continue_on_api_not_found = args.continueonapinotfound
        self.backup = args.backup
        self.push = args.push

        self.config = self.load_config()
        self.github_solution = self.config["general"]["github_solution"]
        self.github_data = self.config["general"]["github_data"]
        self.azure_default = self.config["general"]["azure_default"]
        self.source_config = self.get_node_config(self.source)
        self.destination_config = self.get_node_config(self.destination)

        self.github_repo = self.github_solution["repo"]
        self.github_token = self.github_solution["token"]
        self.commit_id = os.getenv("COMMITID", self.commit_id)
        self.update_repo_workflow = os.getenv("UPDATE_REPO_WORKFLOW", "Update Repo from API Management Service")
        self.update_service_workflow = os.getenv("UPDATE_SERVICE_WORKFLOW", "Update API Management Service")
        self.update_repo_file = os.getenv("UPDATE_REPO_FILE", ".github/workflows/update_repo.yaml")
        self.update_service_file = os.getenv("UPDATE_SERVICE_FILE", ".github/workflows/update_service.yaml")

        self.artifacts = {}
        self.logger_references = set()

    def load_config(self) -> dict:
        return transfer_config.load_config(self.args, self.error)

    def get_node_config(self, node: str) -> dict:
        return transfer_config.get_node_config(self.config, node, self.github_data, self.azure_default)

    def extract_repo_name(self, url: str) -> str:
        match = re.search(r"github\.com[:/](.+?)(\.git)?$", url)
        if match:
            return match.group(1)
        self.error(f"Invalid GitHub URL: {url}")

    def run_git_command(self, command, cwd=None):
        return git_ops.run_git_command(self, command, cwd)

    def clone_source_repo(self):
        return git_ops.clone_source_repo(self)

    async def run(self):
        self.check_parameters()
        if self.backup:
            await self.run_update_repo(self.source_config["github"], self.source)
            await self.run_update_repo(self.destination_config["github"], self.destination)
        await self.verify_github_access(self.destination_config["github"])
        await self.verify_source_and_destination()
        self.clone_source_repo()
        await self.process_apis()
        await self.create_changeset_branch()
        await self.apply_changeset()
        await self.finalize_changes()

    def check_parameters(self):
        if not self.github_token:
            self.error("GitHub token is missing.")
        if not self.source or not self.destination:
            self.error("Source or destination node is missing.")
        if not self.api and not self.apis and not self.transfer_set:
            self.error("No API specified for transfer.")
        if self.transfer_set:
            self.load_transfer_set(self.transfer_set)

    def load_transfer_set(self, file_path: str):
        try:
            if self.verbose:
                print(f"Loading transfer set from {file_path}")
            with open(file_path, "r") as file:
                data = yaml.safe_load(file)
            self.apis.extend(data.get("apiNames", []))
            self.backends.extend(data.get("backendNames", []))
            self.diagnostics.extend(data.get("diagnosticNames", []))
            self.loggers.extend(data.get("loggerNames", []))
            self.named_values.extend(data.get("namedValueNames", []))
            self.products.extend(data.get("productNames", []))
            self.subscriptions.extend(data.get("subscriptionNames", []))
            self.tags.extend(data.get("tagNames", []))

            supported_sections = {
                "apiNames",
                "backendNames",
                "diagnosticNames",
                "loggerNames",
                "namedValueNames",
                "productNames",
                "subscriptionNames",
                "tagNames",
            }
            for key in data.keys():
                if key not in supported_sections:
                    print(f"Warning: Section '{key}' is not supported and will be ignored.")
        except yaml.YAMLError as exc:
            self.error(f"Error parsing transfer set file: {exc}")

    async def verify_github_access(self, github_config: dict):
        return await github_api.verify_github_access(self, github_config)

    async def verify_source_and_destination(self):
        return await github_api.verify_source_and_destination(self)

    async def verify_node(self, github_config: dict, node: str, node_type: str):
        return await github_api.verify_node(self, github_config, node, node_type)

    async def process_apis(self):
        return await artifacts.process_apis(self)

    async def extract_and_process_api(self, api_path: str):
        return await artifacts.extract_and_process_api(self, api_path)

    async def check_and_copy_dependent_objects(self, api_path: str):
        return await artifacts.check_and_copy_dependent_objects(self, api_path)

    def get_directory_content(self, path: str):
        return artifacts.get_directory_content(self, path)

    async def search_backend_references(self, policy_path: str, backend_names, backend_references: set):
        return await artifacts.search_backend_references(self, policy_path, backend_names, backend_references)

    def get_file_content(self, file_path: str):
        return artifacts.get_file_content(self, file_path)

    async def extract_directory(self, path: str):
        return await artifacts.extract_directory(self, path)

    async def check_and_copy_diagnostics(self, api_path: str):
        return await artifacts.check_and_copy_diagnostics(self, api_path)

    async def adjust_diagnostic_information(self, logger_path: str):
        return await artifacts.adjust_diagnostic_information(self, logger_path)

    async def check_and_copy_loggers(self):
        return await artifacts.check_and_copy_loggers(self)

    async def adjust_logger_information(self, logger_path: str):
        return await artifacts.adjust_logger_information(self, logger_path)

    async def create_changeset_branch(self):
        return await github_api.create_changeset_branch(self)

    async def get_branch_sha(self, repo_name: str, branch: str, headers: dict) -> str:
        return await github_api.get_branch_sha(self, repo_name, branch, headers)

    async def apply_changeset(self):
        return await artifacts.apply_changeset(self)

    async def finalize_changes(self):
        if self.use_pull_request:
            await self.create_pull_request()
        else:
            await self.merge_changeset_branch()
            await self.run_update_service()
            if self.push:
                temp_data_repo_dir = os.path.join(self.base_dir, "temp_data_repo")
                self.run_git_command(f"git push origin {self.destination}", cwd=temp_data_repo_dir)
            await self.delete_changeset_branch()
            cleanup_repo_directories(self.base_dir, verbose=self.verbose)

    def on_rm_error(self, func, path, exc_info):
        return on_rm_error(func, path, exc_info)

    async def merge_changeset_branch(self):
        return await github_api.merge_changeset_branch(self)

    async def create_pull_request(self):
        return await github_api.create_pull_request(self)

    async def run_update_service(self):
        return await workflow.run_update_service(self)

    async def delete_changeset_branch(self):
        return await github_api.delete_changeset_branch(self)

    async def run_update_repo(self, github_config: dict, service_name: str):
        return await github_api.run_update_repo(self, github_config, service_name)

    def error(self, message: str):
        exit_with_error(message)


if __name__ == "__main__":
    try:
        args = parse_arguments()

        log_level = logging.WARNING
        if args.verbose:
            log_level = logging.INFO
        if args.debug:
            log_level = logging.DEBUG
        logging.basicConfig(level=log_level, format="%(asctime)s %(levelname)s %(name)s - %(message)s")

        # Resolve project root for both script and PyInstaller modes
        if getattr(sys, "frozen", False):
            base_dir = os.path.dirname(os.path.abspath(sys.executable))
        else:
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        source_repo_dir = os.path.join(base_dir, "source_repo")
        temp_data_repo_dir = os.path.join(base_dir, "temp_data_repo")
        prompt_and_cleanup_temp_dirs(source_repo_dir, temp_data_repo_dir)

        config_path = find_config_path(cli_arg=getattr(args, "config", None), verbose=getattr(args, "verbose", False))
        set_and_verify_git_identity_global(config_path)

        try:
            tool = APIMigrationTool(args)
            asyncio.run(tool.run())
        except Exception as e:
            print(f"\nError: {e}")
            cleanup_repo_directories(base_dir, verbose=True)
            print("Intermediate data was purged due to error.")
            raise
    except ArgumentParseError:
        sys.exit(2)
    except Exception as e:
        print(f"Unexpected Error: {e}")
        raise

