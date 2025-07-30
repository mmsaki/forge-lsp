"""
Remapping resolver for Foundry projects.

This module extracts remappings and file information from forge build output
to enable proper import resolution for LSP features like go-to-definition,
references, and intelligent completions.
"""

import json
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
import logging

logger = logging.getLogger(__name__)


class RemappingResolver:
    """Resolves import paths using Foundry's remapping system."""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.remappings: Dict[str, str] = {}
        self.file_cache: Dict[str, Dict] = {}
        self.source_id_to_path: Dict[str, str] = {}
        self.path_to_source_id: Dict[str, str] = {}
        self._load_remappings()
        self._load_cache()

    def _load_remappings(self) -> None:
        """Load remappings from forge remappings command."""
        try:
            result = subprocess.run(
                ["forge", "remappings"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                check=True,
            )

            for line in result.stdout.strip().split("\n"):
                if "=" in line:
                    prefix, path = line.split("=", 1)
                    self.remappings[prefix] = path
                    logger.debug(f"Loaded remapping: {prefix} -> {path}")

        except subprocess.CalledProcessError as e:
            logger.warning(f"Failed to get remappings: {e}")
        except Exception as e:
            logger.error(f"Error loading remappings: {e}")

    def _load_cache(self) -> None:
        """Load file cache and build info from forge build output."""
        cache_file = self.project_root / "cache" / "solidity-files-cache.json"

        if cache_file.exists():
            try:
                with open(cache_file, "r") as f:
                    cache_data = json.load(f)
                    self.file_cache = cache_data.get("files", {})
                    logger.info(f"Loaded {len(self.file_cache)} files from cache")
            except Exception as e:
                logger.error(f"Error loading cache: {e}")

        # Load build info for source ID mappings
        build_info_dir = self.project_root / "out" / "build-info"
        if build_info_dir.exists():
            for build_file in build_info_dir.glob("*.json"):
                try:
                    with open(build_file, "r") as f:
                        build_data = json.load(f)
                        source_mapping = build_data.get("source_id_to_path", {})
                        self.source_id_to_path.update(source_mapping)
                        # Create reverse mapping
                        for source_id, path in source_mapping.items():
                            self.path_to_source_id[path] = source_id
                        logger.debug(
                            f"Loaded {len(source_mapping)} source mappings from {build_file.name}"
                        )
                except Exception as e:
                    logger.error(f"Error loading build info from {build_file}: {e}")

    def resolve_import(
        self, import_path: str, from_file: Optional[str] = None
    ) -> Optional[Path]:
        """
        Resolve an import path to an absolute file path.

        Args:
            import_path: The import path from Solidity code (e.g., "forge-std/Test.sol")
            from_file: The file containing the import (for relative imports)

        Returns:
            Absolute path to the imported file, or None if not found
        """
        # Handle relative imports
        if import_path.startswith("./") or import_path.startswith("../"):
            if from_file:
                from_path = Path(from_file).parent
                resolved = (from_path / import_path).resolve()
                if resolved.exists():
                    return resolved
            return None

        # Try remapping resolution
        for prefix, mapped_path in self.remappings.items():
            if import_path.startswith(prefix):
                relative_path = import_path[len(prefix) :]
                if relative_path.startswith("/"):
                    relative_path = relative_path[1:]

                # Try absolute path first
                if Path(mapped_path).is_absolute():
                    resolved = Path(mapped_path) / relative_path
                else:
                    resolved = self.project_root / mapped_path / relative_path

                if resolved.exists():
                    return resolved.resolve()

        # Try direct resolution from project root
        direct_path = self.project_root / import_path
        if direct_path.exists():
            return direct_path.resolve()

        # Try common library paths
        for lib_dir in ["lib", "node_modules"]:
            lib_path = self.project_root / lib_dir / import_path
            if lib_path.exists():
                return lib_path.resolve()

        logger.debug(f"Could not resolve import: {import_path}")
        return None

    def get_file_imports(self, file_path: str) -> List[str]:
        """Get all imports for a given file from the cache."""
        # Normalize path for cache lookup
        rel_path = str(Path(file_path).relative_to(self.project_root))

        if rel_path in self.file_cache:
            return self.file_cache[rel_path].get("imports", [])

        return []

    def get_file_dependencies(self, file_path: str) -> Set[Path]:
        """Get all file dependencies (transitive imports) for a given file."""
        dependencies = set()
        to_process = [file_path]
        processed = set()

        while to_process:
            current = to_process.pop()
            if current in processed:
                continue
            processed.add(current)

            imports = self.get_file_imports(current)
            for import_path in imports:
                resolved = self.resolve_import(import_path, current)
                if resolved:
                    dependencies.add(resolved)
                    to_process.append(str(resolved))

        return dependencies

    def get_all_solidity_files(self) -> List[Path]:
        """Get all Solidity files in the project."""
        files = []

        # From cache
        for file_path in self.file_cache.keys():
            full_path = self.project_root / file_path
            if full_path.exists():
                files.append(full_path)

        # Also scan common directories
        for pattern in [
            "src/**/*.sol",
            "test/**/*.sol",
            "script/**/*.sol",
            "lib/**/*.sol",
        ]:
            files.extend(self.project_root.glob(pattern))

        return list(set(files))  # Remove duplicates

    def find_symbol_definition(
        self, symbol: str, symbol_type: Optional[str] = None
    ) -> List[Tuple[Path, int]]:
        """
        Find the definition of a symbol across all project files.

        Args:
            symbol: The symbol name to find
            symbol_type: Optional type hint (contract, function, etc.)

        Returns:
            List of (file_path, line_number) tuples where the symbol is defined
        """
        definitions = []

        for file_path in self.get_all_solidity_files():
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()

                for line_num, line in enumerate(lines, 1):
                    # Simple pattern matching - can be enhanced with proper parsing
                    if self._is_symbol_definition(line, symbol, symbol_type):
                        definitions.append((file_path, line_num))

            except Exception as e:
                logger.debug(f"Error reading {file_path}: {e}")

        return definitions

    def _is_symbol_definition(
        self, line: str, symbol: str, symbol_type: Optional[str] = None
    ) -> bool:
        """Check if a line contains a symbol definition."""
        line = line.strip()

        # Contract definition
        if (
            f"contract {symbol}" in line
            or f"interface {symbol}" in line
            or f"library {symbol}" in line
        ):
            return True

        # Function definition
        if f"function {symbol}" in line:
            return True

        # Event definition
        if f"event {symbol}" in line:
            return True

        # Modifier definition
        if f"modifier {symbol}" in line:
            return True

        # Struct definition
        if f"struct {symbol}" in line:
            return True

        # Enum definition
        if f"enum {symbol}" in line:
            return True

        return False

    def refresh(self) -> None:
        """Refresh remappings and cache data."""
        logger.info("Refreshing remapping resolver")
        self.remappings.clear()
        self.file_cache.clear()
        self.source_id_to_path.clear()
        self.path_to_source_id.clear()

        self._load_remappings()
        self._load_cache()

    def get_completion_candidates(self, import_prefix: str) -> List[str]:
        """Get completion candidates for import statements."""
        candidates = []

        # Get candidates from remappings
        for prefix in self.remappings.keys():
            if prefix.startswith(import_prefix):
                candidates.append(prefix)

        # Get candidates from file system
        try:
            if "/" in import_prefix:
                # Resolve partial path
                parts = import_prefix.split("/")
                base_path = "/".join(parts[:-1])
                prefix = parts[-1]

                resolved_base = self.resolve_import(base_path + "/")
                if resolved_base and resolved_base.is_dir():
                    for item in resolved_base.iterdir():
                        if item.name.startswith(prefix) and item.suffix == ".sol":
                            candidates.append(f"{base_path}/{item.name}")
            else:
                # Look in common directories
                for lib_dir in ["lib", "src", "test", "script"]:
                    lib_path = self.project_root / lib_dir
                    if lib_path.exists():
                        for item in lib_path.iterdir():
                            if item.name.startswith(import_prefix):
                                if item.is_dir():
                                    candidates.append(f"{item.name}/")
                                elif item.suffix == ".sol":
                                    candidates.append(item.name)

        except Exception as e:
            logger.debug(f"Error getting completion candidates: {e}")

        return sorted(list(set(candidates)))
