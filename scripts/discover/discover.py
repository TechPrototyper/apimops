#!/usr/bin/env python3
"""
apimops Azure APIM Discovery & Config Generator Utility (discover)

Scans accessible Azure Subscriptions, Resource Groups, and APIM Instances,
verifies permissions, prompts the user to select managed nodes,
and automatically generates a valid config.yaml file.
"""

import os
import sys
import yaml
import argparse
import platform
from colorama import init, Fore, Style

# --- PyInstaller / Standalone Compatibility ---
if getattr(sys, "frozen", False):
    _meipass = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(sys.executable)))
    if _meipass not in sys.path:
        sys.path.insert(0, _meipass)
    _discover_base = _meipass
else:
    _discover_base = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    _common_dir = os.path.join(_discover_base, "scripts", "common")
    if _common_dir not in sys.path:
        sys.path.insert(0, _common_dir)

try:
    from apimops_utils import find_config_path
except ImportError:
    try:
        from scripts.common.apimops_utils import find_config_path
    except ImportError:
        find_config_path = None

# Initialize Colorama
init(autoreset=True)

VERSION = "1.0.0"

def get_azure_credentials():
    """Obtain Azure credentials using DefaultAzureCredential with browser fallback."""
    from azure.identity import DefaultAzureCredential, InteractiveBrowserCredential
    print(f"{Fore.CYAN}Connecting to Azure authentication context...{Style.RESET_ALL}")
    try:
        cred = DefaultAzureCredential()
        # Test token acquisition
        cred.get_token("https://management.azure.com/.default")
        print(f"{Fore.GREEN}✔ Azure credentials obtained successfully.{Style.RESET_ALL}")
        return cred
    except Exception:
        print(f"{Fore.YELLOW}Default credential check failed. Launching interactive browser login...{Style.RESET_ALL}")
        try:
            cred = InteractiveBrowserCredential()
            cred.get_token("https://management.azure.com/.default")
            print(f"{Fore.GREEN}✔ Interactive login successful.{Style.RESET_ALL}")
            return cred
        except Exception as e:
            print(f"{Fore.RED}✘ Azure authentication failed: {e}{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}Tip: Try running 'az login' in your shell first.{Style.RESET_ALL}")
            sys.exit(1)

def scan_azure_apim_nodes(cred):
    """Scan all accessible Subscriptions, Resource Groups, and APIM Instances."""
    from azure.mgmt.resource import SubscriptionClient
    from azure.mgmt.apimanagement import ApiManagementClient

    sub_client = SubscriptionClient(cred)
    subscriptions = list(sub_client.subscriptions.list())

    if not subscriptions:
        print(f"{Fore.RED}No accessible Azure subscriptions found.{Style.RESET_ALL}")
        return []

    print(f"{Fore.CYAN}Found {len(subscriptions)} accessible subscription(s). Scanning for APIM instances...{Style.RESET_ALL}\n")
    discovered_nodes = []

    for sub in subscriptions:
        sub_id = sub.subscription_id
        sub_name = sub.display_name
        print(f"{Fore.MAGENTA}📁 Subscription: {sub_name} ({sub_id}){Style.RESET_ALL}")

        try:
            apim_client = ApiManagementClient(cred, sub_id)
            services = list(apim_client.api_management_service.list())
            
            if not services:
                print(f"   {Fore.BLACK}{Style.BRIGHT}└── (No APIM instances found in this subscription){Style.RESET_ALL}")
                continue

            for service in services:
                rg_name = service.id.split("/resourceGroups/")[1].split("/")[1] if "/resourceGroups/" in service.id else "Unknown"
                sku_name = service.sku.name if service.sku else "Unknown"
                
                print(f"   ├── {Fore.YELLOW}Resource Group: {rg_name}{Style.RESET_ALL}")
                print(f"   │    └── {Fore.GREEN}APIM Instance: {service.name}{Style.RESET_ALL} (SKU: {sku_name})")

                discovered_nodes.append({
                    "service_name": service.name,
                    "subscription_id": sub_id,
                    "subscription_name": sub_name,
                    "resource_group": rg_name,
                    "sku": sku_name,
                    "location": service.location,
                })
        except Exception as e:
            print(f"   └── {Fore.RED}Error scanning subscription {sub_name}: {e}{Style.RESET_ALL}")

    return discovered_nodes

