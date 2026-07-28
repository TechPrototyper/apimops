# apimops

A handy, lightweight helper utility for managing, synchronizing, and migrating Azure API Management (APIM) instances and related artifacts across environments.

> **Note on Origin:**  
> `apimops` originally originated during a broader corporate client engagement between **late 2023 and spring 2024** by **Tim Walter** to streamline APIM deployment workflows in strictly managed enterprise environments. It was recently refactored, modernized, and updated to align with **Microsoft APIOps v6.0.2** (April 2026) for public release as an open-source helper tool.

> ⚠️ **Status Note (Permanent Beta):**  
> `apimops` is provided in a permanent **Beta** stage. Single API migration (`transfer --api <name>`) has been exhaustively tested and verified in production environments. Not all feature permutations (such as multi-artifact bulk transfers or rollback routines) have been fully tested.

---

## 🎯 Purpose & Scope

`apimops` is a small, pragmatic helper tool designed to simplify DevOps workflows and multi-environment migrations (e.g. `DEV` → `STAGING` → `PROD`) for Azure API Management. 

Rather than replacing official tools, `apimops` acts as an orchestration glue layer that connects local CLI commands, Git repositories, and GitHub Actions workflows with Microsoft's official APIOps Publisher & Extractor binaries.

---

## 🔄 Pipeline Overview

The standard migration pipeline consists of four main steps:

```
┌──────────────┐     ┌────────────────┐     ┌────────────────┐     ┌────────────────┐
│  1. Setup    │ ──> │ 2. Extraction  │ ──> │  3. Transfer   │ ──> │ 4. Publisher   │
│ (setup.py)   │     │ (GitHub Action)│     │ (transfer.py)  │     │ (APIOps v6)    │
└──────────────┘     └────────────────┘     └────────────────┘     └────────────────┘
```

1. **Setup (`setup.py` / `setup.exe`):**  
   Initializes the environment, validates `config.yaml`, checks Azure and GitHub connectivity, and securely provisions required GitHub Secrets and Variables in the Data Repository.

2. **Extraction (`update_repo.yaml`):**  
   Extracts APIs, policies, products, and configurations from a source Azure APIM instance into the Git Data Repository (`apimdata`).

3. **Transfer (`transfer.py` / `transfer.exe`):**  
   Migrates specific APIs or complete artifact sets between APIM environment branches (e.g., `DEV-APIM-SERVICE` → `PROD-APIM-SERVICE`). Automatically resolves dependency objects (Products, NamedValues, Backends), creates changesets, and merges them (or opens a Pull Request).

4. **Commit & Publish (`update_service.yaml`):**  
   Triggers Microsoft's native APIOps Publisher v6.0.2 to apply committed changes directly to the target Azure APIM instance.

---

## 💻 CLI Usage Examples

You can run `transfer` either as a Python script or as a standalone pre-compiled executable (`transfer.exe` on Windows, `transfer` on macOS/Linux).

### 1. Transfer a Single API (Direct Merge & Deploy)
```bash
transfer --source DEV-APIM-SERVICE --destination PROD-APIM-SERVICE --api my-api-name --verbose
```
*Short form:*
```bash
transfer -src DEV-APIM-SERVICE -dst PROD-APIM-SERVICE -a my-api-name -v
```

### 2. Transfer an API via GitHub Pull Request (Governance Mode)
```bash
transfer --source DEV-APIM-SERVICE --destination PROD-APIM-SERVICE --api my-api-name --pullrequest --verbose
```

### 3. Transfer Multiple APIs at once
```bash
transfer --source DEV-APIM-SERVICE --destination PROD-APIM-SERVICE --apis api1,api2,api3 --verbose
```

### 4. Transfer using a Microsoft APIOps Extractor Configuration File
```bash
transfer --source DEV-APIM-SERVICE --destination PROD-APIM-SERVICE --transferset configuration.extractor.yaml --verbose
```

---

## ⚙️ Configuration (`config.yaml`)

`apimops` uses a central `config.yaml` to define Azure subscriptions, resource groups, Service Principals, GitHub repos, and APIM service nodes.

The configuration file is searched in the following priority order:
1. Path provided via `--config` / `-cfg` argument
2. Directory path in `$APIMOPSCONFIG` environment variable
3. Current working directory (`./config.yaml`)
4. Parent directories relative to the executable

