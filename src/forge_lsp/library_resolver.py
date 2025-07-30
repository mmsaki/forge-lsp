"""
Advanced library method resolution system for Solidity LSP.
Handles the complex 'using Library for Type' syntax and method resolution.
"""

import logging
import re
from typing import Dict, List, Optional, Set, Tuple, Any
from dataclasses import dataclass
from pathlib import Path

from lsprotocol.types import Location, Position, Range

logger = logging.getLogger(__name__)


@dataclass
class LibraryFunction:
    """Represents a function in a library that can be attached to types."""
    name: str
    library_name: str
    first_param_type: str  # The type this function can be called on
    location: Location
    parameters: List[str]
    return_type: Optional[str] = None
    visibility: str = "internal"
    is_view: bool = False
    is_pure: bool = False


@dataclass
class UsingDirectiveInfo:
    """Information about a 'using Library for Type' directive."""
    library_name: str
    target_type: str  # "*" for wildcard, specific type otherwise
    is_global: bool = False
    specific_functions: Optional[List[str]] = None  # For selective imports
    location: Optional[Location] = None
    scope: str = ""  # Contract/file scope where this directive applies


@dataclass
class MethodCallContext:
    """Context information for a method call that might be a library method."""
    receiver_name: str  # Variable name (e.g., "name" in "name.add_one()")
    receiver_type: str  # Type of the receiver (e.g., "string")
    method_name: str    # Method being called (e.g., "add_one")
    call_location: Location
    arguments: Optional[List[str]] = None


