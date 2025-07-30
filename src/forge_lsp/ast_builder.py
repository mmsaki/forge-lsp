import logging
from typing import Optional, List, Dict, Any
from antlr4 import CommonTokenStream

from lsprotocol.types import Position

try:
    from .antlr_generated.grammar.SolidityParser import SolidityParser
    from .antlr_generated.grammar.SolidityParserVisitor import SolidityParserVisitor
except ImportError:
    import sys
    import os
    sys.path.append(os.path.join(os.path.dirname(__file__), "antlr_generated", "grammar"))
    from SolidityParser import SolidityParser
    from SolidityParserVisitor import SolidityParserVisitor

from .ast_nodes import (
    ASTNode, SourceUnitNode, ImportNode, PragmaNode, ContractNode, FunctionNode,
    ModifierNode, EventNode, StructNode, EnumNode, VariableNode, ParameterNode,
    UsingNode, TypeNode, ExpressionNode, StatementNode, SourceLocation,
    Visibility, StateMutability
)

logger = logging.getLogger(__name__)


class ASTBuilderVisitor(SolidityParserVisitor):
    def __init__(self, document_uri: str, token_stream: CommonTokenStream):
        self.document_uri = document_uri
        self.token_stream = token_stream
        self.current_contract: Optional[ContractNode] = None

    def _create_location(self, ctx) -> SourceLocation:
        start_token = ctx.start
        stop_token = ctx.stop if ctx.stop else ctx.start
        
        return SourceLocation(
            start=Position(line=start_token.line - 1, character=start_token.column),
            end=Position(
                line=stop_token.line - 1,
                character=stop_token.column + len(stop_token.text)
            ),
            uri=self.document_uri
        )

    def visitSourceUnit(self, ctx: SolidityParser.SourceUnitContext) -> SourceUnitNode:
        location = self._create_location(ctx)
        source_unit = SourceUnitNode(location, self.document_uri.replace("file://", ""))
        
        for child in ctx.children:
            if hasattr(child, 'accept'):
                node = child.accept(self)
                if node:
                    source_unit.add_child(node)
                    
                    if isinstance(node, ImportNode):
                        source_unit.imports.append(node)
                    elif isinstance(node, PragmaNode):
                        source_unit.pragmas.append(node)
                    elif isinstance(node, ContractNode):
                        source_unit.contracts.append(node)
                    elif isinstance(node, UsingNode):
                        source_unit.using_directives.append(node)
        
        return source_unit

    def visitImportDirective(self, ctx: SolidityParser.ImportDirectiveContext) -> ImportNode:
        location = self._create_location(ctx)
        
        path = ""
        symbols = []
        alias = ""
        
        if ctx.importPath():
            path = ctx.importPath().getText().strip("\"'")
        
        if ctx.importDeclaration():
            for import_decl in ctx.importDeclaration():
                if hasattr(import_decl, 'identifier') and import_decl.identifier():
                    symbols.append(import_decl.identifier().getText())
        
        if ctx.identifier():
            alias = ctx.identifier().getText()
        
        return ImportNode(location, path, symbols, alias)

    def visitPragmaDirective(self, ctx: SolidityParser.PragmaDirectiveContext) -> PragmaNode:
        location = self._create_location(ctx)
        
        name = ""
        value = ""
        
        if ctx.pragmaName():
            name = ctx.pragmaName().getText()
        
        if ctx.pragmaValue():
            value = ctx.pragmaValue().getText()
        
        return PragmaNode(location, name, value)

    def visitContractDefinition(self, ctx: SolidityParser.ContractDefinitionContext) -> ContractNode:
        location = self._create_location(ctx)
        
        name = ""
        if ctx.identifier():
            name = ctx.identifier().getText()
        
        contract_type = "contract"
        if ctx.Contract():
            contract_type = "contract"
        elif ctx.Interface():
            contract_type = "interface"
        elif ctx.Library():
            contract_type = "library"
        
        contract = ContractNode(location, name, contract_type)
        self.current_contract = contract
        
        if ctx.inheritanceSpecifier():
            for inheritance in ctx.inheritanceSpecifier():
                if inheritance.userDefinedTypeName():
                    contract.inheritance.append(inheritance.userDefinedTypeName().getText())
        
        for child in ctx.children:
            if hasattr(child, 'accept'):
                node = child.accept(self)
                if node:
                    contract.add_child(node)
                    
                    if isinstance(node, FunctionNode):
                        contract.functions.append(node)
                    elif isinstance(node, VariableNode):
                        contract.variables.append(node)
                    elif isinstance(node, StructNode):
                        contract.structs.append(node)
                    elif isinstance(node, EnumNode):
                        contract.enums.append(node)
                    elif isinstance(node, EventNode):
                        contract.events.append(node)
                    elif isinstance(node, ModifierNode):
                        contract.modifiers.append(node)
                    elif isinstance(node, UsingNode):
                        contract.using_directives.append(node)
        
        self.current_contract = None
        return contract

    def visitFunctionDefinition(self, ctx: SolidityParser.FunctionDefinitionContext) -> FunctionNode:
        location = self._create_location(ctx)
        
        name = ""
        if ctx.identifier():
            name = ctx.identifier().getText()
        elif ctx.Constructor():
            name = "constructor"
        elif ctx.Fallback():
            name = "fallback"
        elif ctx.Receive():
            name = "receive"
        
        function = FunctionNode(location, name)
        
        function.is_constructor = ctx.Constructor() is not None
        function.is_fallback = ctx.Fallback() is not None
        function.is_receive = ctx.Receive() is not None
        
        if ctx.modifierName():
            for modifier in ctx.modifierName():
                if modifier.identifier():
                    function.modifiers.append(modifier.identifier().getText())
        
        if ctx.visibility():
            visibility_text = ctx.visibility().getText().lower()
            if visibility_text == "public":
                function.visibility = Visibility.PUBLIC
            elif visibility_text == "private":
                function.visibility = Visibility.PRIVATE
            elif visibility_text == "internal":
                function.visibility = Visibility.INTERNAL
            elif visibility_text == "external":
                function.visibility = Visibility.EXTERNAL
        
        if ctx.stateMutability():
            mutability_text = ctx.stateMutability().getText().lower()
            if mutability_text == "pure":
                function.state_mutability = StateMutability.PURE
            elif mutability_text == "view":
                function.state_mutability = StateMutability.VIEW
            elif mutability_text == "payable":
                function.state_mutability = StateMutability.PAYABLE
            else:
                function.state_mutability = StateMutability.NONPAYABLE
        
        if ctx.parameterList():
            for param_ctx in ctx.parameterList():
                if hasattr(param_ctx, 'parameter'):
                    for param in param_ctx.parameter():
                        param_node = self.visitParameter(param)
                        if param_node:
                            function.parameters.append(param_node)
                            function.add_child(param_node)
        
        if ctx.returnParameters():
            for return_param_ctx in ctx.returnParameters():
                if hasattr(return_param_ctx, 'parameter'):
                    for param in return_param_ctx.parameter():
                        param_node = self.visitParameter(param)
                        if param_node:
                            function.return_parameters.append(param_node)
                            function.add_child(param_node)
        
        if ctx.block():
            body = self.visitBlock(ctx.block())
            if body:
                function.body = body
                function.add_child(body)
        
        return function

    def visitParameter(self, ctx: SolidityParser.ParameterContext) -> ParameterNode:
        location = self._create_location(ctx)
        
        name = ""
        if ctx.identifier():
            name = ctx.identifier().getText()
        
        type_name = ""
        if ctx.typeName():
            type_name = ctx.typeName().getText()
        
        param = ParameterNode(location, name, type_name)
        
        if ctx.storageLocation():
            param.storage_location = ctx.storageLocation().getText()
        
        return param

    def visitStateVariableDeclaration(self, ctx: SolidityParser.StateVariableDeclarationContext) -> VariableNode:
        location = self._create_location(ctx)
        
        name = ""
        type_name = ""
        
        if ctx.identifier():
            name = ctx.identifier().getText()
        
        if ctx.typeName():
            type_name = ctx.typeName().getText()
        
        variable = VariableNode(location, name, type_name)
        variable.is_state_variable = True
        
        if ctx.visibility():
            visibility_text = ctx.visibility().getText().lower()
            if visibility_text == "public":
                variable.visibility = Visibility.PUBLIC
            elif visibility_text == "private":
                variable.visibility = Visibility.PRIVATE
            elif visibility_text == "internal":
                variable.visibility = Visibility.INTERNAL
            elif visibility_text == "external":
                variable.visibility = Visibility.EXTERNAL
        
        variable.is_constant = ctx.Constant() is not None
        variable.is_immutable = ctx.Immutable() is not None
        
        if ctx.expression():
            initial_value = self.visitExpression(ctx.expression())
            if initial_value:
                variable.initial_value = initial_value
                variable.add_child(initial_value)
        
        return variable

    def visitStructDefinition(self, ctx: SolidityParser.StructDefinitionContext) -> StructNode:
        location = self._create_location(ctx)
        
        name = ""
        if ctx.identifier():
            name = ctx.identifier().getText()
        
        struct = StructNode(location, name)
        
        if ctx.variableDeclaration():
            for var_ctx in ctx.variableDeclaration():
                var_node = self.visitVariableDeclaration(var_ctx)
                if var_node:
                    struct.members.append(var_node)
                    struct.add_child(var_node)
        
        return struct

    def visitVariableDeclaration(self, ctx: SolidityParser.VariableDeclarationContext) -> VariableNode:
        location = self._create_location(ctx)
        
        name = ""
        type_name = ""
        
        if ctx.identifier():
            name = ctx.identifier().getText()
        
        if ctx.typeName():
            type_name = ctx.typeName().getText()
        
        return VariableNode(location, name, type_name)

    def visitEnumDefinition(self, ctx: SolidityParser.EnumDefinitionContext) -> EnumNode:
        location = self._create_location(ctx)
        
        name = ""
        if ctx.identifier():
            name = ctx.identifier().getText()
        
        enum = EnumNode(location, name)
        
        if ctx.enumValue():
            for enum_value in ctx.enumValue():
                if enum_value.identifier():
                    enum.values.append(enum_value.identifier().getText())
        
        return enum

    def visitEventDefinition(self, ctx: SolidityParser.EventDefinitionContext) -> EventNode:
        location = self._create_location(ctx)
        
        name = ""
        if ctx.identifier():
            name = ctx.identifier().getText()
        
        event = EventNode(location, name)
        event.anonymous = ctx.Anonymous() is not None
        
        if ctx.eventParameterList():
            for param_list in ctx.eventParameterList():
                if hasattr(param_list, 'eventParameter'):
                    for param in param_list.eventParameter():
                        param_node = self.visitEventParameter(param)
                        if param_node:
                            event.parameters.append(param_node)
                            event.add_child(param_node)
        
        return event

    def visitEventParameter(self, ctx: SolidityParser.EventParameterContext) -> ParameterNode:
        location = self._create_location(ctx)
        
        name = ""
        type_name = ""
        
        if ctx.identifier():
            name = ctx.identifier().getText()
        
        if ctx.typeName():
            type_name = ctx.typeName().getText()
        
        param = ParameterNode(location, name, type_name)
        param.is_indexed = ctx.Indexed() is not None
        
        return param

    def visitModifierDefinition(self, ctx: SolidityParser.ModifierDefinitionContext) -> ModifierNode:
        location = self._create_location(ctx)
        
        name = ""
        if ctx.identifier():
            name = ctx.identifier().getText()
        
        modifier = ModifierNode(location, name)
        
        if ctx.parameterList():
            for param_ctx in ctx.parameterList():
                if hasattr(param_ctx, 'parameter'):
                    for param in param_ctx.parameter():
                        param_node = self.visitParameter(param)
                        if param_node:
                            modifier.parameters.append(param_node)
                            modifier.add_child(param_node)
        
        if ctx.block():
            body = self.visitBlock(ctx.block())
            if body:
                modifier.body = body
                modifier.add_child(body)
        
        return modifier

    def visitUsingDirective(self, ctx: SolidityParser.UsingDirectiveContext) -> UsingNode:
        location = self._create_location(ctx)
        
        library_name = ""
        target_type = "*"
        
        if ctx.identifierPath():
            library_name = ctx.identifierPath().getText()
        
        if ctx.typeName():
            target_type = ctx.typeName().getText()
        elif ctx.Mul():
            target_type = "*"
        
        using = UsingNode(location, library_name, target_type)
        using.is_global = ctx.Global() is not None
        
        return using

    def visitExpression(self, ctx: SolidityParser.ExpressionContext) -> ExpressionNode:
        location = self._create_location(ctx)
        
        expression_type = "unknown"
        value = None
        
        if ctx.primaryExpression():
            expression_type = "primary"
            if ctx.primaryExpression().identifier():
                expression_type = "identifier"
                value = ctx.primaryExpression().identifier().getText()
            elif ctx.primaryExpression().literal():
                expression_type = "literal"
                value = ctx.primaryExpression().literal().getText()
        
        expression = ExpressionNode(location, expression_type)
        expression.value = value
        
        return expression

    def visitBlock(self, ctx: SolidityParser.BlockContext) -> StatementNode:
        location = self._create_location(ctx)
        
        block = StatementNode(location, "block")
        
        if ctx.statement():
            for stmt_ctx in ctx.statement():
                stmt_node = self.visitStatement(stmt_ctx)
                if stmt_node:
                    block.add_child(stmt_node)
        
        return block

    def visitStatement(self, ctx: SolidityParser.StatementContext) -> StatementNode:
        location = self._create_location(ctx)
        
        statement_type = "unknown"
        
        if ctx.ifStatement():
            statement_type = "if"
        elif ctx.whileStatement():
            statement_type = "while"
        elif ctx.forStatement():
            statement_type = "for"
        elif ctx.block():
            return self.visitBlock(ctx.block())
        elif ctx.expressionStatement():
            statement_type = "expression"
        elif ctx.returnStatement():
            statement_type = "return"
        elif ctx.throwStatement():
            statement_type = "throw"
        elif ctx.assemblyBlock():
            statement_type = "assembly"
        elif ctx.variableDeclarationStatement():
            statement_type = "variable_declaration"
        
        return StatementNode(location, statement_type)

    def visitChildren(self, node):
        result = None
        n = node.getChildCount()
        for i in range(n):
            child = node.getChild(i)
            if hasattr(child, 'accept'):
                child_result = child.accept(self)
                if child_result:
                    result = child_result
        return result

    def visitTerminal(self, node):
        return None

    def visitErrorNode(self, node):
        return None