See [`config.template.yaml`](file:///Users/timw/Projects/apimops/config.template.yaml) for a clean configuration template with placeholders.

> 📘 **Enterprise & Corporate Admins:**  
> For detailed instructions on running `apimops` in zero-trust, locked-down corporate Windows environments, read the [Corporate Admin Guide](file:///Users/timw/Projects/apimops/docs/CORPORATE_ADMIN_GUIDE.md).

---

## 📌 Microsoft APIOps v6.0.2 Compatibility

This project natively uses **Microsoft APIOps v6.0.2** (April 2026 baseline).

| Scenario | How It Works |
|---|---|
| **Deploy last commit** | `COMMIT_ID` = `HEAD^` → Publisher diffs `HEAD^` vs its parent |
| **Deploy specific commit** | `COMMIT_ID` = `<sha>` → Publisher diffs `<sha>` vs its parent |
| **Force full deploy** | No `COMMIT_ID` set → Publisher deploys all artifacts |

*No custom source patches required.* Native Microsoft Publisher binaries (`linux-x64`, `win-x64`, `osx-x64`, `osx-arm64`) are used directly.

---

## 🤖 AI Commit Message Generation

`apimops` includes an automated commit message generator for Git diffs, supporting any standard **OpenAI-compatible ChatCompletions API endpoint (`/chat/completions`)**:
- Supports any OpenAI-compatible API provider (Azure OpenAI, GitHub Models, or Custom/Local LLMs like Ollama or vLLM).
- Generates concise single-line Git commit messages based on staged changes.

Configured under `ai_assistant` in `config.yaml` and provisioned automatically via `setup.py` as GitHub Secrets (`AI_API_KEY`) and Variables (`AI_ENDPOINT`, `AI_MODEL`).

---

## 📦 Building Standalone Executables

For corporate environments where Python cannot be installed on target machines:

```bash
# Build for current platform using PyInstaller
python3 build/build_all.py

# Windows Native Build
build\build_win.bat

# macOS Native Build
bash build/build_mac.sh
```

Binaries are generated in `build/dist/` or `~/apimops_build/dist/`.

> 💡 **Windows Deployment Note:**  
> Place `transfer.exe`, `setup.exe`, and `config.yaml` inside the user's profile folder (`C:\Users\%USERNAME%\apimops\`). Ensure **Git for Windows** (`git.exe`) is installed and available in PATH. No local Python runtime is required.

---

## 🔌 Optional Model Context Protocol (MCP) Server

`apimops` includes an optional, standalone MCP Server ([`scripts/mcp_server.py`](file:///Users/timw/Projects/apimops/scripts/mcp_server.py)) that enables AI agents to list nodes, search APIs, inspect metadata, and execute transfers directly.

> For setup and configuration instructions, see the [MCP Server Guide](file:///Users/timw/Projects/apimops/docs/MCP_SERVER_GUIDE.md).

---

## 🛠 Project Structure

```
apimops/
├── LICENSE                          # MIT License (Tim Walter & Third-Party Notices)
├── config.template.yaml             # Configuration template with placeholders
├── docs/
│   └── CORPORATE_ADMIN_GUIDE.md    # Detailed guide for Enterprise & Corporate Admins
├── build/                           # PyInstaller build scripts & spec files
│   ├── build_all.py
│   ├── build_mac.sh
│   └── build_win.bat
├── scripts/
│   ├── setup/
│   │   └── setup.py                 # Environment init & GitHub Secrets provisioner
│   ├── transfer/
│   │   ├── transfer.py              # Main orchestrator CLI
│   │   └── modules/                 # Modularized transfer engine
│   └── asst/
│       └── commit_message.py        # LLM commit message generator
└── .github/
    └── workflows/                   # Actions workflows (update_repo, update_service)
```

---

## 📄 License & Attribution

This project is licensed under the **[MIT License](file:///Users/timw/Projects/apimops/LICENSE)** by **Tim Walter**.

- **Custom Extensions & Utility Code:** Copyright (c) 2023–2026 Tim Walter. Free to use, modify, and distribute with attribution.
- **Third-Party Components:** Inspired by and adapted from the open-source [Azure/apiops](https://github.com/Azure/apiops) project by Microsoft. Original Microsoft APIOps tools, workflows, and binaries remain subject to their respective upstream licenses (MIT License by Microsoft Corporation).
