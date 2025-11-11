#!/usr/bin/env python3
"""
Validate Python syntax for all Python files in the backend
This script is run before starting the server to catch syntax errors early
"""
import ast
import sys
import os
from pathlib import Path

def validate_file(file_path: Path) -> tuple[bool, str]:
    """Validate syntax of a Python file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            source = f.read()
        
        # Try to compile the file
        compile(source, str(file_path), 'exec', ast.PyCF_ONLY_AST)
        return True, ""
    except SyntaxError as e:
        return False, f"SyntaxError in {file_path}:{e.lineno}: {e.msg}\n  {e.text}"
    except Exception as e:
        return False, f"Error validating {file_path}: {str(e)}"

def main():
    """Main validation function"""
    backend_dir = Path(__file__).parent.parent
    errors = []
    
    # Find all Python files
    python_files = []
    for ext in ['*.py']:
        python_files.extend(backend_dir.rglob(ext))
    
    # Exclude __pycache__, .venv, node_modules, etc.
    python_files = [
        f for f in python_files
        if '__pycache__' not in str(f) and '.venv' not in str(f) and 'node_modules' not in str(f)
    ]
    
    print(f"Validating {len(python_files)} Python files...")
    
    for file_path in python_files:
        is_valid, error = validate_file(file_path)
        if not is_valid:
            errors.append(error)
            print(f"✗ {error}")
        else:
            print(f"✓ {file_path.relative_to(backend_dir)}")
    
    if errors:
        print(f"\n❌ Found {len(errors)} syntax error(s):")
        for error in errors:
            print(f"  {error}")
        sys.exit(1)
    else:
        print(f"\n✅ All {len(python_files)} files are valid!")
        sys.exit(0)

if __name__ == "__main__":
    main()