def interactive_selection(discovered_nodes):
    """Prompt the user to select which discovered APIM instances to manage."""
    if not discovered_nodes:
        return []

    print(f"\n{Fore.CYAN}============================================================{Style.RESET_ALL}")
    print(f"{Fore.CYAN}APIM INSTANCE SELECTION{Style.RESET_ALL}")
    print(f"{Fore.CYAN}============================================================{Style.RESET_ALL}")
    print("Select which APIM instances to include in your apimops config.yaml.\n")

    selected_nodes = []
    for node in discovered_nodes:
        name = node["service_name"]
        rg = node["resource_group"]
        sub = node["subscription_name"]
        sku = node["sku"]

        choice = input(f"Include APIM instance {Fore.GREEN}{name}{Style.RESET_ALL} (RG: {rg}, SKU: {sku}) in managed nodes? [Y/n]: ").strip().lower()
        if choice in ("", "y", "yes"):
            description = input(f"  Enter optional description for {name} [{sku} SKU]: ").strip()
            if not description:
                description = f"{name} ({sku} SKU in {rg})"
            node["description"] = description
            selected_nodes.append(node)
            print(f"  {Fore.GREEN}✔ Added {name}{Style.RESET_ALL}\n")
        else:
            print(f"  {Fore.YELLOW}⊘ Skipped {name}{Style.RESET_ALL}\n")

    return selected_nodes

def generate_config_yaml(selected_nodes, output_path="config.yaml"):
    """Generate config.yaml based on selected nodes and user prompts."""
    print(f"{Fore.CYAN}============================================================{Style.RESET_ALL}")
    print(f"{Fore.CYAN}GITHUB & AZURE CONFIGURATION PROMPTS{Style.RESET_ALL}")
    print(f"{Fore.CYAN}============================================================{Style.RESET_ALL}")

    solution_url = input("Enter GitHub Operations Repo URL [e.g. https://github.com/my-org/apimops.git]: ").strip()
    solution_token = input("Enter GitHub Operations Token (PAT): ").strip()
    data_url = input("Enter GitHub Data Repo URL [e.g. https://github.com/my-org/apimdata.git]: ").strip()
    data_token = input("Enter GitHub Data Token (PAT): ").strip()

    first_node = selected_nodes[0] if selected_nodes else {}
    tenant_id = input(f"Enter Azure Tenant ID: ").strip()
    sp_client_id = input(f"Enter Azure Service Principal Client ID: ").strip()
    sp_client_secret = input(f"Enter Azure Service Principal Client Secret: ").strip()

    config_data = {
        "general": {
            "apiops": {
                "release_version": "6.0.2",
                "specification_format": "OpenAPIV3Yaml"
            },
            "github_solution": {
                "repo": solution_url.rstrip(".git").split("/")[-1] if solution_url else "apimops",
                "url": solution_url,
                "token": solution_token
            },
            "github_data": {
                "repo": data_url.rstrip(".git").split("/")[-1] if data_url else "apimdata",
                "url": data_url,
                "token": data_token
            },
            "azure_default": {
                "tenant_id": tenant_id,
                "subscription_id": first_node.get("subscription_id", ""),
                "resource_group": first_node.get("resource_group", ""),
                "sp_client_id": sp_client_id,
                "sp_client_secret": sp_client_secret
            },
            "ai_assistant": {
                "provider": "grok",
                "endpoint": "https://api.x.ai/v1/chat/completions",
                "api_key": "<REPLACE_WITH_LLM_KEY>",
                "model": "grok-build-0.1"
            }
        },
        "apim_services": {}
    }

    for node in selected_nodes:
        config_data["apim_services"][node["service_name"]] = {
            "name": node["description"],
            "azure": {
                "tenant_id": tenant_id,
                "subscription_id": node["subscription_id"],
                "resource_group": node["resource_group"],
                "sp_client_id": sp_client_id,
                "sp_client_secret": sp_client_secret
            }
        }

    with open(output_path, "w") as f:
        yaml.dump(config_data, f, default_flow_style=False, sort_keys=False)

    print(f"\n{Fore.GREEN}✔ Successfully generated {output_path}!{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}Next Step: Run 'setup.exe' (or './setup') to validate connectivity and provision GitHub Secrets.{Style.RESET_ALL}\n")

def main():
    parser = argparse.ArgumentParser(description="apimops Azure APIM Discovery & Config Generator Utility.", add_help=True)
    parser.add_argument("-o", "--output", default="config.yaml", help="Path to save generated config file (default: config.yaml)")
    args = parser.parse_args()

    print(f"============================================================")
    print(f"apimops Azure APIM Discovery Utility v{VERSION}")
    print(f"============================================================\n")

    cred = get_azure_credentials()
    nodes = scan_azure_apim_nodes(cred)

    if not nodes:
        print(f"{Fore.YELLOW}No APIM nodes were discovered. Ensure your account has Reader/Contributor permissions across your Azure Subscriptions.{Style.RESET_ALL}")
        return

    selected = interactive_selection(nodes)
    if selected:
        generate_config_yaml(selected, args.output)
    else:
        print(f"{Fore.YELLOW}No APIM nodes were selected. Exiting without creating config.yaml.{Style.RESET_ALL}")

if __name__ == "__main__":
    main()
