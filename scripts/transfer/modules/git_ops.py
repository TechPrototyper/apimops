import os
import subprocess


def run_git_command(tool, command, cwd=None):
    """Run a git command and return CompletedProcess."""
    result = subprocess.run(command, cwd=cwd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        tool.logger.debug("Git command failed: %s\n%s", command, result.stderr)
    else:
        tool.logger.debug("Git command output: %s", result.stdout)
    return result


def clone_source_repo(tool):
    """Clone source repository and checkout source branch."""
    if not os.path.exists(tool.source_repo_dir):
        os.makedirs(tool.source_repo_dir)
    tool.logger.info("Cloning source repo to %s", tool.source_repo_dir)
    run_git_command(tool, f"git clone {tool.source_config['github']['url']} .", cwd=tool.source_repo_dir)
    run_git_command(tool, f"git checkout {tool.source}", cwd=tool.source_repo_dir)


def prepare_temp_data_repo(tool, repo_name, branch_name):
    """Clone destination repository to temp_data_repo and checkout branch."""
    temp_data_repo_dir = os.path.join(tool.base_dir, "temp_data_repo")
    os.makedirs(temp_data_repo_dir, exist_ok=True)
    run_git_command(tool, f"git clone https://github.com/{repo_name}.git .", cwd=temp_data_repo_dir)
    run_git_command(tool, f"git checkout {branch_name}", cwd=temp_data_repo_dir)
    return temp_data_repo_dir
