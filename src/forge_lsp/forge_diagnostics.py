"""
Forge diagnostics integration for Solidity LSP.
Provides compilation errors and linting diagnostics from forge build and forge lint.
"""

import asyncio
import json
import logging
import re
import subprocess
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union, Any
from dataclasses import dataclass

from lsprotocol.types import Diagnostic, DiagnosticSeverity, Position, Range

logger = logging.getLogger(__name__)


def clean_ansi_sequences(text: str) -> str:
    """Remove ANSI escape sequences and other control characters from text."""
    if not text:
        return text
    
    # Remove ANSI escape sequences (colors, cursor movement, etc.)
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    text = ansi_escape.sub('', text)
    
    # Remove OSC (Operating System Command) sequences like \x1b]8;;url\x1b\\
    osc_escape = re.compile(r'\x1B\]8;;[^\x1B]*\x1B\\')
    text = osc_escape.sub('', text)
    
    # Remove any remaining control characters except newlines and tabs
    control_chars = re.compile(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]')
    text = control_chars.sub('', text)
    
    return text.strip()


@dataclass
class ForgeDiagnostic:
    """Represents a diagnostic from forge build or forge lint."""
    file_path: str
    line: int
    column: int
    message: str
    severity: DiagnosticSeverity
    code: Optional[str] = None
    source: str = "forge"
    help_url: Optional[str] = None
    category: str = "error"  # error, warning, note, help


