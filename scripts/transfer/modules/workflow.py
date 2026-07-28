import asyncio
import time
import uuid
from datetime import datetime, timedelta

import aiohttp
import pytz

from modules.utils import spinner


class DoneException(Exception):
    def __init__(self, workflow_id, workflow_url):
        self.workflow_id = workflow_id
        self.workflow_url = workflow_url
        super().__init__(f"Launched Workflow found with ID {workflow_id}")


async def run_update_service(tool):
    """Run update_service workflow and wait with progress output."""
    if tool.verbose:
        print("Running update service.")

    headers = {
        "Authorization": f'token {tool.github_solution["token"]}',
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    repo_name = tool.extract_repo_name(tool.github_solution["url"])
    workflow_file_name = tool.update_service_file.split("/")[-1]
    workflow_url = f"https://api.github.com/repos/{repo_name}/actions/workflows/{workflow_file_name}/dispatches"
    unique_id = str(uuid.uuid4())
    data = {
        "ref": "main",
        "inputs": {
            "API_MANAGEMENT_SERVICE_NAME": tool.destination,
            "COMMIT_ID": tool.commit_id,
            "COMMIT_ID_CHOICE": "publish-artifacts-in-last-commit",
            "unique_id": unique_id,
        },
    }
    tool.logger.debug("Dispatching workflow payload: %s", data)

    async with aiohttp.ClientSession(headers=headers) as session:
        spin_done, spin_thread = spinner("Dispatching workflow...") if tool.verbose else (None, None)
        async with session.post(workflow_url, json=data) as response:
            if response.status != 204:
                if tool.verbose and spin_done:
                    spin_done.set()
                    spin_thread.join()
                tool.error(f"Failed to dispatch workflow: {await response.text()}")
        if tool.verbose and spin_done:
            spin_done.set()
            spin_thread.join()

        print("Workflow dispatched successfully. Waiting for completion...")
        max_wait_time = 600
        start_time = time.time()
        calc_time = datetime.now()
        utc_time = calc_time.astimezone(pytz.utc)
        five_mins_ago_utc = utc_time - timedelta(minutes=5)
        five_mins_ago_utc = five_mins_ago_utc.replace(microsecond=0).isoformat(timespec="seconds")
        workflow_id = None
        workflow_html_url = None

        try:
            while time.time() - start_time < max_wait_time:
                elapsed = int(time.time() - start_time)
                print(f"[Workflow Progress] locating run... {elapsed}s elapsed", end="\r")
                params = {"created": f">{five_mins_ago_utc}", "event": "workflow_dispatch"}
                async with session.get(f"https://api.github.com/repos/{repo_name}/actions/runs", params=params) as runs_response:
                    runs = (await runs_response.json()).get("workflow_runs", [])
                    for run in runs:
                        jobs_url = run.get("jobs_url")
                        if not jobs_url:
                            continue
                        async with session.get(jobs_url) as jobs_response:
                            jobs = (await jobs_response.json()).get("jobs", [])
                            for job in jobs:
                                steps = job.get("steps", [])
                                if len(steps) > 1 and steps[1].get("name") == unique_id:
                                    workflow_id = job.get("run_id")
                                    workflow_html_url = run.get("html_url")
                                    raise DoneException(workflow_id, workflow_html_url)
                await asyncio.sleep(5)
        except DoneException as done:
            workflow_id = done.workflow_id
            workflow_html_url = done.workflow_url
        else:
            print("\nTimeout: Workflow did not start within the allotted time.")
            return None, None

    return await wait_for_workflow_completion(tool, repo_name, headers, workflow_id, workflow_html_url)


async def wait_for_workflow_completion(tool, repo_name, headers, workflow_id, workflow_html_url):
    """Poll workflow run until completion, with progress output."""
    if workflow_id is None:
        return None, None

    print(f"\nFound matching workflow with ID {workflow_id}")
    print(f"Workflow URL: {workflow_html_url}")
    print("Waiting for workflow completion...")

    max_wait_time = 600
    check_begin_time = time.time()
    status = conclusion = None

    async with aiohttp.ClientSession(headers=headers) as session:
        while time.time() - check_begin_time < max_wait_time:
            elapsed = int(time.time() - check_begin_time)
            print(f"[Workflow Progress] running... {elapsed}s elapsed", end="\r")
            async with session.get(f"https://api.github.com/repos/{repo_name}/actions/runs/{workflow_id}") as workflow_response:
                workflow = await workflow_response.json()
                status = workflow.get("status", "")
                conclusion = workflow.get("conclusion", "")
                if status not in ("in_progress", "queued"):
                    print(f"\nWorkflow ended with status: {status}, result: {conclusion}")
                    return status, conclusion
            await asyncio.sleep(5)

    print("\nTimeout: The workflow did not complete within the allotted time.")
    return status, conclusion
