"""GENESIS Core Tool: Calculator

Evaluate mathematical expressions safely using AST validation.
"""

import ast
import logging
import math
import operator

logger = logging.getLogger(__name__)

SKILL_ID = "calculator"
SKILL_NAME = "Calculator"
SKILL_DESCRIPTION = "Evaluate mathematical expressions safely"
SKILL_CATEGORY = "core"

_ALLOWED_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

_SAFE_FUNCTIONS: dict[str, callable] = {
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
    "sum": sum,
    "pow": pow,
    "sqrt": math.sqrt,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "log": math.log,
    "log10": math.log10,
    "log2": math.log2,
    "ceil": math.ceil,
    "floor": math.floor,
    "pi": math.pi,
    "e": math.e,
    "tau": math.tau,
    "inf": math.inf,
}

_ALLOWED_NODE_TYPES = (
    ast.Expression,
    ast.Constant,
    ast.BinOp,
    ast.UnaryOp,
    ast.Call,
    ast.Name,
    ast.Attribute,
    ast.Load,
    ast.Tuple,
    ast.List,
)


def _validate_ast(node: ast.AST) -> None:
    """Walk the AST and reject any unsafe nodes."""
    if not isinstance(node, _ALLOWED_NODE_TYPES + tuple(_ALLOWED_OPERATORS.keys())):
        raise ValueError(f"Unsafe expression element: {type(node).__name__}")

    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name):
            if node.func.id not in _SAFE_FUNCTIONS:
                raise ValueError(f"Function not allowed: {node.func.id}")
        elif isinstance(node.func, ast.Attribute):
            if not (
                isinstance(node.func.value, ast.Name)
                and node.func.value.id == "math"
                and hasattr(math, node.func.attr)
            ):
                raise ValueError(f"Attribute access not allowed: {ast.dump(node.func)}")
        else:
            raise ValueError(f"Unsupported call type: {type(node.func).__name__}")

    if isinstance(node, ast.Name) and node.id not in _SAFE_FUNCTIONS and node.id != "math":
        raise ValueError(f"Name not allowed: {node.id}")

    for child in ast.iter_child_nodes(node):
        _validate_ast(child)


async def calculate(expression: str) -> dict:
    """Evaluate a mathematical expression safely.

    Args:
        expression: A mathematical expression string (e.g., "2 + 3 * sin(pi/4)").

    Returns:
        Dict with success status and result or error message.
    """
    try:
        expression = expression.strip()
        if not expression:
            return {"success": False, "error": "Empty expression"}

        tree = ast.parse(expression, mode="eval")
        _validate_ast(tree)

        safe_globals = {"__builtins__": {}, "math": math}
        safe_globals.update(_SAFE_FUNCTIONS)

        code = compile(tree, "<expr>", "eval")
        result = eval(code, safe_globals)  # noqa: S307

        if isinstance(result, complex):
            return {
                "success": True,
                "result": {"real": result.real, "imag": result.imag},
                "expression": expression,
            }

        return {
            "success": True,
            "result": float(result) if isinstance(result, (int, float)) else result,
            "expression": expression,
        }

    except (ValueError, SyntaxError, TypeError, ZeroDivisionError) as e:
        logger.warning("Calculator rejected expression %r: %s", expression, e)
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.error("Unexpected calculator error for %r: %s", expression, e)
        return {"success": False, "error": f"Evaluation error: {e}"}