class ForgeOutputParser:
    """Parses forge build and lint JSON output into diagnostics."""
    
    def parse_forge_compile_json_output(self, json_output: str, working_dir: str) -> List[ForgeDiagnostic]:
        """Parse forge JSON output into diagnostics."""
        diagnostics = []
        
        try:
            data = json.loads(json_output)
            
            # Parse errors from JSON
            if "errors" in data:
                for error in data["errors"]:
                    diagnostic = self._parse_json_error(error, working_dir)
                    if diagnostic:
                        diagnostics.append(diagnostic)
            
            return diagnostics
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse forge JSON output: {e}")
            # Fallback to text parsing
            return self._parse_text_output(json_output, working_dir)
    
    def _parse_json_error(self, error: Dict[str, Any], working_dir: str) -> Optional[ForgeDiagnostic]:
        """Parse a single error from JSON format."""
        try:
            source_location = error.get("sourceLocation", {})
            file_path = source_location.get("file", "")
            
            if not file_path:
                return None
            
            # Extract position information
            start_pos = source_location.get("start", -1)
            end_pos = source_location.get("end", -1)
            
            # Convert byte positions to line/column if needed
            line = 0
            column = 0
            
            # If we have formatted message, try to extract line/column from it
            formatted_message = error.get("formattedMessage", "")
            line_match = re.search(r'--> [^:]+:(\d+):(\d+)', formatted_message)
            if line_match:
                line = int(line_match.group(1)) - 1  # Convert to 0-based
                column = int(line_match.group(2)) - 1
            
            # Determine severity
            severity = DiagnosticSeverity.Error
            error_type = error.get("type", "").lower()
            severity_str = error.get("severity", "").lower()
            
            if error_type == "warning" or severity_str == "warning":
                severity = DiagnosticSeverity.Warning
            elif error_type == "info" or severity_str == "info":
                severity = DiagnosticSeverity.Information
            elif "note" in error_type.lower():
                severity = DiagnosticSeverity.Information
            
            # Determine source and category
            source = "forge-compile"
            category = "error"
            
            if "lint" in error.get("component", "").lower():
                source = "forge-lint"
                category = "lint"
            elif severity == DiagnosticSeverity.Warning:
                category = "warning"
            elif severity == DiagnosticSeverity.Information:
                category = "info"
            
            # Extract help URL from formatted message if it's a lint error
            help_url = None
            if "help:" in formatted_message:
                help_match = re.search(r'= help: (https?://[^\s]+)', formatted_message)
                if help_match:
                    help_url = help_match.group(1)
            
            return ForgeDiagnostic(
                file_path=self._resolve_file_path(file_path, working_dir),
                line=line,
                column=column,
                message=error.get("message", "").strip(),
                severity=severity,
                code=error.get("errorCode"),
                source=source,
                help_url=help_url,
                category=category
            )
            
        except Exception as e:
            logger.error(f"Error parsing JSON error: {e}")
            return None
    
    def _parse_text_output(self, output: str, working_dir: str) -> List[ForgeDiagnostic]:
        """Fallback text parsing for non-JSON output."""
        diagnostics = []
        
        # Parse lint notes from text output (these appear even with --format-json)
        lint_pattern = re.compile(
            r'note\[([^\]]+)\]: (.+?)\n.*?--> ([^:]+):(\d+):(\d+)(?:\n.*?= help: (https?://[^\s]+))?',
            re.MULTILINE | re.DOTALL
        )
        
        for match in lint_pattern.finditer(output):
            groups = match.groups()
            lint_code = groups[0]
            message = groups[1].strip()
            file_path = groups[2]
            line = int(groups[3]) - 1  # Convert to 0-based
            column = int(groups[4]) - 1
            help_url = groups[5] if len(groups) > 5 else None
            
            # Clean and format the message with [forge lint] prefix
            cleaned_message = clean_ansi_sequences(message)
            formatted_message = f"[forge lint] {cleaned_message}"
            
            diagnostics.append(ForgeDiagnostic(
                file_path=self._resolve_file_path(file_path, working_dir),
                line=line,
                column=column,
                message=formatted_message,
                severity=DiagnosticSeverity.Information,
                code=lint_code,
                source="forge-lint",
                help_url=help_url,
                category="lint"
            ))
        
        return diagnostics
    
    def parse_forge_lint_jsonc_output(self, jsonc_output: str, working_dir: str) -> List[ForgeDiagnostic]:
        """Parse forge lint JSONC output into diagnostics."""
        diagnostics = []
        
        # Forge lint outputs one JSON object per line (JSONC format)
        for line in jsonc_output.strip().split('\n'):
            if not line.strip():
                continue
                
            try:
                data = json.loads(line)
                
                if data.get("$message_type") == "diag":
                    diagnostic = self._parse_lint_jsonc_diag(data, working_dir)
                    if diagnostic:
                        diagnostics.append(diagnostic)
                        
            except json.JSONDecodeError as e:
                logger.debug(f"Failed to parse lint JSONC line: {e}")
                continue
        
        return diagnostics
    
    def _parse_lint_jsonc_diag(self, data: Dict[str, Any], working_dir: str) -> Optional[ForgeDiagnostic]:
        """Parse a single lint diagnostic from JSONC format."""
        try:
            message = data.get("message", "")
            level = data.get("level", "error")
            code_info = data.get("code", {})
            spans = data.get("spans", [])
            children = data.get("children", [])
            rendered = data.get("rendered", "")
            
            if not spans:
                return None
            
            # Get the primary span
            primary_span = None
            for span in spans:
                if span.get("is_primary", False):
                    primary_span = span
                    break
            
            if not primary_span:
                primary_span = spans[0]
            
            file_name = primary_span.get("file_name", "")
            line_start = primary_span.get("line_start", 1) - 1  # Convert to 0-based
            column_start = primary_span.get("column_start", 1) - 1
            
            # Determine severity based on lint level
            severity = DiagnosticSeverity.Information  # Most lint issues are informational
            if level == "error":
                severity = DiagnosticSeverity.Error
            elif level == "warning":
                severity = DiagnosticSeverity.Warning
            elif level == "note":
                severity = DiagnosticSeverity.Information
            elif level == "help":
                severity = DiagnosticSeverity.Hint
            
            # Extract code from lint diagnostic
            code = None
            if isinstance(code_info, dict):
                code = code_info.get("code")
            
            # Clean up the message and prepend [forge lint] as requested
            # If message is empty, try to extract from rendered field
            if not message and rendered:
                # Extract message from rendered field (format: "note[code]: message")
                rendered_clean = clean_ansi_sequences(rendered)
                # Look for pattern like "note[code]: actual message"
                import re
                match = re.match(r'note\[[^\]]+\]:\s*(.+?)(?:\n|$)', rendered_clean)
                if match:
                    message = match.group(1).strip()
                    logger.debug(f"Extracted message from rendered field: {repr(message)}")
            
            logger.debug(f"Original message: {repr(message)}")
            logger.debug(f"Code: {repr(code)}")
            if message:
                # Clean ANSI escape sequences from the original message
                cleaned_message = clean_ansi_sequences(message)
                logger.debug(f"Cleaned message: {repr(cleaned_message)}")
                # Prepend [forge lint] to the cleaned original message
                message = f"[forge lint] {cleaned_message}"
                logger.debug(f"Final message: {repr(message)}")
            elif code:
                # Fallback: if no message, create a more descriptive message based on the code
                # Map common lint codes to their descriptions
                lint_descriptions = {
                    "screaming-snake-case-const": "constants should use SCREAMING_SNAKE_CASE",
                    "mixed-case-function": "function names should use mixedCase",
                    "unused-import": "unused import",
                    "unaliased-plain-import": "plain imports should be aliased",
                    "unused-variable": "unused variable",
                    "unused-parameter": "unused parameter",
                    "dead-code": "unreachable code",
                    "style-guide-violation": "style guide violation"
                }
                
                descriptive_message = lint_descriptions.get(code, code.replace("-", " ").replace("_", " "))
                message = f"[forge lint] {descriptive_message}"
                logger.debug(f"Fallback message: {repr(message)}")
            else:
                logger.debug("No message and no code available")
            
            # Extract help URL from children (contains ANSI escape sequences)
            help_url = None
            for child in children:
                if child.get("level") == "help":
                    child_message = child.get("message", "")
                    # Clean ANSI escape sequences first, then extract URL
                    clean_message = clean_ansi_sequences(child_message)
                    # Look for URLs in the format https://... and clean up any trailing artifacts
                    url_match = re.search(r'https?://[^\s\x1b]+', clean_message)
                    if url_match:
                        # Clean up any remaining artifacts from the URL
                        url = url_match.group(0)
                        # Remove any trailing control characters or duplicated fragments
                        url = re.sub(r'[^\w\-\./:?#=&]+$', '', url)
                        # Remove duplicated URL fragments (common with ANSI sequences)
                        url_parts = url.split('https://')
                        if len(url_parts) > 2:
                            url = 'https://' + url_parts[1]
                        help_url = url
                    break
            
            return ForgeDiagnostic(
                file_path=self._resolve_file_path(file_name, working_dir),
                line=line_start,
                column=column_start,
                message=message,
                severity=severity,
                code=code,
                source="forge-lint",
                help_url=help_url,
                category="lint"
            )
            
        except Exception as e:
            logger.error(f"Error parsing lint JSONC diagnostic: {e}")
            return None
    
    def _resolve_file_path(self, file_path: str, working_dir: str) -> str:
        """Resolve relative file paths to absolute paths."""
        if os.path.isabs(file_path):
            return file_path
        
        # Try to resolve relative to working directory
        resolved = os.path.join(working_dir, file_path)
        if os.path.exists(resolved):
            return os.path.abspath(resolved)
        
        # If not found, return as-is (might be in a different location)
        return file_path


