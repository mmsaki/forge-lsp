import logging
from typing import Dict, List, Optional, Set, Tuple, Any
from dataclasses import dataclass
from enum import Enum

from lsprotocol.types import Diagnostic, DiagnosticSeverity, Position, Range

try:
    from .ast_nodes import (
        ASTNode, SourceUnitNode, ContractNode, FunctionNode, VariableNode,
        ParameterNode, ExpressionNode, StatementNode, BaseASTVisitor,
        NodeType, Visibility, StateMutability
    )
except ImportError:
    from ast_nodes import (
        ASTNode, SourceUnitNode, ContractNode, FunctionNode, VariableNode,
        ParameterNode, ExpressionNode, StatementNode, BaseASTVisitor,
        NodeType, Visibility, StateMutability
    )

logger = logging.getLogger(__name__)


class SolidityType:
    """Represents a Solidity type with additional metadata."""
    
    def __init__(self, name: str, is_array: bool = False, array_size: Optional[int] = None):
        self.name = name
        self.is_array = is_array
        self.array_size = array_size
        self.is_mapping = False
        self.key_type: Optional['SolidityType'] = None
        self.value_type: Optional['SolidityType'] = None
    
    def __str__(self) -> str:
        if self.is_mapping:
            return f"mapping({self.key_type} => {self.value_type})"
        elif self.is_array:
            if self.array_size:
                return f"{self.name}[{self.array_size}]"
            else:
                return f"{self.name}[]"
        return self.name
    
    def is_numeric(self) -> bool:
        """Check if this is a numeric type."""
        return (self.name.startswith(('uint', 'int')) or 
                self.name in ('uint', 'int'))
    
    def is_compatible_with(self, other: 'SolidityType') -> bool:
        """Check if this type is compatible with another type."""
        if self.name == other.name:
            return True
        
        # Numeric type compatibility
        if self.is_numeric() and other.is_numeric():
            return True
        
        # Address compatibility
        if self.name == 'address' and other.name in ('address', 'address payable'):
            return True
        
        return False


@dataclass
class Symbol:
    """Represents a symbol in the symbol table."""
    name: str
    symbol_type: SolidityType
    node_type: NodeType
    visibility: Optional[Visibility] = None
    is_constant: bool = False
    is_immutable: bool = False
    scope: str = ""
    location: Optional[Position] = None


class Scope:
    """Represents a lexical scope in Solidity code."""
    
    def __init__(self, name: str, parent: Optional['Scope'] = None):
        self.name = name
        self.parent = parent
        self.symbols: Dict[str, Symbol] = {}
        self.children: List['Scope'] = []
    
    def add_symbol(self, symbol: Symbol) -> bool:
        """Add a symbol to this scope. Returns False if symbol already exists."""
        if symbol.name in self.symbols:
            return False
        self.symbols[symbol.name] = symbol
        return True
    
    def lookup(self, name: str) -> Optional[Symbol]:
        """Look up a symbol in this scope and parent scopes."""
        if name in self.symbols:
            return self.symbols[name]
        
        if self.parent:
            return self.parent.lookup(name)
        
        return None
    
    def lookup_local(self, name: str) -> Optional[Symbol]:
        """Look up a symbol only in this scope."""
        return self.symbols.get(name)


