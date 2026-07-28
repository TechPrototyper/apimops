# apimops Model Context Protocol (MCP) Server

The `apimops` repository includes an optional, standalone **MCP Server** ([`scripts/mcp_server.py`](file:///Users/timw/Projects/apimops/scripts/mcp_server.py)) that exposes APIM node listing, API searching, metadata inspection, and transfer capabilities directly to AI agents (Claude Desktop, Antigravity, VS Code, Cursor, etc.).

---

## 🎯 Key Features

- **`list_nodes`**: Lists all APIM environment nodes configured in `config.yaml` (`DEV-APIM-SERVICE`, `STAGE-APIM-SERVICE`, `PROD-APIM-SERVICE`).
- **`list_apis`**: Queries Azure APIM via Azure SDK and returns all deployed APIs for a specific node.
- **`search_apis`**: Searches APIs on a node by keyword (e.g. `"SAP"`, `"invoice"`).
- **`get_api_details`**: Retrieves detailed metadata and policy configuration for a specific API.
- **`transfer_api`**: Triggers an API migration between nodes via `transfer.py` with complete stdout redirection for clean JSON-RPC protocol handling.

---

## ⚙️ Registration & Setup

To enable the `apimops` MCP Server in your LLM client (e.g. Claude Desktop or VS Code / Cursor / Antigravity MCP settings), add the following entry to your `mcp_config.json`:

```json
{
  "mcpServers": {
    "apimops": {
      "command": "/path/to/apimops/scripts/setup/.venv/bin/python",
      "args": [
        "/path/to/apimops/scripts/mcp_server.py"
      ],
      "env": {
        "APIMOPSCONFIG": "/path/to/apimops/config.yaml"
      }
    }
  }
}
```

---

## 🔒 Isolation & Safety

The MCP server is **100% optional** and isolated from the core CLI tools. `transfer.py` and standalone binaries (`transfer.exe`, `transfer`) remain fully operational without installing or running the MCP server.
