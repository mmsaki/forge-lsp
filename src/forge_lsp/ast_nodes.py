from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Union, Any
from enum import Enum

from lsprotocol.types import Position, Range, Location


class NodeType(Enum):
    SOURCE_UNIT = "source_unit"
    CONTRACT = "contract"
    INTERFACE = "interface"
    LIBRARY = "library"
    FUNCTION = "function"
    MODIFIER = "modifier"
    EVENT = "event"
    STRUCT = "struct"
    ENUM = "enum"
    VARIABLE = "variable"
    PARAMETER = "parameter"
    IMPORT = "import"
    USING = "using"
    PRAGMA = "pragma"
    EXPRESSION = "expression"
    STATEMENT = "statement"
    TYPE = "type"


class Visibility(Enum):
    PUBLIC = "public"
    PRIVATE = "private"
    INTERNAL = "internal"
    EXTERNAL = "external"


class StateMutability(Enum):
    PURE = "pure"
    VIEW = "view"
    PAYABLE = "payable"
    NONPAYABLE = "nonpayable"


@dataclass
class SourceLocation:
    start: Position
    end: Position
    uri: str = ""

    def to_range(self) -> Range:
        return Range(start=self.start, end=self.end)

    def to_location(self) -> Location:
        return Location(uri=self.uri, range=self.to_range())


class ASTNode(ABC):
    def __init__(self, node_type: NodeType, location: SourceLocation):
        self.node_type = node_type
        self.location = location
        self.parent: Optional['ASTNode'] = None
        self.children: List['ASTNode'] = []

    def add_child(self, child: 'ASTNode'):
        child.parent = self
        self.children.append(child)

    def remove_child(self, child: 'ASTNode'):
        if child in self.children:
            child.parent = None
            self.children.remove(child)

    def find_children_by_type(self, node_type: NodeType) -> List['ASTNode']:
        return [child for child in self.children if child.node_type == node_type]

    def find_ancestor_by_type(self, node_type: NodeType) -> Optional['ASTNode']:
        current = self.parent
        while current:
            if current.node_type == node_type:
                return current
            current = current.parent
        return None

    @abstractmethod
    def accept(self, visitor: 'ASTVisitor'):
        pass


class SourceUnitNode(ASTNode):
    def __init__(self, location: SourceLocation, file_path: str = ""):
        super().__init__(NodeType.SOURCE_UNIT, location)
        self.file_path = file_path
        self.imports: List['ImportNode'] = []
        self.pragmas: List['PragmaNode'] = []
        self.contracts: List['ContractNode'] = []
        self.using_directives: List['UsingNode'] = []

    def accept(self, visitor: 'ASTVisitor'):
        return visitor.visit_source_unit(self)


class ImportNode(ASTNode):
    def __init__(self, location: SourceLocation, path: str, symbols: Optional[List[str]] = None, alias: str = ""):
        super().__init__(NodeType.IMPORT, location)
        self.path = path
        self.symbols = symbols or []
        self.alias = alias

    def accept(self, visitor: 'ASTVisitor'):
        return visitor.visit_import(self)


class PragmaNode(ASTNode):
    def __init__(self, location: SourceLocation, name: str, value: str):
        super().__init__(NodeType.PRAGMA, location)
        self.name = name
        self.value = value

    def accept(self, visitor: 'ASTVisitor'):
        return visitor.visit_pragma(self)


class ContractNode(ASTNode):
    def __init__(self, location: SourceLocation, name: str, contract_type: str = "contract"):
        super().__init__(NodeType.CONTRACT, location)
        self.name = name
        self.contract_type = contract_type  # contract, interface, library
        self.inheritance: List[str] = []
        self.functions: List['FunctionNode'] = []
        self.variables: List['VariableNode'] = []
        self.structs: List['StructNode'] = []
        self.enums: List['EnumNode'] = []
        self.events: List['EventNode'] = []
        self.modifiers: List['ModifierNode'] = []
        self.using_directives: List['UsingNode'] = []

    def accept(self, visitor: 'ASTVisitor'):
        return visitor.visit_contract(self)


class FunctionNode(ASTNode):
    def __init__(self, location: SourceLocation, name: str):
        super().__init__(NodeType.FUNCTION, location)
        self.name = name
        self.visibility: Optional[Visibility] = None
        self.state_mutability: Optional[StateMutability] = None
        self.is_constructor = False
        self.is_fallback = False
        self.is_receive = False
        self.parameters: List['ParameterNode'] = []
        self.return_parameters: List['ParameterNode'] = []
        self.modifiers: List[str] = []
        self.body: Optional['StatementNode'] = None

    def accept(self, visitor: 'ASTVisitor'):
        return visitor.visit_function(self)


class ModifierNode(ASTNode):
    def __init__(self, location: SourceLocation, name: str):
        super().__init__(NodeType.MODIFIER, location)
        self.name = name
        self.parameters: List['ParameterNode'] = []
        self.body: Optional['StatementNode'] = None

    def accept(self, visitor: 'ASTVisitor'):
        return visitor.visit_modifier(self)


class EventNode(ASTNode):
    def __init__(self, location: SourceLocation, name: str):
        super().__init__(NodeType.EVENT, location)
        self.name = name
        self.parameters: List['ParameterNode'] = []
        self.anonymous = False

    def accept(self, visitor: 'ASTVisitor'):
        return visitor.visit_event(self)


