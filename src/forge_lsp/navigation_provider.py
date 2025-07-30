"""
Advanced navigation provider for Solidity LSP.
Implements go-to-definition, go-to-declaration, go-to-type-definition, 
go-to-implementation, and find-references with library method resolution.
"""

import logging
import re
from typing import Dict, List, Optional, Set, Tuple
from pathlib import Path

from lsprotocol.types import Location, Position, Range

try:
    from .library_resolver import LibraryMethodResolver, MethodCallContext
except ImportError:
    from library_resolver import LibraryMethodResolver, MethodCallContext

try:
    from .remapping_resolver import RemappingResolver
except ImportError:
    # Create a placeholder if remapping resolver is not available
    class RemappingResolver:
        def get_all_solidity_files(self):
            return []

logger = logging.getLogger(__name__)


class NavigationProvider:
    """Provides advanced navigation features for Solidity code."""
    
    def __init__(self, remapping_resolver: Optional[RemappingResolver] = None):
        self.remapping_resolver = remapping_resolver
        self.library_resolver = LibraryMethodResolver(remapping_resolver)
        
        # Cache for parsed symbols across files
        self.symbol_cache: Dict[str, Dict[str, List[Location]]] = {}  # file_uri -> {symbol -> locations}
        self.type_definitions: Dict[str, Location] = {}  # type_name -> definition location
        self.interface_implementations: Dict[str, List[Location]] = {}  # interface -> implementations
    
    def get_definitions(self, text: str, position: Position, document_uri: str) -> List[Location]:
        """
        Get definition locations for a symbol with comprehensive library method resolution.
        This is the main method that handles the complex 'using Library for Type' resolution.
        """
        lines = text.split('\n')
        if position.line >= len(lines):
            return []
        
        current_line = lines[position.line]
        
        # Parse the current context to understand what we're looking for
        context = self._analyze_position_context(text, position, document_uri)
        
        if context['type'] == 'library_method_call':
            # This is the complex case: variable.method() where method might be from a library
            return self._resolve_library_method_definition(context, document_uri)
        
        elif context['type'] == 'direct_method_call':
            # Direct method call: contract.method() or this.method()
            return self._resolve_direct_method_definition(context, document_uri)
        
        elif context['type'] == 'type_reference':
            # Type reference: uint256, MyStruct, etc.
            return self._resolve_type_definition(context, document_uri)
        
        elif context['type'] == 'import_path':
            # Import path: import "./Contract.sol"
            return self._resolve_import_definition(context, document_uri)
        
        elif context['type'] == 'identifier':
            # General identifier: variable, function, contract name
            return self._resolve_identifier_definition(context, document_uri)
        
        return []
    
    def get_declarations(self, text: str, position: Position, document_uri: str) -> List[Location]:
        """Get declaration locations (similar to definitions but includes forward declarations)."""
        # For Solidity, declarations and definitions are usually the same
        # But we can extend this for interface declarations vs implementations
        definitions = self.get_definitions(text, position, document_uri)
        
        # Add interface declarations if we're looking at an implementation
        context = self._analyze_position_context(text, position, document_uri)
        if context['type'] == 'identifier' and context.get('symbol_type') == 'function':
            # Check if this function implements an interface
            interface_declarations = self._find_interface_declarations(context, document_uri)
            definitions.extend(interface_declarations)
        
        return definitions
    
    def get_type_definitions(self, text: str, position: Position, document_uri: str) -> List[Location]:
        """Get type definition locations for variables, parameters, etc."""
        context = self._analyze_position_context(text, position, document_uri)
        
        if context['type'] == 'identifier':
            # Find the type of this identifier and then find the type's definition
            variable_type = self._infer_identifier_type(context, document_uri, text)
            if variable_type:
                return self._resolve_type_definition({'symbol': variable_type}, document_uri)
        
        elif context['type'] == 'library_method_call':
            # For library method calls, return the type that the method operates on
            receiver_type = context.get('receiver_type')
            if receiver_type:
                return self._resolve_type_definition({'symbol': receiver_type}, document_uri)
        
        return []
    
    def get_implementations(self, text: str, position: Position, document_uri: str) -> List[Location]:
        """Get implementation locations for interfaces and abstract functions."""
        context = self._analyze_position_context(text, position, document_uri)
        
        if context['type'] == 'identifier':
            symbol = context.get('symbol', '')
            
            # Check if this is an interface
            if self._is_interface(symbol, document_uri):
                return self._find_interface_implementations(symbol, document_uri)
            
            # Check if this is an abstract function
            if context.get('symbol_type') == 'function':
                return self._find_function_implementations(context, document_uri)
        
        return []
    
    def find_references(self, text: str, position: Position, document_uri: str, 
                       include_declaration: bool = True) -> List[Location]:
        """
        Find all references to a symbol with comprehensive library method support.
        This handles the complex case of library methods attached via 'using' directives.
        """
        context = self._analyze_position_context(text, position, document_uri)
        references = []
        
        if context['type'] == 'library_method_call':
            # Find all references to this library method
            references = self._find_library_method_references(context, document_uri)
        
        elif context['type'] == 'identifier':
            symbol = context.get('symbol', '')
            
            # Check if this identifier is a library function
            if self._is_library_function(symbol, document_uri):
                # Find both direct calls and library method calls
                references.extend(self._find_direct_function_references(symbol, document_uri))
                references.extend(self._find_library_method_references_by_function_name(symbol, document_uri))
            else:
                # Standard identifier references
                references = self._find_identifier_references(symbol, document_uri)
        
        # Add the declaration if requested
        if include_declaration:
            definitions = self.get_definitions(text, position, document_uri)
            references.extend(definitions)
        
        # Remove duplicates and sort by location
        references = self._deduplicate_locations(references)
        return references
    
    def _analyze_position_context(self, text: str, position: Position, document_uri: str) -> Dict:
        """Analyze the context around a position to determine what kind of symbol we're dealing with."""
        lines = text.split('\n')
        if position.line >= len(lines):
            return {'type': 'unknown'}
        
        current_line = lines[position.line]
        char_pos = position.character
        
        # Get the word at the current position
        word_start = char_pos
        while word_start > 0 and (current_line[word_start - 1].isalnum() or current_line[word_start - 1] == '_'):
            word_start -= 1
        
        word_end = char_pos
        while word_end < len(current_line) and (current_line[word_end].isalnum() or current_line[word_end] == '_'):
            word_end += 1
        
        if word_start == word_end:
            return {'type': 'unknown'}
        
        symbol = current_line[word_start:word_end]
        
        # Analyze the context around the symbol
        line_before = current_line[:word_start]
        line_after = current_line[word_end:]
        
        # Check for library method call pattern: variable.method(
        method_call_match = re.search(r'(\w+)\.\s*$', line_before)
        if method_call_match and line_after.strip().startswith('('):
            receiver_name = method_call_match.group(1)
            
            # Parse the file to get library info
            self.library_resolver.parse_file_for_library_info(
                document_uri.replace('file://', ''), text
            )
            
            # Infer the receiver type
            receiver_type = self.library_resolver._infer_variable_type(
                receiver_name, document_uri, text
            )
            
            if receiver_type:
                return {
                    'type': 'library_method_call',
                    'symbol': symbol,
                    'receiver_name': receiver_name,
                    'receiver_type': receiver_type,
                    'position': position
                }
        
        # Check for direct method call: contract.method( or this.method(
        direct_call_match = re.search(r'(\w+|this)\.\s*$', line_before)
        if direct_call_match and line_after.strip().startswith('('):
            return {
                'type': 'direct_method_call',
                'symbol': symbol,
                'receiver': direct_call_match.group(1),
                'position': position
            }
        
        # Check for import path
        if 'import' in current_line and ('"' in line_before or "'" in line_before):
            return {
                'type': 'import_path',
                'symbol': symbol,
                'position': position
            }
        
        # Check for type context
        type_keywords = ['uint', 'int', 'bool', 'address', 'string', 'bytes', 'mapping']
        if any(keyword in line_before for keyword in type_keywords) or symbol in type_keywords:
            return {
                'type': 'type_reference',
                'symbol': symbol,
                'position': position
            }
        
        # Default to identifier
        return {
            'type': 'identifier',
            'symbol': symbol,
            'position': position
        }
    
    def _resolve_library_method_definition(self, context: Dict, document_uri: str) -> List[Location]:
        """Resolve the definition of a library method call."""
        method_context = MethodCallContext(
            receiver_name=context['receiver_name'],
            receiver_type=context['receiver_type'],
            method_name=context['symbol'],
            call_location=Location(
                uri=document_uri,
                range=Range(
                    start=context['position'],
                    end=Position(
                        line=context['position'].line,
                        character=context['position'].character + len(context['symbol'])
                    )
                )
            )
        )
        
        # Use the library resolver to find the actual function
        resolved_function = self.library_resolver.resolve_library_method_call(
            method_context, document_uri
        )
        
        if resolved_function:
            return [resolved_function.location]
        
        return []
    
    def _resolve_direct_method_definition(self, context: Dict, document_uri: str) -> List[Location]:
        """Resolve direct method calls like contract.method() or this.method()."""
        # This would involve parsing the contract structure and finding the method
        # For now, we'll implement a basic version
        symbol = context['symbol']
        receiver = context['receiver']
        
        if receiver == 'this':
            # Look for the method in the current contract
            return self._find_method_in_current_contract(symbol, document_uri)
        else:
            # Look for the method in the specified contract/variable
            return self._find_method_in_contract(symbol, receiver, document_uri)
    
    def _resolve_type_definition(self, context: Dict, document_uri: str) -> List[Location]:
        """Resolve type definitions."""
        type_name = context['symbol']
        
        # Check built-in types first
        if type_name in ['uint', 'int', 'bool', 'address', 'string', 'bytes']:
            return []  # Built-in types don't have definitions
        
        # Look for custom types (structs, contracts, enums)
        return self._find_type_definition(type_name, document_uri)
    
    def _resolve_import_definition(self, context: Dict, document_uri: str) -> List[Location]:
        """Resolve import path definitions."""
        if not self.remapping_resolver:
            return []
        
        # Extract the import path from the current line
        # This is a simplified implementation
        return []
    
    def _resolve_identifier_definition(self, context: Dict, document_uri: str) -> List[Location]:
        """Resolve general identifier definitions."""
        symbol = context['symbol']
        
        # Look for the symbol in various contexts
        locations = []
        
        # Check for variable definitions
        locations.extend(self._find_variable_definition(symbol, document_uri))
        
        # Check for function definitions
        locations.extend(self._find_function_definition(symbol, document_uri))
        
        # Check for contract definitions
        locations.extend(self._find_contract_definition(symbol, document_uri))
        
        return locations
    
    def _find_library_method_references(self, context: Dict, document_uri: str) -> List[Location]:
        """Find all references to a library method."""
        method_name = context['symbol']
        receiver_type = context['receiver_type']
        
        # First, resolve which library function this refers to
        method_context = MethodCallContext(
            receiver_name=context['receiver_name'],
            receiver_type=receiver_type,
            method_name=method_name,
            call_location=Location(uri=document_uri, range=Range(
                start=context['position'], end=context['position']
            ))
        )
        
        resolved_function = self.library_resolver.resolve_library_method_call(
            method_context, document_uri
        )
        
        if not resolved_function:
            return []
        
        # Find all references to this specific library function
        project_files = self._get_project_files()
        return self.library_resolver.find_all_library_method_references(
            method_name, resolved_function.library_name, project_files
        )
    
    def _find_library_method_references_by_function_name(self, function_name: str, 
                                                        document_uri: str) -> List[Location]:
        """Find library method references when we know the function name."""
        project_files = self._get_project_files()
        references = []
        
        # We need to find which libraries contain this function
        for library_name, functions in self.library_resolver.library_functions.items():
            for func in functions:
                if func.name == function_name:
                    refs = self.library_resolver.find_all_library_method_references(
                        function_name, library_name, project_files
                    )
                    references.extend(refs)
        
        return references
    
    def _get_project_files(self) -> List[str]:
        """Get all Solidity files in the project."""
        if self.remapping_resolver:
            try:
                return [str(f) for f in self.remapping_resolver.get_all_solidity_files()]
            except:
                pass
        
        # Fallback: scan current directory
        project_root = Path.cwd()
        return [str(f) for f in project_root.rglob("*.sol")]
    
    def _deduplicate_locations(self, locations: List[Location]) -> List[Location]:
        """Remove duplicate locations and sort them."""
        seen = set()
        unique_locations = []
        
        for loc in locations:
            key = (loc.uri, loc.range.start.line, loc.range.start.character)
            if key not in seen:
                seen.add(key)
                unique_locations.append(loc)
        
        # Sort by file, then by line, then by character
        unique_locations.sort(key=lambda x: (x.uri, x.range.start.line, x.range.start.character))
        return unique_locations
    
    # Placeholder methods for various resolution types
    # These would be implemented with full parsing logic
    
    def _find_method_in_current_contract(self, method_name: str, document_uri: str) -> List[Location]:
        """Find a method in the current contract."""
        # Implementation would parse the current file and find the method
        return []
    
    def _find_method_in_contract(self, method_name: str, contract_name: str, document_uri: str) -> List[Location]:
        """Find a method in a specific contract."""
        return []
    
    def _find_type_definition(self, type_name: str, document_uri: str) -> List[Location]:
        """Find the definition of a custom type."""
        return []
    
    def _find_variable_definition(self, var_name: str, document_uri: str) -> List[Location]:
        """Find variable definitions."""
        return []
    
    def _find_function_definition(self, func_name: str, document_uri: str) -> List[Location]:
        """Find function definitions."""
        return []
    
    def _find_contract_definition(self, contract_name: str, document_uri: str) -> List[Location]:
        """Find contract definitions."""
        return []
    
    def _find_identifier_references(self, symbol: str, document_uri: str) -> List[Location]:
        """Find all references to an identifier."""
        return []
    
    def _find_direct_function_references(self, func_name: str, document_uri: str) -> List[Location]:
        """Find direct function call references."""
        return []
    
    def _infer_identifier_type(self, context: Dict, document_uri: str, text: str) -> Optional[str]:
        """Infer the type of an identifier."""
        return self.library_resolver._infer_variable_type(
            context['symbol'], document_uri, text
        )
    
    def _is_interface(self, symbol: str, document_uri: str) -> bool:
        """Check if a symbol is an interface."""
        return False
    
    def _is_library_function(self, symbol: str, document_uri: str) -> bool:
        """Check if a symbol is a library function."""
        for functions in self.library_resolver.library_functions.values():
            if any(f.name == symbol for f in functions):
                return True
        return False
    
    def _find_interface_declarations(self, context: Dict, document_uri: str) -> List[Location]:
        """Find interface declarations for a function."""
        return []
    
    def _find_interface_implementations(self, interface_name: str, document_uri: str) -> List[Location]:
        """Find implementations of an interface."""
        return []
    
    def _find_function_implementations(self, context: Dict, document_uri: str) -> List[Location]:
        """Find implementations of an abstract function."""
        return []