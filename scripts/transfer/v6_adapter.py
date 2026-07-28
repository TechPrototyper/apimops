import os
import json
import re
from pathlib import Path
from typing import Set, List, Optional, Dict

class V6DependencyResolver:
    """
    Helper class to resolve dependencies (Backends, Tags, VersionSets, NamedValues)
    within an APIOps v6 artifact structure.
    
    APIOps v6 Structure typically looks like:
    /root
      /apis
        /my-api
          apiInformation.json
          policy.xml
          /operations
      /backends
        /my-backend
          backendInformation.json
      /namedValues
        /my-nv
          namedValueInformation.json
      /tags
        /my-tag
          tagInformation.json
      /apiVersionSets
        /my-vs
          apiVersionSetInformation.json
    """

    def __init__(self, root_dir: str):
        self.root_dir = Path(root_dir)

    def find_api_folder(self, api_name: str) -> Optional[Path]:
        """Finds the folder for a specific API."""
        # Typically under /apis/<api_name>
        candidate = self.root_dir / "apis" / api_name
        if candidate.exists() and candidate.is_dir():
            return candidate
        
        # Fallback: Search recursively if structure varies
        for path in self.root_dir.rglob(api_name):
            if path.is_dir() and "apis" in str(path.parent):
                return path
        return None

    def get_dependencies(self, api_path: Path) -> Dict[str, Set[Path]]:
        """
        Analyzes the API folder and returns a dictionary of dependency paths used.
        Keys: 'backends', 'namedValues', 'tags', 'versionSets', 'loggers', 'diagnostics'
        """
        dependencies = {
            "backends": set(),
            "namedValues": set(),
            "tags": set(),
            "versionSets": set(),
            "loggers": set(),
            "diagnostics": set()
        }

        # 1. Version Sets (from apiInformation.json)
        info_file = api_path / "apiInformation.json"
        if info_file.exists():
            try:
                data = json.loads(info_file.read_text(encoding='utf-8'))
                props = data.get("properties", {})
                vs_id = props.get("apiVersionSetId")
                if vs_id:
                    # ID format: .../apiVersionSets/<name>
                    vs_name = vs_id.split("/")[-1]
                    vs_path = self.find_global_artifact("apiVersionSets", vs_name)
                    if vs_path:
                        dependencies["versionSets"].add(vs_path)
            except Exception as e:
                print(f"Warning parsing {info_file}: {e}")

        # 2. Tags (Folders inside api path)
        # v6 often links tags inside the API folder, e.g. apis/myapi/tags/mytag.json
        # The actual tag definition is in /tags/mytag
        for tag_ref in api_path.rglob("tags/*.json"):
            tag_name = tag_ref.stem # filename without .json
            tag_def = self.find_global_artifact("tags", tag_name)
            if tag_def:
                dependencies["tags"].add(tag_def)

        # 3. Policy References (Backends & NamedValues)
        # Scan all XML files in the API folder (api policy + operation policies)
        backend_names = set()
        nv_names = set()

        for xml_file in api_path.rglob("*.xml"):
            try:
                content = xml_file.read_text(encoding='utf-8')
                # Backends: <set-backend-service backend-id="my-backend" ... />
                # Regex for backend-id="..."
                backend_names.update(re.findall(r'backend-id="([^"]+)"', content))
                
                # Named Values: {{my-value}}
                nv_names.update(re.findall(r'{{([^}]+)}}', content))
            except Exception:
                pass

        for be in backend_names:
            p = self.find_global_artifact("backends", be)
            if p: dependencies["backends"].add(p)
            
        for nv in nv_names:
            p = self.find_global_artifact("namedValues", nv)
            if p: dependencies["namedValues"].add(p)

        # 4. Diagnostics & Loggers
        # Diagnostics are usually subfolders: apis/myapi/diagnostics/applicationinsights
        diag_folder = api_path / "diagnostics"
        if diag_folder.exists():
            # The folder itself is part of the API, so we don't treat it as external dep,
            # BUT we need to parse it to find Loggers
            for diag_info in diag_folder.rglob("diagnosticInformation.json"):
                try:
                    data = json.loads(diag_info.read_text(encoding='utf-8'))
                    logger_id = data.get("properties", {}).get("loggerId")
                    if logger_id:
                        logger_name = logger_id.split("/")[-1]
                        logger_path = self.find_global_artifact("loggers", logger_name)
                        if logger_path:
                            dependencies["loggers"].add(logger_path)
                except Exception:
                    pass

        return dependencies

    def find_global_artifact(self, type_folder: str, name: str) -> Optional[Path]:
        """
        Finds a global artifact like /backends/my-backend.
        """
        # Direct check
        candidate = self.root_dir / type_folder / name
        if candidate.exists():
            return candidate
            
        # Recursive fallback
        for path in self.root_dir.rglob(name):
             if path.parent.name == type_folder:
                 return path
        return None
