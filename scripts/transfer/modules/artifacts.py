import base64
import json
import os
import re
from pathlib import Path
from typing import List


async def process_apis(tool):
    """Process API artifacts with progress output."""
    if tool.verbose:
        print(f"Processing API(s): {tool.api if tool.api else tool.apis}")

    api_paths = [f"apis/{tool.api}"] if tool.api else [f"apis/{api}" for api in tool.apis]
    total = len(api_paths)
    for index, api_path in enumerate(api_paths, start=1):
        print(f"[API Progress] {index}/{total}: {api_path}")
        await extract_and_process_api(tool, api_path)

    if tool.debug:
        tool.logger.debug("Extracted APIs: %s", list(tool.artifacts.keys()))


async def extract_and_process_api(tool, api_path: str):
    await extract_directory(tool, api_path)
    await check_and_copy_dependent_objects(tool, api_path)


async def check_and_copy_dependent_objects(tool, api_path: str):
    artifacts_root = os.path.join(tool.source_repo_dir, "apimartifacts", tool.source)
    try:
        from v6_adapter import V6DependencyResolver

        resolver = V6DependencyResolver(artifacts_root)
        abs_api_path = Path(artifacts_root) / api_path
        if tool.verbose:
            print(f"Resolving dependencies for {api_path} using V6 logic...")

        deps = resolver.get_dependencies(abs_api_path)
        for dep_type in ("backends", "tags", "versionSets", "namedValues", "loggers"):
            for dep_path in deps.get(dep_type, []):
                rel_path = str(dep_path.relative_to(Path(artifacts_root)))
                await extract_directory(tool, rel_path)
    except ImportError:
        tool.error("v6_adapter not found. Dependency resolution cannot continue.")
    except Exception as e:
        tool.error(f"Error checking dependencies v6: {e}")


def get_directory_content(tool, path: str) -> List[dict]:
    if os.path.exists(path) and os.path.isdir(path):
        return [
            {"name": name, "type": "dir" if os.path.isdir(os.path.join(path, name)) else "file"}
            for name in os.listdir(path)
        ]
    tool.logger.debug("Directory not found or empty: %s", path)
    return []


async def search_backend_references(tool, policy_path: str, backend_names: List[str], backend_references: set):
    full_policy_path = os.path.join(tool.source_repo_dir, f"apimartifacts/{tool.source}/{policy_path}")
    policy_file_content = get_file_content(tool, full_policy_path)
    if not policy_file_content:
        print(f"Warning: policy.xml not found at path '{full_policy_path}'.")
        return
    for backend_name in backend_names:
        if f'<set-backend-service backend-id="{backend_name}" />' in policy_file_content:
            backend_references.add(backend_name)


def get_file_content(tool, file_path: str):
    if os.path.exists(file_path) and os.path.isfile(file_path):
        with open(file_path, "r") as file:
            return file.read()
    tool.logger.debug("Unable to get file content for '%s'.", file_path)
    return None


async def extract_directory(tool, path: str):
    if tool.verbose:
        print(f"Extracting directory '{path}' from source '{tool.source}'")

    local_path = os.path.join(tool.source_repo_dir, f"apimartifacts/{tool.source}/{path}")
    if not os.path.exists(local_path):
        tool.error(f"Directory '{local_path}' not found in source.")
        return

    file_paths = []
    for root, _, files in os.walk(local_path):
        for file_name in files:
            file_paths.append((root, file_name))

    total_files = len(file_paths)
    for index, (root, file_name) in enumerate(file_paths, start=1):
        full_file_path = os.path.join(root, file_name)
        relative_file_path = os.path.relpath(
            full_file_path, os.path.join(tool.source_repo_dir, f"apimartifacts/{tool.source}")
        )
        with open(full_file_path, "r") as file:
            content = file.read()

        tool.artifacts[relative_file_path] = {
            "name": file_name,
            "path": full_file_path,
            "sha": "",
            "size": os.path.getsize(full_file_path),
            "url": "",
            "html_url": "",
            "git_url": "",
            "download_url": "",
            "type": "file",
            "content": base64.b64encode(content.encode()).decode(),
            "encoding": "base64",
        }
        if total_files > 1 and (index == 1 or index == total_files or index % 20 == 0):
            print(f"[File Progress] Extract {index}/{total_files}: {relative_file_path}")


async def check_and_copy_diagnostics(tool, api_path: str):
    diagnostics_path = f"apimartifacts/{tool.source}/{api_path}/diagnostics"
    diagnostics_dir = get_directory_content(tool, diagnostics_path)
    if not diagnostics_dir:
        print(f"Warning: Diagnostics directory for API '{api_path}' not found at path '{diagnostics_path}'.")
        return

    for diagnostic in diagnostics_dir:
        if diagnostic["type"] == "dir":
            logger_path = os.path.join(api_path, "diagnostics", diagnostic["name"])
            print(f"INFO: Processing diagnostic directory: {logger_path}")
            await extract_directory(tool, logger_path)
            await adjust_diagnostic_information(tool, logger_path)
        else:
            print(f"INFO: Skipping non-directory item in diagnostics: {diagnostic['name']}")