class ForgeRunner:
    """Runs forge commands and captures output."""
    
    def __init__(self, forge_path: str = "forge"):
        self.forge_path = forge_path
        self.parser = ForgeOutputParser()
        self._forge_version = None
        self._supports_lint = None
    
    def _get_forge_version(self) -> str:
        """Get forge version string."""
        if self._forge_version is None:
            try:
                result = subprocess.run(
                    [self.forge_path, "--version"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                self._forge_version = result.stdout.strip()
            except Exception as e:
                logger.warning(f"Failed to get forge version: {e}")
                self._forge_version = ""
        return self._forge_version
    
    def _supports_linting(self) -> bool:
        """Check if forge supports linting (nightly feature)."""
        if self._supports_lint is None:
            version = self._get_forge_version()
            # Check if it's a nightly version
            self._supports_lint = "nightly" in version.lower()
            logger.info(f"Forge version: {version}, supports linting: {self._supports_lint}")
        return self._supports_lint
    
    async def run_forge_compile(self, working_dir: str, file_path: str, use_cache: bool = True) -> List[ForgeDiagnostic]:
        """Run forge compile on a specific file and return diagnostics."""
        cmd = [self.forge_path, "compile", file_path, "--json"]
        
        # Add --no-cache flag when we want to ensure all warnings are shown (e.g., on save)
        if not use_cache:
            cmd.append("--no-cache")
        
        try:
            cache_info = "cached" if use_cache else "no-cache"
            logger.info(f"Running forge compile on {file_path} in {working_dir} ({cache_info})")
            result = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=working_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={**os.environ, "FOUNDRY_DISABLE_NIGHTLY_WARNING": "1"}
            )
            
            stdout, stderr = await result.communicate()
            json_output = stdout.decode('utf-8', errors='replace')
            jsonc_output = stderr.decode('utf-8', errors='replace')
            
            logger.debug(f"Forge compile JSON output: {json_output}")
            logger.debug(f"Forge compile JSONC output: {jsonc_output}")
            
            # Parse JSON output for compilation errors
            diagnostics = self.parser.parse_forge_compile_json_output(json_output, working_dir)
            
            # Parse JSONC output for linting errors (from stderr) - only if forge supports linting
            if self._supports_linting() and jsonc_output.strip():
                lint_diagnostics = self.parser.parse_forge_lint_jsonc_output(jsonc_output, working_dir)
                diagnostics.extend(lint_diagnostics)
            
            return diagnostics
            
        except Exception as e:
            logger.error(f"Error running forge compile on {file_path}: {e}")
            return []
    
    async def run_forge_lint(self, working_dir: str, file_path: str) -> List[ForgeDiagnostic]:
        """Run forge lint on a specific file and return lint diagnostics."""
        cmd = [self.forge_path, "lint", file_path, "--json"]
        
        try:
            logger.info(f"Running forge lint on {file_path} in {working_dir}")
            result = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=working_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={**os.environ, "FOUNDRY_DISABLE_NIGHTLY_WARNING": "1"}
            )
            
            stdout, stderr = await result.communicate()
            # Lint output goes to stderr in JSONC format
            jsonc_output = stderr.decode('utf-8', errors='replace')
            
            logger.debug(f"Forge lint JSONC output: {jsonc_output}")
            
            return self.parser.parse_forge_lint_jsonc_output(jsonc_output, working_dir)
            
        except Exception as e:
            logger.error(f"Error running forge lint: {e}")
            return []
    
    def run_forge_compile_sync(self, working_dir: str, file_path: str, use_cache: bool = True) -> List[ForgeDiagnostic]:
        """Synchronous version of run_forge_compile."""
        cmd = [self.forge_path, "compile", file_path, "--json"]
        
        # Add --no-cache flag when we want to ensure all warnings are shown (e.g., on save)
        if not use_cache:
            cmd.append("--no-cache")
        
        try:
            cache_info = "cached" if use_cache else "no-cache"
            logger.info(f"Running forge compile (sync) on {file_path} in {working_dir} ({cache_info})")
            result = subprocess.run(
                cmd,
                cwd=working_dir,
                capture_output=True,
                text=True,
                env={**os.environ, "FOUNDRY_DISABLE_NIGHTLY_WARNING": "1"}
            )
            
            json_output = result.stdout
            jsonc_output = result.stderr
            
            logger.debug(f"Forge compile JSON output: {json_output}")
            logger.debug(f"Forge compile JSONC output: {jsonc_output}")
            
            # Parse JSON output for compilation errors
            diagnostics = self.parser.parse_forge_compile_json_output(json_output, working_dir)
            
            # Parse JSONC output for linting errors (from stderr) - only if forge supports linting
            if self._supports_linting() and jsonc_output.strip():
                lint_diagnostics = self.parser.parse_forge_lint_jsonc_output(jsonc_output, working_dir)
                diagnostics.extend(lint_diagnostics)
            
            return diagnostics
            
        except Exception as e:
            logger.error(f"Error running forge compile on {file_path}: {e}")
            return []