class SemanticAnalyzer(BaseASTVisitor):
    """Performs semantic analysis on Solidity AST."""
    
    def __init__(self, document_uri: str):
        self.document_uri = document_uri
        self.diagnostics: List[Diagnostic] = []
        self.global_scope = Scope("global")
        self.current_scope = self.global_scope
        self.current_contract: Optional[ContractNode] = None
        self.current_function: Optional[FunctionNode] = None
        
        # Built-in types and functions
        self._initialize_builtin_types()
    
    def _initialize_builtin_types(self):
        """Initialize built-in Solidity types and global functions."""
        # Built-in types
        builtin_types = [
            'bool', 'address', 'string', 'bytes',
            'uint', 'int', 'uint8', 'uint16', 'uint32', 'uint64', 'uint128', 'uint256',
            'int8', 'int16', 'int32', 'int64', 'int128', 'int256',
            'bytes1', 'bytes2', 'bytes4', 'bytes8', 'bytes16', 'bytes32'
        ]
        
        for type_name in builtin_types:
            symbol = Symbol(
                name=type_name,
                symbol_type=SolidityType(type_name),
                node_type=NodeType.TYPE
            )
            self.global_scope.add_symbol(symbol)
        
        # Global functions
        global_functions = [
            ('require', SolidityType('function')),
            ('assert', SolidityType('function')),
            ('revert', SolidityType('function')),
            ('keccak256', SolidityType('function')),
            ('sha256', SolidityType('function')),
            ('ecrecover', SolidityType('function')),
        ]
        
        for func_name, func_type in global_functions:
            symbol = Symbol(
                name=func_name,
                symbol_type=func_type,
                node_type=NodeType.FUNCTION
            )
            self.global_scope.add_symbol(symbol)
    
    def analyze(self, ast: SourceUnitNode) -> List[Diagnostic]:
        """Perform semantic analysis on the AST and return diagnostics."""
        self.diagnostics = []
        ast.accept(self)
        return self.diagnostics
    
    def _enter_scope(self, name: str) -> Scope:
        """Enter a new scope."""
        new_scope = Scope(name, self.current_scope)
        self.current_scope.children.append(new_scope)
        self.current_scope = new_scope
        return new_scope
    
    def _exit_scope(self):
        """Exit the current scope."""
        if self.current_scope.parent:
            self.current_scope = self.current_scope.parent
    
    def _add_diagnostic(self, message: str, severity: DiagnosticSeverity, 
                       position: Position, end_position: Optional[Position] = None):
        """Add a diagnostic message."""
        if not end_position:
            end_position = Position(line=position.line, character=position.character + 1)
        
        diagnostic = Diagnostic(
            range=Range(start=position, end=end_position),
            message=message,
            severity=severity,
            source="semantic-analyzer"
        )
        self.diagnostics.append(diagnostic)
    
    def _parse_type(self, type_name: str) -> SolidityType:
        """Parse a type string into a SolidityType object."""
        # Handle arrays
        if type_name.endswith('[]'):
            base_type = type_name[:-2]
            return SolidityType(base_type, is_array=True)
        
        # Handle fixed-size arrays
        if '[' in type_name and type_name.endswith(']'):
            bracket_pos = type_name.find('[')
            base_type = type_name[:bracket_pos]
            size_str = type_name[bracket_pos+1:-1]
            try:
                size = int(size_str)
                return SolidityType(base_type, is_array=True, array_size=size)
            except ValueError:
                pass
        
        # Handle mappings
        if type_name.startswith('mapping('):
            # Simple mapping parsing - could be enhanced
            return SolidityType('mapping')
        
        return SolidityType(type_name)
    
    def visit_source_unit(self, node: SourceUnitNode):
        """Visit source unit node."""
        super().visit_source_unit(node)
    
    def visit_contract(self, node: ContractNode):
        """Visit contract node."""
        self.current_contract = node
        
        # Enter contract scope
        contract_scope = self._enter_scope(f"contract_{node.name}")
        
        # Add contract to global scope
        contract_symbol = Symbol(
            name=node.name,
            symbol_type=SolidityType(node.contract_type),
            node_type=NodeType.CONTRACT,
            location=node.location.start
        )
        self.global_scope.add_symbol(contract_symbol)
        
        # Visit children
        super().visit_contract(node)
        
        # Exit contract scope
        self._exit_scope()
        self.current_contract = None
    
    def visit_function(self, node: FunctionNode):
        """Visit function node."""
        self.current_function = node
        
        # Enter function scope
        function_scope = self._enter_scope(f"function_{node.name}")
        
        # Add function to contract scope
        function_type = SolidityType('function')
        function_symbol = Symbol(
            name=node.name,
            symbol_type=function_type,
            node_type=NodeType.FUNCTION,
            visibility=node.visibility,
            location=node.location.start
        )
        
        if self.current_scope.parent and not self.current_scope.parent.add_symbol(function_symbol):
            self._add_diagnostic(
                f"Function '{node.name}' is already defined",
                DiagnosticSeverity.Error,
                node.location.start
            )
        
        # Add parameters to function scope
        for param in node.parameters:
            param_type = self._parse_type(param.type_name)
            param_symbol = Symbol(
                name=param.name,
                symbol_type=param_type,
                node_type=NodeType.PARAMETER,
                location=param.location.start
            )
            
            if not function_scope.add_symbol(param_symbol):
                self._add_diagnostic(
                    f"Parameter '{param.name}' is already defined",
                    DiagnosticSeverity.Error,
                    param.location.start
                )
        
        # Validate function modifiers
        self._validate_function_modifiers(node)
        
        # Visit function body
        if node.body:
            node.body.accept(self)
        
        # Exit function scope
        self._exit_scope()
        self.current_function = None
    
    def visit_variable(self, node: VariableNode):
        """Visit variable node."""
        var_type = self._parse_type(node.type_name)
        var_symbol = Symbol(
            name=node.name,
            symbol_type=var_type,
            node_type=NodeType.VARIABLE,
            visibility=node.visibility,
            is_constant=node.is_constant,
            is_immutable=node.is_immutable,
            location=node.location.start
        )
        
        if not self.current_scope.add_symbol(var_symbol):
            self._add_diagnostic(
                f"Variable '{node.name}' is already defined",
                DiagnosticSeverity.Error,
                node.location.start
            )
        
        # Validate initial value if present
        if node.initial_value:
            self._validate_expression_type(node.initial_value, var_type)
        
        super().visit_variable(node)
    
    def visit_expression(self, node: ExpressionNode):
        """Visit expression node."""
        # Type check expressions
        expr_type = self._infer_expression_type(node)
        
        # Store inferred type for later use
        if not hasattr(node, 'inferred_type'):
            node.inferred_type = expr_type
        
        super().visit_expression(node)
    
    def _validate_function_modifiers(self, node: FunctionNode):
        """Validate function modifiers and visibility."""
        # Check for conflicting visibility modifiers
        if node.visibility is None and node.name != "constructor":
            self._add_diagnostic(
                f"Function '{node.name}' must specify visibility",
                DiagnosticSeverity.Warning,
                node.location.start
            )
        
        # Check for conflicting state mutability
        if (node.state_mutability == StateMutability.PURE and 
            self._function_reads_state(node)):
            self._add_diagnostic(
                f"Function '{node.name}' is declared pure but reads state",
                DiagnosticSeverity.Error,
                node.location.start
            )
        
        if (node.state_mutability == StateMutability.VIEW and 
            self._function_modifies_state(node)):
            self._add_diagnostic(
                f"Function '{node.name}' is declared view but modifies state",
                DiagnosticSeverity.Error,
                node.location.start
            )
    
    def _function_reads_state(self, node: FunctionNode) -> bool:
        """Check if function reads contract state."""
        # This is a simplified check - could be enhanced with more sophisticated analysis
        return False
    
    def _function_modifies_state(self, node: FunctionNode) -> bool:
        """Check if function modifies contract state."""
        # This is a simplified check - could be enhanced with more sophisticated analysis
        return False
    
    def _infer_expression_type(self, node: ExpressionNode) -> SolidityType:
        """Infer the type of an expression."""
        if node.expression_type == "identifier":
            # Look up identifier in symbol table
            symbol = self.current_scope.lookup(str(node.value))
            if symbol:
                return symbol.symbol_type
            else:
                self._add_diagnostic(
                    f"Undefined identifier '{node.value}'",
                    DiagnosticSeverity.Error,
                    node.location.start
                )
                return SolidityType("unknown")
        
        elif node.expression_type == "literal":
            return self._infer_literal_type(str(node.value))
        
        elif node.expression_type == "binary_op":
            # Infer type based on operands and operator
            if node.left and node.right:
                left_type = self._infer_expression_type(node.left)
                right_type = self._infer_expression_type(node.right)
                return self._infer_binary_op_type(left_type, right_type, node.operator)
        
        return SolidityType("unknown")
    
    def _infer_literal_type(self, literal: str) -> SolidityType:
        """Infer the type of a literal value."""
        if literal.lower() in ('true', 'false'):
            return SolidityType('bool')
        
        if literal.startswith('"') or literal.startswith("'"):
            return SolidityType('string')
        
        if literal.startswith('0x'):
            # Hex literal - could be address or bytes
            if len(literal) == 42:  # 0x + 40 hex chars = address
                return SolidityType('address')
            else:
                return SolidityType('bytes')
        
        # Try to parse as number
        try:
            int(literal)
            return SolidityType('uint256')  # Default integer type
        except ValueError:
            pass
        
        return SolidityType('unknown')
    
    def _infer_binary_op_type(self, left_type: SolidityType, right_type: SolidityType, 
                             operator: Optional[str]) -> SolidityType:
        """Infer the result type of a binary operation."""
        if not operator:
            return SolidityType('unknown')
        
        # Comparison operators always return bool
        if operator in ('==', '!=', '<', '>', '<=', '>='):
            return SolidityType('bool')
        
        # Logical operators
        if operator in ('&&', '||'):
            return SolidityType('bool')
        
        # Arithmetic operators
        if operator in ('+', '-', '*', '/', '%', '**'):
            if left_type.is_numeric() and right_type.is_numeric():
                # Return the "larger" type
                return left_type if left_type.name >= right_type.name else right_type
        
        return SolidityType('unknown')
    
    def _validate_expression_type(self, expr: ExpressionNode, expected_type: SolidityType):
        """Validate that an expression matches the expected type."""
        actual_type = self._infer_expression_type(expr)
        
        if not actual_type.is_compatible_with(expected_type):
            self._add_diagnostic(
                f"Type mismatch: expected {expected_type}, got {actual_type}",
                DiagnosticSeverity.Error,
                expr.location.start
            )


class TypeChecker:
    """Standalone type checker for Solidity expressions."""
    
    def __init__(self, semantic_analyzer: SemanticAnalyzer):
        self.analyzer = semantic_analyzer
    
    def check_assignment(self, target_type: SolidityType, value_type: SolidityType) -> bool:
        """Check if a value can be assigned to a target."""
        return value_type.is_compatible_with(target_type)
    
    def check_function_call(self, function_name: str, arg_types: List[SolidityType]) -> Optional[SolidityType]:
        """Check a function call and return the return type."""
        # Look up function in symbol table
        symbol = self.analyzer.current_scope.lookup(function_name)
        if not symbol or symbol.node_type != NodeType.FUNCTION:
            return None
        
        # For now, return a generic function type
        # This could be enhanced with proper function signature checking
        return SolidityType('unknown')