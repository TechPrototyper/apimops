# apimops Corporate Admin & Operations Guide

This guide is designed for SysAdmins, DevOps Engineers, and Enterprise Platform Admins deploying and operating **apimops** in corporate, zero-trust, or heavily managed environments.

---

## 1. Overview & Architecture

`apimops` provides automated synchronization, migration, and publishing for Microsoft Azure API Management (APIM) instances. It is fully compatible with **Microsoft APIOps v6.0.2** (April 2026 baseline).

### Key Design Principles for Corporate Environments
- **Zero-Trust Ready:** All sensitive credentials (Azure Service Principals, GitHub Access Tokens, LLM API Keys) are injected securely via write-only GitHub Actions Secrets or isolated local configurations.
- **No Local Python Runtime Required:** Standalone executables (`transfer.exe`, `setup.exe` on Windows; `transfer`, `setup` on macOS/Linux) bundle Python and all dependencies into self-contained binaries.
- **Idempotent & Auditable:** Migrations create traceable Git commits and GitHub Pull Requests for audit compliance before deploying to target Azure environments.

---

## 2. Standalone Binaries & Deployment Location

In restricted corporate Windows workstations where installing Python or package managers is prohibited, pre-compiled standalone executables are used.

### Recommended Deployment Location
To satisfy AppLocker, Software Restriction Policies (SRP), and user privilege boundaries, place `transfer.exe`, `setup.exe`, and `config.yaml` directly within the user's home profile directory:

```cmd
C:\Users\%USERNAME%\apimops\
├── transfer.exe
├── setup.exe
└── config.yaml
```

### Runtime Prerequisites & Requirements
Although no Python installation is required on target Windows machines, the following runtime dependencies must be present:

1. **Git for Windows (`git.exe`):**  
   Must be installed and present in the user's PATH (or standard location `C:\Program Files\Git\cmd\git.exe`). `transfer.exe` uses `git` for local changeset branch operations, cloning, diffing, and merging.
2. **Outbound HTTPS Access (Port 443):**  
   Workstations require outbound network access to:
   - `github.com` and `api.github.com` (GitHub API & repository operations)
   - `management.azure.com` (Azure APIM Management REST APIs)
