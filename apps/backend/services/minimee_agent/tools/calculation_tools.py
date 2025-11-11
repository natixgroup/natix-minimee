"""
LangChain tools for calculations and math
"""
from langchain.tools import tool
import math
import re


@tool
def calculate(expression: str) -> str:
    """
    Evaluate a mathematical expression safely.
    Supports basic arithmetic operations: +, -, *, /, **, sqrt, etc.
    
    Args:
        expression: Mathematical expression to evaluate (e.g., "2 + 2", "sqrt(16)", "10 * 5")
    
    Returns:
        Result of the calculation or error message
    
    Examples:
        - "2 + 2" -> "4"
        - "10 * 5" -> "50"
        - "sqrt(16)" -> "4.0"
        - "2 ** 3" -> "8"
    """
    try:
        # Sanitize expression - only allow safe math operations
        # Remove any potentially dangerous functions
        safe_chars = set('0123456789+-*/.() sqrtpowlogexpabsminmax')
        if not all(c in safe_chars or c.isspace() for c in expression):
            return "Error: Expression contains invalid characters"
        
        # Replace common math functions
        expression = expression.replace('sqrt', 'math.sqrt')
        expression = expression.replace('pow', 'math.pow')
        expression = expression.replace('log', 'math.log')
        expression = expression.replace('exp', 'math.exp')
        expression = expression.replace('abs', 'math.abs')
        expression = expression.replace('min', 'math.min')
        expression = expression.replace('max', 'math.max')
        
        # Evaluate safely
        result = eval(expression, {"__builtins__": {}}, {"math": math})
        
        # Format result
        if isinstance(result, float):
            if result.is_integer():
                return str(int(result))
            return f"{result:.2f}"
        return str(result)
    except ZeroDivisionError:
        return "Error: Division by zero"
    except Exception as e:
        return f"Error calculating: {str(e)}"


