import os

import aiohttp

from modules.git_ops import prepare_temp_data_repo


async def verify_github_access(tool, github_config: dict):
    if tool.verbose:
        print(f"Checking GitHub access for repo: {github_config['repo']}")

    headers = {"Authorization": f'token {github_config["token"]}'}
    repo_name = tool.extract_repo_name(github_config["url"])
    url = f"https://api.github.com/repos/{repo_name}"
    tool.logger.debug("Verifying GitHub access: %s", url)

    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(url) as response:
            response_text = await response.text()
            if response.status != 200:
                tool.error(f"GitHub access failed with status code {response.status}. Response: {response_text}")
            if tool.verbose:
                print("GitHub access verified.")


async def verify_source_and_destination(tool):
    if tool.verbose:
        print(f"Verifying source node: {tool.source}")
        print(f"Verifying destination node: {tool.destination}")
    await verify_node(tool, tool.destination_config["github"], tool.destination, "destination")


async def verify_node(tool, github_config: dict, node: str, node_type: str):
    headers = {"Authorization": f'token {github_config["token"]}'}
    repo_name = tool.extract_repo_name(github_config["url"])
    branch_url = f"https://api.github.com/repos/{repo_name}/branches/{node}"
    dir_url = f"https://api.github.com/repos/{repo_name}/contents/apimartifacts/{node}?ref={node}"
    tool.logger.debug("Verifying %s node with %s and %s", node_type, branch_url, dir_url)

    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(branch_url) as branch_response:
            if branch_response.status != 200:
                tool.error(f"{node_type.capitalize()} '{node}': Unknown API Management Service. Response: {await branch_response.text()}")

        async with session.get(dir_url) as dir_response:
            if dir_response.status != 200:
                tool.error(
                    f"{node_type.capitalize()} '{node}': Branch was found in repo {repo_name}, but artifact directory is missing. Response: {await dir_response.text()}"
                )

    if tool.verbose:
        print(f"{node_type.capitalize()} node '{node}' verified.")


async def create_changeset_branch(tool):
    if tool.verbose:
        print("Creating changeset branch on the GitHub server.")

    headers = {"Authorization": f'token {tool.destination_config["github"]["token"]}'}
    repo_name = tool.extract_repo_name(tool.destination_config["github"]["url"])
    branch_name = f"changeset-{tool.destination}"
    base_branch = tool.destination

    # Delete stale changeset branch if it exists from a previous run
    delete_url = f"https://api.github.com/repos/{repo_name}/git/refs/heads/{branch_name}"
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.delete(delete_url) as del_resp:
            if del_resp.status == 204:
                if tool.verbose:
                    print(f"Removed stale changeset branch '{branch_name}'.")
            elif del_resp.status != 422:
                tool.error(f"Failed to delete stale branch: {await del_resp.text()}")

    create_branch_url = f"https://api.github.com/repos/{repo_name}/git/refs"
    data = {"ref": f"refs/heads/{branch_name}", "sha": await get_branch_sha(tool, repo_name, base_branch, headers)}
    tool.logger.debug("Creating branch via %s payload=%s", create_branch_url, data)

    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.post(create_branch_url, json=data) as response:
            if response.status not in [200, 201]:
                tool.error(f"Failed to create changeset branch with status code {response.status}. Response: {await response.text()}")

    prepare_temp_data_repo(tool, repo_name, branch_name)
    if tool.verbose:
        print(f"Checked out changeset branch '{branch_name}' in temp_data_repo directory.")


async def get_branch_sha(tool, repo_name: str, branch: str, headers: dict) -> str:
    url = f"https://api.github.com/repos/{repo_name}/git/refs/heads/{branch}"
    tool.logger.debug("Fetching branch SHA: %s", url)

    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(url) as response:
            if response.status != 200:
                tool.error(f"Failed to get branch SHA for branch '{branch}' with status code {response.status}. Response: {await response.text()}")
            return (await response.json())["object"]["sha"]


async def merge_changeset_branch(tool):
    if tool.verbose:
        print("Merging changeset branch.")

    branch_name = f"changeset-{tool.destination}"
    temp_data_repo_dir = os.path.join(tool.base_dir, "temp_data_repo")
    tool.run_git_command(f"git push origin {branch_name}", cwd=temp_data_repo_dir)

    headers = {"Authorization": f'token {tool.destination_config["github"]["token"]}'}
    repo_name = tool.extract_repo_name(tool.destination_config["github"]["url"])
    merge_url = f"https://api.github.com/repos/{repo_name}/merges"
    data = {
        "base": tool.destination,
        "head": branch_name,
        "commit_message": f"Migrating APIs to {tool.destination}",
        "merge_method": "merge",
    }
    tool.logger.debug("Merging branch via %s payload=%s", merge_url, data)

    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.post(merge_url, json=data) as response:
            if response.status not in [200, 201, 204]:
                tool.error(f"Failed to merge changeset branch with status code {response.status}. Response: {await response.text()}")

    if tool.verbose:
        print("Changeset branch merged.")


async def create_pull_request(tool):
    if tool.verbose:
        print("Creating pull request for changeset.")

    headers = {"Authorization": f'token {tool.destination_config["github"]["token"]}'}
    branch_name = f"changeset-{tool.destination}"
    pr_url = f'https://api.github.com/repos/{tool.destination_config["github"]["repo"]}/pulls'
    data = {
        "title": f"Migrate APIs to {tool.destination}",
        "head": branch_name,
        "base": tool.destination,
        "body": "Automated migration of APIs.",
    }
    tool.logger.debug("Creating PR via %s payload=%s", pr_url, data)

    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.post(pr_url, json=data) as response:
            if response.status not in [200, 201]:
                tool.error(f"Failed to create pull request with status code {response.status}")

    if tool.verbose:
        print("Pull request created.")


async def delete_changeset_branch(tool):
    if tool.verbose:
        print("Deleting changeset branch.")

    headers = {"Authorization": f'token {tool.destination_config["github"]["token"]}'}
    repo_name = tool.extract_repo_name(tool.destination_config["github"]["url"])
    branch_name = f"changeset-{tool.destination}"
    delete_url = f"https://api.github.com/repos/{repo_name}/git/refs/heads/{branch_name}"
    tool.logger.debug("Deleting branch via %s", delete_url)

    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.delete(delete_url) as response:
            if response.status not in [204, 200]:
                tool.error(f"Failed to delete changeset branch with status code {response.status}. Response: {await response.text()}")

    if tool.verbose:
        print("Changeset branch deleted.")


async def run_update_repo(tool, github_config: dict, service_name: str):
    """Dispatch update_repo workflow when backup is enabled."""
    headers = {
        "Authorization": f'token {github_config["token"]}',
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    repo_name = tool.extract_repo_name(github_config["url"])
    workflow_file_name = tool.update_repo_file.split("/")[-1]
    workflow_url = f"https://api.github.com/repos/{repo_name}/actions/workflows/{workflow_file_name}/dispatches"
    payload = {"ref": "main", "inputs": {"API_MANAGEMENT_SERVICE_NAME": service_name}}
    tool.logger.info("Dispatching update_repo workflow for %s", service_name)

    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.post(workflow_url, json=payload) as response:
            if response.status != 204:
                tool.error(f"Failed to dispatch update repo workflow for {service_name}: {await response.text()}")