async def adjust_diagnostic_information(tool, logger_path: str):
    diagnostic_info_path = f"{logger_path}/diagnosticInformation.json"
    diagnostic_info = tool.artifacts.get(diagnostic_info_path)
    if not diagnostic_info:
        print(f"Warning: diagnosticInformation.json not found at path '{diagnostic_info_path}'.")
        return

    content = base64.b64decode(diagnostic_info["content"]).decode()
    diagnostic_info_json = json.loads(content)
    if "loggerId" in diagnostic_info_json.get("properties", {}):
        logger_id = diagnostic_info_json["properties"]["loggerId"]
        tool.logger_references.add(logger_id.split("/")[-1])
        diagnostic_info_json["properties"]["loggerId"] = (
            f"/subscriptions/{tool.destination_config['azure']['subscription_id']}"
            f"/resourceGroups/{tool.destination_config['azure']['resource_group']}"
            f"/providers/Microsoft.ApiManagement/service/{tool.destination}/loggers/{logger_id.split('/')[-1]}"
        )
        diagnostic_info["content"] = base64.b64encode(json.dumps(diagnostic_info_json).encode()).decode()


async def check_and_copy_loggers(tool):
    for logger_name in tool.logger_references:
        logger_path = f"loggers/{logger_name}"
        print(f"INFO: Processing logger directory: {logger_path}")
        await extract_directory(tool, logger_path)
        await adjust_logger_information(tool, logger_path)


async def adjust_logger_information(tool, logger_path: str):
    logger_info_path = f"{logger_path}/loggerInformation.json"
    logger_info = tool.artifacts.get(logger_info_path)
    if not logger_info:
        print(f"Warning: loggerInformation.json not found at path '{logger_info_path}'.")
        return
    content = base64.b64decode(logger_info["content"]).decode()
    logger_info_json = json.loads(content)
    if "resourceId" in logger_info_json:
        resource_id = logger_info_json["properties"]["resourceId"]
        logger_info_json["properties"]["resourceId"] = (
            f"/subscriptions/{tool.destination_config['azure']['subscription_id']}"
            f"/resourceGroups/{tool.destination_config['azure']['resource_group']}"
            f"/providers/Microsoft.ApiManagement/service/{tool.destination}/loggers/{resource_id.split('/')[-1]}"
        )
        logger_info["content"] = base64.b64encode(json.dumps(logger_info_json).encode()).decode()


async def apply_changeset(tool):
    if tool.verbose:
        print("Applying changeset.")

    destination_subscription_id = tool.destination_config["azure"]["subscription_id"]
    destination_resource_group = tool.destination_config["azure"]["resource_group"]
    destination_service_name = tool.destination
    # Use tool.base_dir (project root) instead of os.getcwd() for reliability
    temp_data_repo_dir = os.path.join(tool.base_dir, "temp_data_repo")
    base_dir = os.path.join(temp_data_repo_dir, "apimartifacts", tool.destination)

    artifact_items = list(tool.artifacts.items())
    total_artifacts = len(artifact_items)
    for index, (artifact_path, data) in enumerate(artifact_items, start=1):
        relative_artifact_path = artifact_path.replace(f"apimartifacts/{tool.source}/", "")
        destination_path = os.path.join(base_dir, relative_artifact_path)
        content = data["content"]
        if isinstance(content, str):
            content = base64.b64decode(content).decode()

        if "apiInformation.json" in destination_path:
            api_info_json = json.loads(content)
            if "properties" in api_info_json and "apiVersionSetId" in api_info_json["properties"]:
                api_version_set_id = api_info_json["properties"]["apiVersionSetId"]
                api_info_json["properties"]["apiVersionSetId"] = re.sub(
                    r"/subscriptions/[^/]+/resourceGroups/[^/]+/providers/Microsoft.ApiManagement/service/[^/]+/apiVersionSets/",
                    f"/subscriptions/{destination_subscription_id}/resourceGroups/{destination_resource_group}/providers/Microsoft.ApiManagement/service/{destination_service_name}/apiVersionSets/",
                    api_version_set_id,
                )
                content = json.dumps(api_info_json, indent=4)

        os.makedirs(os.path.dirname(destination_path), exist_ok=True)
        with open(destination_path, "w") as file:
            file.write(content)

        tool.run_git_command(f'git add "{destination_path}"', cwd=temp_data_repo_dir)
        if total_artifacts > 1 and (index == 1 or index == total_artifacts or index % 20 == 0):
            print(f"[File Progress] Apply {index}/{total_artifacts}: {destination_path}")

    commit_message = "Applying changeset"
    tool.run_git_command(f'git commit -m "{commit_message}"', cwd=temp_data_repo_dir)
    branch_name = f"changeset-{tool.destination}"
    tool.run_git_command(f"git push origin {branch_name}", cwd=temp_data_repo_dir)

    if tool.verbose:
        print("Changeset applied.")