class ForgeDiagnosticsProvider:
    """Provides forge-based diagnostics for Solidity files."""
    
    def __init__(self, forge_path: str = "forge"):
        self.forge_runner = ForgeRunner(forge_path)
        self.diagnostics_cache: Dict[str, List[Diagnostic]] = {}
        self.last_build_time: Dict[str, float] = {}
    
    def get_project_root(self, file_path: str) -> Optional[str]:
        """Find the project root by looking for foundry.toml."""
        current_dir = Path(file_path).parent if os.path.isfile(file_path) else Path(file_path)
        
        while current_dir != current_dir.parent:
            if (current_dir / "foundry.toml").exists():
                return str(current_dir)
            current_dir = current_dir.parent
        
        return None
    
    def get_diagnostics_for_file(self, file_path: str) -> List[Diagnostic]:
        """Get forge diagnostics for a specific file."""
        project_root = self.get_project_root(file_path)
        if not project_root:
            logger.warning(f"No foundry.toml found for {file_path}")
            return []
        
        # Check if we need to rebuild
        file_uri = f"file://{os.path.abspath(file_path)}"
        file_mtime = os.path.getmtime(file_path) if os.path.exists(file_path) else 0
        
        if (file_uri in self.last_build_time and 
            self.last_build_time[file_uri] >= file_mtime and
            file_uri in self.diagnostics_cache):
            return self.diagnostics_cache[file_uri]
        
        # Run forge compile on the specific file
        relative_path = os.path.relpath(file_path, project_root)
        forge_diagnostics = self.forge_runner.run_forge_compile_sync(project_root, relative_path)
        
        # Convert to LSP diagnostics and group by file
        diagnostics_by_file: Dict[str, List[Diagnostic]] = {}
        
        for forge_diag in forge_diagnostics:
            diag_file_uri = f"file://{os.path.abspath(forge_diag.file_path)}"
            
            diagnostic = Diagnostic(
                range=Range(
                    start=Position(line=forge_diag.line, character=forge_diag.column),
                    end=Position(line=forge_diag.line, character=forge_diag.column + 1)
                ),
                message=forge_diag.message,
                severity=forge_diag.severity,
                code=forge_diag.code,
                source=forge_diag.source
            )
            
            # Add help URL as additional data
            if forge_diag.help_url:
                diagnostic.data = {"help_url": forge_diag.help_url}
            
            if diag_file_uri not in diagnostics_by_file:
                diagnostics_by_file[diag_file_uri] = []
            diagnostics_by_file[diag_file_uri].append(diagnostic)
        
        # Update cache
        self.diagnostics_cache.update(diagnostics_by_file)
        self.last_build_time[file_uri] = file_mtime
        
        return diagnostics_by_file.get(file_uri, [])
    
    async def get_diagnostics_for_file_async(self, file_path: str, use_cache: bool = True) -> List[Diagnostic]:
        """Async version of get_diagnostics_for_file."""
        project_root = self.get_project_root(file_path)
        if not project_root:
            logger.warning(f"No foundry.toml found for {file_path}")
            return []
        
        # Run forge compile which now includes both compilation and linting diagnostics
        relative_path = os.path.relpath(file_path, project_root)
        forge_diagnostics = await self.forge_runner.run_forge_compile(project_root, relative_path, use_cache)
        
        # Convert to LSP diagnostics - always return diagnostics for the current file
        diagnostics = []
        
        for forge_diag in forge_diagnostics:
            # Check if this diagnostic is for the current file or any file (to catch import errors etc.)
            diag_file_path = os.path.abspath(forge_diag.file_path)
            current_file_path = os.path.abspath(file_path)
            
            # Always include diagnostics for the current file
            # Also include diagnostics that don't have a specific file (general errors)
            if diag_file_path == current_file_path or not forge_diag.file_path:
                diagnostic = Diagnostic(
                    range=Range(
                        start=Position(line=forge_diag.line, character=forge_diag.column),
                        end=Position(line=forge_diag.line, character=forge_diag.column + 1)
                    ),
                    message=forge_diag.message,
                    severity=forge_diag.severity,
                    code=forge_diag.code,
                    source=forge_diag.source
                )
                
                if forge_diag.help_url:
                    diagnostic.data = {"help_url": forge_diag.help_url}
                
                diagnostics.append(diagnostic)
        
        return diagnostics
    
    def get_project_diagnostics(self, project_root: str) -> Dict[str, List[Diagnostic]]:
        """Get diagnostics for all files in a project."""
        # For project diagnostics, we still compile the whole project
        # This method is used for getting all diagnostics, not file-specific ones
        forge_diagnostics = self.forge_runner.run_forge_compile_sync(project_root, ".")
        
        diagnostics_by_file: Dict[str, List[Diagnostic]] = {}
        
        for forge_diag in forge_diagnostics:
            file_uri = f"file://{os.path.abspath(forge_diag.file_path)}"
            
            diagnostic = Diagnostic(
                range=Range(
                    start=Position(line=forge_diag.line, character=forge_diag.column),
                    end=Position(line=forge_diag.line, character=forge_diag.column + 1)
                ),
                message=forge_diag.message,
                severity=forge_diag.severity,
                code=forge_diag.code,
                source=forge_diag.source
            )
            
            if forge_diag.help_url:
                diagnostic.data = {"help_url": forge_diag.help_url}
            
            if file_uri not in diagnostics_by_file:
                diagnostics_by_file[file_uri] = []
            diagnostics_by_file[file_uri].append(diagnostic)
        
        # Update cache
        self.diagnostics_cache.update(diagnostics_by_file)
        
        return diagnostics_by_file
    
    def clear_cache(self):
        """Clear the diagnostics cache."""
        self.diagnostics_cache.clear()
        self.last_build_time.clear()