3. **Write Permissions in Execution Directory:**  
   The execution folder (`C:\Users\%USERNAME%\apimops\`) must allow temporary directory creation (`source_repo`, `temp_data_repo`), which are cleaned up automatically upon completion.

### Linux Distributions & Binary Compatibility

Pre-compiled Linux binaries created by `apimops` are standard **ELF executables** targeting standard `glibc` environments:

- **Supported Linux Distributions:**  
  - **Debian / Ubuntu:** Tested and verified on Ubuntu 24.04 / 22.04 and Debian 11/12.
  - **openSUSE / SUSE Linux Enterprise (SLES):** Full compatibility with Leap, Tumbleweed, and SLES.
  - **RHEL / Fedora / AlmaLinux / Rocky Linux:** Full compatibility with glibc 2.28+.
- **Runtime Prerequisites for Linux:**
  - **Git (`git`):** Must be installed via package manager (`apt install git` on Debian/Ubuntu, `zypper install git` on SUSE, `dnf install git` on RHEL/Fedora).
  - **GLIBC (GNU C Library):** Standard on virtually all enterprise Linux distributions.
  - **Outbound HTTPS Access (Port 443):** Access to GitHub and Azure APIM.

---

### Pre-compiled Executables
- `transfer.exe` / `transfer`: Main migration CLI tool.
- `setup.exe` / `setup`: Environment initialization and GitHub Secrets provisioning tool.

### Building Binaries from Source
To build native binaries for your OS platform:

```bash
# Build all binaries (detects Windows / macOS / Linux automatically)
python3 build/build_all.py

# Windows Native Build (Run in CMD or PowerShell)
build\build_win.bat

# macOS Native Build
bash build/build_mac.sh
```
Outputs are written to `build/dist/` or `~/apimops_build/dist/`.

---

## 3. Zero-Trust Security & Onboarding Architecture

To meet zero-trust compliance standards in corporate environments, `apimops` separates **local workstation operations** from **cloud-based CI/CD pipeline execution**:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          LOCAL ADMIN WORKSTATION                            │
│                                                                             │
│   ┌───────────────────────┐                                                 │
│   │ config.template.yaml  │ ──► [Admin edits] ──► ┌──────────────────┐      │
│   └───────────────────────┘                       │   config.yaml    │      │
│                                                   │ (NEVER COMMITTED)│      │
│                                                   └────────┬─────────┘      │
│                                                            │                │
│                                              [Reads local cleartext config] │
│                                                            ▼                │
│                                                   ┌──────────────────┐      │
│                                                   │    setup.exe     │      │
│                                                   └────────┬─────────┘      │
└────────────────────────────────────────────────────────────┼────────────────┘
                                                             │
                      [Provisions via GitHub REST API]       │
                                                             ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          GITHUB CLOUD REPOSITORIES                          │
│                                                                             │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │ GitHub Repository & Environment Secrets                             │   │
│   │   • AZURE_CLIENT_ID           • AZURE_CLIENT_SECRET                 │   │
│   │   • AZURE_TENANT_ID           • AZURE_SUBSCRIPTION_ID               │   │
│   │   • AZURE_RESOURCE_GROUP_NAME • GH_APIMDATA_TOKEN                   │   │
│   │   • GH_APIMOPS_TOKEN          • AI_API_KEY                          │   │
│   ├─────────────────────────────────────────────────────────────────────┤   │
│   │ GitHub Repository Variables                                         │   │
│   │   • APIOPS_RELEASE_VERSION    • API_SPECIFICATION_FORMAT            │   │
│   │   • AI_ENDPOINT               • AI_MODEL                            │   │
│   └──────────────────────────────────┬──────────────────────────────────┘   │
│                                      │                                      │
│                     [Injected at workflow runtime]                          │
│                                      ▼                                      │
│                   ┌──────────────────────────────────────┐                  │
│                   │   GitHub Actions Workflows (Cloud)   │                  │
│                   │ (Operates 100% WITHOUT config.yaml!) │                  │
│                   └──────────────────────────────────────┘                  │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Key Security Guarantee: `config.yaml` Isolation
- **Local-Only File:** `config.yaml` contains local credentials and is permanently ignored via `.gitignore`. It is **never** pushed to remote Git repositories.
- **Workflow Independence:** GitHub Actions workflows (`update_repo.yaml`, `update_service_publisher.yaml`) running on GitHub Cloud runners do not expect or require `config.yaml`. All required inputs are injected via write-only GitHub Secrets and Repository Variables.
---

## 4. Step-by-Step Onboarding Walkthrough for Third-Party & Enterprise Customers

When a new organization, partner, or third-party enterprise customer starts from scratch with zero pre-existing repositories:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                   STEP 1: FORK / CLONE OPERATIONS REPOSITORY               │
│                                                                             │
│   Fork or clone `apimops` into your enterprise GitHub Org / GHES:           │
│   `https://github.your-company.com/my-org/apimops.git`                       │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                   STEP 2: CREATE LOCAL `config.yaml`                        │
│                                                                             │
│   Copy `config.template.yaml` -> `config.yaml` and configure:               │
│   • GitHub Operations Repo URL & Token (`github_solution`)                  │
│   • Target Data Repo URL (`github_data` - e.g. `my-org/apimdata`)            │
│   • Azure SP Credentials & Subscription IDs (`azure_default`)               │
│   • Target APIM Nodes (`apim_services`: DEV, TEST, PROD)                    │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                   STEP 3: RUN AUTOMATED `setup.exe`                         │
│                                                                             │
│   Execute `setup.exe` (Windows) or `./setup` (Linux/macOS) once.            │
│   `setup` automatically:                                                    │
│   1. Connects to GitHub (supports GitHub Enterprise Server URLs).           │
│   2. Auto-creates the private Data Repository (`apimdata`) if missing.      │
│   3. Creates APIM node branches (`DEV`, `PROD`, etc.) in `apimdata`.        │
│   4. Provisions all GitHub Secrets & Variables in both repositories.        │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                   STEP 4: READY FOR API MIGRATIONS                          │
│                                                                             │
│   Run `transfer.exe --source DEV --destination PROD --api my-api`           │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Configuration Management (`config.yaml`)

Tools search for `config.yaml` in the following strict priority order:

1. **CLI Parameter (Highest Priority):** `--config /path/to/custom-config.yaml`
2. **Environment Variable:** Path set in `$APIMOPSCONFIG`
3. **Current Working Directory:** `./config.yaml`
4. **Script Root Directory:** Two directories above the script executable

### Template Configuration Structure (`config.template.yaml`)
```yaml
general:
  apiops:
    release_version: "6.0.2"
    specification_format: "OpenAPIV3Yaml"

  github_solution:
    repo: "apimops"
    url: "https://github.com/your-org/apimops.git"
    token: "<GITHUB_PAT_TOKEN>"

  github_data:
    repo: "apimdata"
    url: "https://github.com/your-org/apimdata.git"
    token: "<GITHUB_PAT_TOKEN>"

  azure_default:
    tenant_id: "<AZURE_TENANT_ID>"
    subscription_id: "<AZURE_SUBSCRIPTION_ID>"
    resource_group: "rg-apim-dev-01"
    sp_client_id: "<AZURE_CLIENT_ID>"
    sp_client_secret: "<AZURE_CLIENT_SECRET>"

  ai_assistant:
    provider: "grok" # grok, github_models, azure_openai, local
    endpoint: "https://api.x.ai/v1/chat/completions"
    api_key: "<XAI_API_KEY>"
    model: "grok-build-0.1"

apim_services:
  DEV-APIM-SERVICE:
    name: "Development APIM Instance"
  STAGE-APIM-SERVICE:
    name: "Staging APIM Instance"
  PROD-APIM-SERVICE:
    name: "Production APIM Instance"
```

---

## 4. Setup & Secrets Provisioning

Before executing transfers for the first time, run `setup` (or `setup.exe`). This script verifies connectivity to Azure APIM nodes and populates GitHub Secrets in the Data Repository:

```bash
# macOS / Linux
./setup

# Windows CMD / PowerShell
setup.exe
```

### Managed GitHub Secrets Created
- `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`, `AZURE_RESOURCE_GROUP_NAME`
- `GH_APIMDATA_TOKEN`, `GH_APIMDATA_URL`, `GH_APIMDATA_REPO`
- `AI_API_KEY`, `AI_ENDPOINT`, `AI_MODEL`

---

## 5. Migration CLI Reference (`transfer`)

### Command-Line Arguments
| Option | Short | Description |
|---|---|---|
| `--config` | `-cfg` | Path to custom `config.yaml` file |
| `--source` | `-src` | Source APIM node name (e.g. `DEV-APIM-SERVICE`) |
| `--destination` | `-dst` | Target APIM node name (e.g. `PROD-APIM-SERVICE`) |
| `--api` | `-a` | Name of a single API artifact to transfer |
| `--apis` | `-as` | Comma-separated list of API artifacts |
| `--products` | `-prod` | Comma-separated list of Product artifacts |
| `--pullrequest` | `-pr` | Create a GitHub Pull Request instead of direct merge |
| `--backup` | `-b` | Backup current target state before transfer |
| `--verbose` | `-v` | Enable detailed console output |

### Common Operational Examples

#### 1. Transfer a Single API directly to Target APIM:
```bash
transfer --source DEV-APIM-SERVICE --destination PROD-APIM-SERVICE --api echo-api --verbose
```

#### 2. Transfer via Pull Request for Governance Review:
```bash
transfer --source DEV-APIM-SERVICE --destination PROD-APIM-SERVICE --api customer-service --pullrequest --verbose
```

#### 3. Transfer Multiple APIs with Backup:
```bash
transfer --source DEV-APIM-SERVICE --destination PROD-APIM-SERVICE --apis weather-api,orders-api --backup --verbose
```

---

## 6. AI Assistant Commitment Logging

`apimops` integrates automatic commit message generation for Git diffs using any standard **OpenAI-compatible ChatCompletions API endpoint (`/chat/completions`)** (such as Azure OpenAI, GitHub Models, or local LLMs like Ollama or vLLM).

- **Endpoint Format:** `https://your-api-endpoint/v1/chat/completions`
- **Behavior:** Reads staged git diffs, produces concise 1-line commit messages adhering to standard Git conventions, and falls back to a timestamped message if the LLM endpoint is unreachable.

---

## 7. Performance & Packaging Notes

### Single-File Binary vs Directory Mode
- **Single-File (`--onefile`):** Decompresses runtime dependencies to `/tmp/_MEIXXXXXX` on each run. Expect 2–4s unpacking overhead per invocation. Ideal for single-file distribution to locked-down workstations.
- **Directory Mode (`--onedir`):** Decompresses binaries once at build time into a directory folder (`transfer/_internal/`). Execution is instant (< 0.2 seconds). Recommended for servers or automated build pipelines.
