import yaml

from apimops_utils import find_config_path


def load_config(args, error_handler):
    """Load configuration from YAML."""
    try:
        config_path = find_config_path(
            cli_arg=getattr(args, "config", None),
            verbose=getattr(args, "verbose", False),
        )
        with open(config_path, "r") as file:
            return yaml.safe_load(file)
    except yaml.YAMLError as exc:
        error_handler(f"Error parsing config file: {exc}")
    except FileNotFoundError as exc:
        error_handler(str(exc))


def get_node_config(config, node, github_data, azure_default):
    """Get node configuration with backward compatible defaults."""
    if node in config["apim_services"]:
        node_config = config["apim_services"][node]
        github_config = node_config.get("github", github_data)
        azure_config = node_config.get("azure", azure_default)
    else:
        github_config = github_data
        azure_config = azure_default

    return {
        "github": github_config,
        "azure": azure_config,
    }

