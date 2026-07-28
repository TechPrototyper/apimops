#!/usr/bin/env python3
"""
apimops Model Context Protocol (MCP) Server

Provides LLM agents (Claude Desktop, Antigravity, VS Code, Cursor, etc.)
with direct tools to query Azure APIM nodes, search APIs, and trigger transfers.

Usage:
    python scripts/mcp_server.py [--config /path/to/config.yaml]
"""

import sys
import os
import io
import json
import asyncio
from contextlib import redirect_stdout, redirect_stderr
import yaml

# Ensure project modules are in path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, os.path.join(SCRIPT_DIR, 'common'))
sys.path.insert(0, os.path.join(SCRIPT_DIR, 'transfer'))

from mcp.server.fastmcp import FastMCP
from apimops_utils import find_config_path

# Initialize FastMCP Server
mcp = FastMCP("apimops-mcp", log_level="INFO")

# Global Config & Azure Client Cache
_config_cache = None

def get_loaded_config(config_path_arg=None):
    global _config_cache
    if _config_cache is None:
        cfg_path = find_config_path(config_path_arg)
        with open(cfg_path, 'r', encoding='utf-8') as f:
            _config_cache = yaml.safe_load(f)
    return _config_cache

def get_apim_client_for_node(node_name: str, config_path_arg=None):
    """
    Initializes Azure ApiManagementClient for the specified node using credentials from config.yaml.
    """
    from azure.identity import ClientSecretCredential
    from azure.mgmt.apimanagement import ApiManagementClient

    config = get_loaded_config(config_path_arg)
    apim_services = config.get("apim_services", {})

    if node_name not in apim_services:
        available = list(apim_services.keys())
        raise ValueError(f"Unknown APIM node '{node_name}'. Available nodes: {available}")

    azure_cfg = config.get("general", {}).get("azure_default", {}) or config.get("azure_default", {})
    tenant_id = azure_cfg.get("tenant_id")
    subscription_id = azure_cfg.get("subscription_id")
    client_id = azure_cfg.get("sp_client_id")
    client_secret = azure_cfg.get("sp_client_secret")

    if not all([tenant_id, subscription_id, client_id, client_secret]):
        raise ValueError("Missing Azure credentials in config.yaml under azure_default.")

    credential = ClientSecretCredential(
        tenant_id=tenant_id,
        client_id=client_id,
        client_secret=client_secret
    )

    client = ApiManagementClient(credential=credential, subscription_id=subscription_id)
    resource_group = azure_cfg.get("resource_group", "rg-apim-dev-01")
    apim_service_name = node_name  # In our config, key is the APIM service name

    return client, resource_group, apim_service_name


@mcp.tool()
def list_nodes() -> str:
    """
    List all configured Azure API Management (APIM) nodes available in apimops.
    Returns node names and their configured descriptions.
    """
    try:
        config = get_loaded_config()
        apim_services = config.get("apim_services", {})
        result = []
        for node_key, info in apim_services.items():
            result.append({
                "node_name": node_key,
                "description": info.get("name", node_key),
                "resource_group": config.get("azure_default", {}).get("resource_group", "")
            })
        return json.dumps(result, indent=2)
    except Exception as e:
        return f"Error listing APIM nodes: {str(e)}"


@mcp.tool()
def list_apis(node: str) -> str:
    """
    List all APIs deployed on a specific Azure APIM node (e.g., 'DEV-APIM-SERVICE', 'PROD-APIM-SERVICE').
    Returns API ID, display name, path, service URL, and protocols.
    """
    try:
        client, resource_group, apim_service_name = get_apim_client_for_node(node)
        api_list = []
        
        # Query Azure APIM REST API via Azure SDK
        apis = client.api.list_by_service(resource_group_name=resource_group, service_name=apim_service_name)
        for api in apis:
            api_list.append({
                "id": api.name,
                "display_name": api.display_name,
                "path": api.path,
                "service_url": api.service_url,
                "protocols": api.protocols,
                "is_current": api.is_current,
                "api_type": api.api_type
            })
            
        return json.dumps({
            "node": node,
            "total_count": len(api_list),
            "apis": api_list
        }, indent=2)
    except Exception as e:
        return f"Error listing APIs on node '{node}': {str(e)}"