class StructNode(ASTNode):
    def __init__(self, location: SourceLocation, name: str):
        super().__init__(NodeType.STRUCT, location)
        self.name = name
        self.members: List['VariableNode'] = []

    def accept(self, visitor: 'ASTVisitor'):
        return visitor.visit_struct(self)


class EnumNode(ASTNode):
    def __init__(self, location: SourceLocation, name: str):
        super().__init__(NodeType.ENUM, location)
        self.name = name
        self.values: List[str] = []

    def accept(self, visitor: 'ASTVisitor'):
        return visitor.visit_enum(self)


class VariableNode(ASTNode):
    def __init__(self, location: SourceLocation, name: str, type_name: str):
        super().__init__(NodeType.VARIABLE, location)
        self.name = name
        self.type_name = type_name
        self.visibility: Optional[Visibility] = None
        self.is_constant = False
        self.is_immutable = False
        self.is_state_variable = False
        self.initial_value: Optional['ExpressionNode'] = None

    def accept(self, visitor: 'ASTVisitor'):
        return visitor.visit_variable(self)


class ParameterNode(ASTNode):
    def __init__(self, location: SourceLocation, name: str, type_name: str):
        super().__init__(NodeType.PARAMETER, location)
        self.name = name
        self.type_name = type_name
        self.storage_location: Optional[str] = None  # memory, storage, calldata
        self.is_indexed = False  # for event parameters

    def accept(self, visitor: 'ASTVisitor'):
        return visitor.visit_parameter(self)


class UsingNode(ASTNode):
    def __init__(self, location: SourceLocation, library_name: str, target_type: str):
        super().__init__(NodeType.USING, location)
        self.library_name = library_name
        self.target_type = target_type
        self.is_global = False
        self.functions: List[str] = []

    def accept(self, visitor: 'ASTVisitor'):
        return visitor.visit_using(self)


class TypeNode(ASTNode):
    def __init__(self, location: SourceLocation, type_name: str):
        super().__init__(NodeType.TYPE, location)
        self.type_name = type_name
        self.is_array = False
        self.array_size: Optional[int] = None
        self.key_type: Optional['TypeNode'] = None  # for mappings
        self.value_type: Optional['TypeNode'] = None  # for mappings

    def accept(self, visitor: 'ASTVisitor'):
        return visitor.visit_type(self)


class ExpressionNode(ASTNode):
    def __init__(self, location: SourceLocation, expression_type: str):
        super().__init__(NodeType.EXPRESSION, location)
        self.expression_type = expression_type  # identifier, literal, binary_op, etc.
        self.value: Any = None
        self.operator: Optional[str] = None
        self.left: Optional['ExpressionNode'] = None
        self.right: Optional['ExpressionNode'] = None

    def accept(self, visitor: 'ASTVisitor'):
        return visitor.visit_expression(self)


class StatementNode(ASTNode):
    def __init__(self, location: SourceLocation, statement_type: str):
        super().__init__(NodeType.STATEMENT, location)
        self.statement_type = statement_type  # block, if, for, while, etc.

    def accept(self, visitor: 'ASTVisitor'):
        return visitor.visit_statement(self)


class ASTVisitor(ABC):
    @abstractmethod
    def visit_source_unit(self, node: SourceUnitNode):
        pass

    @abstractmethod
    def visit_import(self, node: ImportNode):
        pass

    @abstractmethod
    def visit_pragma(self, node: PragmaNode):
        pass

    @abstractmethod
    def visit_contract(self, node: ContractNode):
        pass

    @abstractmethod
    def visit_function(self, node: FunctionNode):
        pass

    @abstractmethod
    def visit_modifier(self, node: ModifierNode):
        pass

    @abstractmethod
    def visit_event(self, node: EventNode):
        pass

    @abstractmethod
    def visit_struct(self, node: StructNode):
        pass

    @abstractmethod
    def visit_enum(self, node: EnumNode):
        pass

    @abstractmethod
    def visit_variable(self, node: VariableNode):
        pass

    @abstractmethod
    def visit_parameter(self, node: ParameterNode):
        pass

    @abstractmethod
    def visit_using(self, node: UsingNode):
        pass

    @abstractmethod
    def visit_type(self, node: TypeNode):
        pass

    @abstractmethod
    def visit_expression(self, node: ExpressionNode):
        pass

    @abstractmethod
    def visit_statement(self, node: StatementNode):
        pass


class BaseASTVisitor(ASTVisitor):
    def visit_source_unit(self, node: SourceUnitNode):
        for child in node.children:
            child.accept(self)

    def visit_import(self, node: ImportNode):
        pass

    def visit_pragma(self, node: PragmaNode):
        pass

    def visit_contract(self, node: ContractNode):
        for child in node.children:
            child.accept(self)

    def visit_function(self, node: FunctionNode):
        for child in node.children:
            child.accept(self)

    def visit_modifier(self, node: ModifierNode):
        for child in node.children:
            child.accept(self)

    def visit_event(self, node: EventNode):
        for child in node.children:
            child.accept(self)

    def visit_struct(self, node: StructNode):
        for child in node.children:
            child.accept(self)

    def visit_enum(self, node: EnumNode):
        pass

    def visit_variable(self, node: VariableNode):
        for child in node.children:
            child.accept(self)

    def visit_parameter(self, node: ParameterNode):
        pass

    def visit_using(self, node: UsingNode):
        pass

    def visit_type(self, node: TypeNode):
        for child in node.children:
            child.accept(self)

    def visit_expression(self, node: ExpressionNode):
        for child in node.children:
            child.accept(self)

    def visit_statement(self, node: StatementNode):
        for child in node.children:
            child.accept(self)