class LibraryMethodResolver:
    """Resolves library method calls using 'using Library for Type' directives."""
    
    def __init__(self, remapping_resolver=None):
        self.remapping_resolver = remapping_resolver
        
        # Cache for parsed library functions
        self.library_functions: Dict[str, List[LibraryFunction]] = {}
        
        # Cache for using directives by file
        self.using_directives: Dict[str, List[UsingDirectiveInfo]] = {}
        
        # Cache for variable types in each file/scope
        self.variable_types: Dict[str, Dict[str, str]] = {}  # file_uri -> {var_name: type}
        
        # Cache for parsed files to avoid re-parsing
        self.parsed_files: Set[str] = set()
    
    def clear_cache(self):
        """Clear all caches - useful for testing or when files change."""
        self.library_functions.clear()
        self.using_directives.clear()
        self.variable_types.clear()
        self.parsed_files.clear()
    
    def parse_file_for_library_info(self, file_path: str, content: str) -> None:
        """Parse a file to extract library functions and using directives."""
        if file_path in self.parsed_files:
            return
        
        self.parsed_files.add(file_path)
        file_uri = f"file://{file_path}" if not file_path.startswith("file://") else file_path
        
        lines = content.split('\n')
        current_library = None
        current_contract = None
        
        for line_num, line in enumerate(lines):
            line_stripped = line.strip()
            
            # Parse library definitions
            library_match = re.match(r'library\s+(\w+)\s*{', line_stripped)
            if library_match:
                current_library = library_match.group(1)
                continue
            
            # Parse contract definitions
            contract_match = re.match(r'contract\s+(\w+)', line_stripped)
            if contract_match:
                current_contract = contract_match.group(1)
                current_library = None  # Reset library context
                continue
            
            # Parse using directives
            using_match = re.match(r'using\s+(\w+)\s+for\s+([^;]+);', line_stripped)
            if using_match:
                library_name = using_match.group(1)
                target_type = using_match.group(2).strip()
                
                # Handle wildcard
                if target_type == "*":
                    target_type = "*"
                
                directive = UsingDirectiveInfo(
                    library_name=library_name,
                    target_type=target_type,
                    location=Location(
                        uri=file_uri,
                        range=Range(
                            start=Position(line=line_num, character=0),
                            end=Position(line=line_num, character=len(line))
                        )
                    ),
                    scope=current_contract or "global"
                )
                
                if file_uri not in self.using_directives:
                    self.using_directives[file_uri] = []
                self.using_directives[file_uri].append(directive)
                continue
            
            # Parse library functions
            if current_library:
                func_match = re.match(
                    r'function\s+(\w+)\s*\(([^)]*)\)\s*(internal|external|public|private)?\s*(view|pure)?\s*(returns\s*\([^)]*\))?\s*{?',
                    line_stripped
                )
                if func_match:
                    func_name = func_match.group(1)
                    params_str = func_match.group(2)
                    visibility = func_match.group(3) or "internal"
                    state_mut = func_match.group(4) or ""
                    returns_str = func_match.group(5) or ""
                    
                    # Parse first parameter type (the type this function can be called on)
                    first_param_type = "*"  # Default to any type
                    parameters = []
                    
                    if params_str.strip():
                        params = [p.strip() for p in params_str.split(',')]
                        parameters = params
                        
                        if params:
                            # Extract type from first parameter
                            first_param = params[0].strip()
                            type_match = re.match(r'(\w+(?:\[\])?)\s+(?:memory|storage|calldata)?\s*\w+', first_param)
                            if type_match:
                                first_param_type = type_match.group(1)
                    
                    # Parse return type
                    return_type = None
                    if returns_str:
                        return_match = re.search(r'returns\s*\(([^)]*)\)', returns_str)
                        if return_match:
                            return_type = return_match.group(1).strip()
                    
                    lib_func = LibraryFunction(
                        name=func_name,
                        library_name=current_library,
                        first_param_type=first_param_type,
                        location=Location(
                            uri=file_uri,
                            range=Range(
                                start=Position(line=line_num, character=line.find('function')),
                                end=Position(line=line_num, character=line.find('function') + len(func_name) + 8)
                            )
                        ),
                        parameters=parameters,
                        return_type=return_type,
                        visibility=visibility,
                        is_view="view" in state_mut,
                        is_pure="pure" in state_mut
                    )
                    
                    if current_library not in self.library_functions:
                        self.library_functions[current_library] = []
                    self.library_functions[current_library].append(lib_func)
                    continue
            
            # Parse variable declarations to track types
            if current_contract:
                var_match = re.match(r'(\w+(?:\[\])?)\s+(?:public|private|internal)?\s*(\w+)', line_stripped)
                if var_match and 'function' not in line_stripped:
                    var_type = var_match.group(1)
                    var_name = var_match.group(2)
                    
                    if file_uri not in self.variable_types:
                        self.variable_types[file_uri] = {}
                    self.variable_types[file_uri][var_name] = var_type
    
    def resolve_library_method_call(self, context: MethodCallContext, file_uri: str) -> Optional[LibraryFunction]:
        """
        Resolve a method call to a library function using 'using' directives.
        
        This is the core method that handles the complex resolution logic.
        """
        # Get using directives for this file
        using_directives = self.using_directives.get(file_uri, [])
        
        # Find applicable using directives for the receiver type
        applicable_directives = []
        for directive in using_directives:
            if (directive.target_type == "*" or 
                directive.target_type == context.receiver_type or
                self._types_are_compatible(directive.target_type, context.receiver_type)):
                applicable_directives.append(directive)
        
        # Search for the method in applicable libraries
        for directive in applicable_directives:
            library_functions = self.library_functions.get(directive.library_name, [])
            
            for lib_func in library_functions:
                if lib_func.name == context.method_name:
                    # Check if the first parameter type matches the receiver type
                    if (lib_func.first_param_type == "*" or
                        lib_func.first_param_type == context.receiver_type or
                        self._types_are_compatible(lib_func.first_param_type, context.receiver_type)):
                        return lib_func
        
        return None
    
    def find_all_library_method_references(self, method_name: str, library_name: str, 
                                         project_files: List[str]) -> List[Location]:
        """Find all references to a library method across the project."""
        references = []
        
        for file_path in project_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                file_uri = f"file://{file_path}"
                self.parse_file_for_library_info(file_path, content)
                
                # Find method calls that could reference this library method
                lines = content.split('\n')
                for line_num, line in enumerate(lines):
                    # Look for method calls: variable.method_name(
                    method_calls = re.finditer(rf'(\w+)\.{re.escape(method_name)}\s*\(', line)
                    
                    for match in method_calls:
                        receiver_name = match.group(1)
                        
                        # Get the type of the receiver variable
                        receiver_type = self._infer_variable_type(receiver_name, file_uri, content)
                        
                        if receiver_type:
                            # Create context and check if it resolves to our library method
                            context = MethodCallContext(
                                receiver_name=receiver_name,
                                receiver_type=receiver_type,
                                method_name=method_name,
                                call_location=Location(
                                    uri=file_uri,
                                    range=Range(
                                        start=Position(line=line_num, character=match.start()),
                                        end=Position(line=line_num, character=match.end())
                                    )
                                )
                            )
                            
                            resolved_func = self.resolve_library_method_call(context, file_uri)
                            if resolved_func and resolved_func.library_name == library_name:
                                references.append(context.call_location)
            
            except Exception as e:
                logger.debug(f"Error processing file {file_path}: {e}")
        
        return references
    
    def get_library_methods_for_type(self, type_name: str, file_uri: str) -> List[LibraryFunction]:
        """Get all library methods available for a specific type in a file."""
        methods = []
        
        using_directives = self.using_directives.get(file_uri, [])
        
        for directive in using_directives:
            if (directive.target_type == "*" or 
                directive.target_type == type_name or
                self._types_are_compatible(directive.target_type, type_name)):
                
                library_functions = self.library_functions.get(directive.library_name, [])
                
                for lib_func in library_functions:
                    if (lib_func.first_param_type == "*" or
                        lib_func.first_param_type == type_name or
                        self._types_are_compatible(lib_func.first_param_type, type_name)):
                        methods.append(lib_func)
        
        return methods
    
    def _types_are_compatible(self, type1: str, type2: str) -> bool:
        """Check if two types are compatible for library method resolution."""
        if type1 == type2:
            return True
        
        # Handle array types
        if type1.endswith('[]') and type2.endswith('[]'):
            return self._types_are_compatible(type1[:-2], type2[:-2])
        
        # Handle basic type compatibility
        if type1 in ['uint', 'uint256'] and type2 in ['uint', 'uint256']:
            return True
        
        if type1 in ['int', 'int256'] and type2 in ['int', 'int256']:
            return True
        
        return False
    
    def _infer_variable_type(self, var_name: str, file_uri: str, content: str) -> Optional[str]:
        """Infer the type of a variable from the code context."""
        # First check our cache
        if file_uri in self.variable_types and var_name in self.variable_types[file_uri]:
            return self.variable_types[file_uri][var_name]
        
        # Parse the content to find variable declarations
        lines = content.split('\n')
        
        # Look for variable declarations
        for line in lines:
            line_stripped = line.strip()
            
            # State variable declaration
            var_match = re.match(rf'(\w+(?:\[\])?)\s+(?:public|private|internal)?\s+{re.escape(var_name)}\b', line_stripped)
            if var_match:
                return var_match.group(1)
            
            # Local variable declaration
            local_var_match = re.match(rf'(\w+(?:\[\])?)\s+(?:memory|storage)?\s+{re.escape(var_name)}\s*[=;]', line_stripped)
            if local_var_match:
                return local_var_match.group(1)
            
            # Function parameter (this is more complex, would need full parsing)
            # For now, we'll handle simple cases
            if f'{var_name} memory' in line or f'{var_name} storage' in line or f'{var_name} calldata' in line:
                param_match = re.search(rf'(\w+)\s+(?:memory|storage|calldata)\s+{re.escape(var_name)}\b', line)
                if param_match:
                    return param_match.group(1)
        
        return None
    
    def get_using_directives_for_file(self, file_uri: str) -> List[UsingDirectiveInfo]:
        """Get all using directives for a specific file."""
        return self.using_directives.get(file_uri, [])
    
    def get_library_functions(self, library_name: str) -> List[LibraryFunction]:
        """Get all functions for a specific library."""
        return self.library_functions.get(library_name, [])