@mcp.tool()
def search_apis(node: str, query: str) -> str:
    """
    Search APIs on a specific APIM node by keyword or search term (e.g. 'SAP', 'invoice', 'order').
    Returns matching APIs with ID, display name, and path.
    """
    try:
        client, resource_group, apim_service_name = get_apim_client_for_node(node)
        query_lower = query.lower()
        matching_apis = []

        apis = client.api.list_by_service(resource_group_name=resource_group, service_name=apim_service_name)
        for api in apis:
            name_match = query_lower in (api.name or "").lower()
            display_match = query_lower in (api.display_name or "").lower()
            desc_match = query_lower in (api.description or "").lower()
            path_match = query_lower in (api.path or "").lower()

            if name_match or display_match or desc_match or path_match:
                matching_apis.append({
                    "id": api.name,
                    "display_name": api.display_name,
                    "path": api.path,
                    "service_url": api.service_url,
                    "description": api.description or ""
                })

        return json.dumps({
            "node": node,
            "search_query": query,
            "matches_found": len(matching_apis),
            "apis": matching_apis
        }, indent=2)
    except Exception as e:
        return f"Error searching APIs on node '{node}': {str(e)}"


@mcp.tool()
def get_api_details(node: str, api_id: str) -> str:
    """
    Retrieve detailed information for a specific API on an APIM node.
    """
    try:
        client, resource_group, apim_service_name = get_apim_client_for_node(node)
        api = client.api.get(resource_group_name=resource_group, service_name=apim_service_name, api_id=api_id)
        
        details = {
            "id": api.name,
            "display_name": api.display_name,
            "description": api.description or "",
            "path": api.path,
            "service_url": api.service_url,
            "protocols": api.protocols,
            "subscription_required": api.subscription_required,
            "is_current": api.is_current,
            "api_version": api.api_version or "",
            "api_version_set_id": api.api_version_set_id or ""
        }
        return json.dumps(details, indent=2)
    except Exception as e:
        return f"Error getting details for API '{api_id}' on node '{node}': {str(e)}"


@mcp.tool()
async def transfer_api(source: str, destination: str, api: str, pullrequest: bool = False) -> str:
    """
    Transfer an API from a source APIM node (e.g. 'DEV-APIM-SERVICE') to a destination node (e.g. 'PROD-APIM-SERVICE').
    Optionally creates a GitHub Pull Request instead of direct merge.
    """
    # Import transfer module dynamically
    from transfer import APIMigrationTool
    
    class Args:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)
                
    args = Args(
        source=source,
        target=destination,
        destination=destination,
        api=api,
        apis=None,
        config=None,
        verbose=True,
        debug=False,
        push=True,
        pullrequest=pullrequest,
        use_pull_request=pullrequest,
        continueonapinotfound=False,
        backup=False,
        transferset=None,
        commitid=None,
        backends=None,
        diagnostics=None,
        loggers=None,
        namedvalues=None,
        products=None,
        subscriptions=None,
        tags=None,
        versionsets=None,
        githubrepo=None,
        githubtoken=None
    )

    # Capture stdout to stderr so MCP JSON-RPC protocol over stdout is preserved
    buffer = io.StringIO()
    try:
        tool = APIMigrationTool(args)
        with redirect_stdout(sys.stderr):
            await tool.run()
        return f"Successfully completed transfer of API '{api}' from '{source}' to '{destination}'."
    except Exception as e:
        return f"Failed to transfer API '{api}': {str(e)}"


if __name__ == "__main__":
    mcp.run()
