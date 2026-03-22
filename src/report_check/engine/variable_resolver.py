import re
import os
import time
from typing import Any, Dict
from report_check.core.exceptions import VariableMissingError


class VariableResolver:
    """Resolves variables in strings and dictionaries from context, environment, and builtins."""

    # Pattern to match ${var_name}
    VARIABLE_PATTERN = re.compile(r"\$\{([^}]+)\}")

    # Builtin variables
    BUILTINS = {
        "__timestamp__": lambda: str(int(time.time())),
        "__iso_timestamp__": lambda: time.strftime("%Y-%m-%dT%H:%M:%S"),
    }

    def resolve(self, value: str, context_vars: Dict[str, Any]) -> Any:
        """
        Resolve variables in a string.

        Args:
            value: The string that may contain ${var} patterns
            context_vars: Dictionary of context variables

        Returns:
            The string with variables resolved

        Raises:
            VariableMissingError: If a variable is not found
        """
        if not isinstance(value, str):
            return value

        def replace_var(match):
            var_name = match.group(1)
            return self._get_variable(var_name, context_vars)

        # Keep resolving until no more variables are found (handles nested variables)
        prev = None
        current = value
        max_iterations = 10  # Prevent infinite loops
        iterations = 0

        while prev != current and iterations < max_iterations:
            prev = current
            current = self.VARIABLE_PATTERN.sub(replace_var, current)
            iterations += 1

        return current

    def resolve_dict(self, obj: Any, context_vars: Dict[str, Any]) -> Any:
        """
        Recursively resolve variables in a dictionary or list.

        Args:
            obj: The object to resolve (dict, list, or primitive)
            context_vars: Dictionary of context variables

        Returns:
            The object with all variables resolved

        Raises:
            VariableMissingError: If a variable is not found
        """
        if isinstance(obj, dict):
            return {key: self.resolve_dict(value, context_vars) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self.resolve_dict(item, context_vars) for item in obj]
        elif isinstance(obj, str):
            return self.resolve(obj, context_vars)
        else:
            return obj

    def _get_variable(self, var_name: str, context_vars: Dict[str, Any]) -> str:
        """
        Get a variable value from context, environment, or builtins.

        Priority:
        1. context_vars
        2. Environment variables
        3. Builtins

        Args:
            var_name: The variable name
            context_vars: Dictionary of context variables

        Returns:
            The variable value as a string

        Raises:
            VariableMissingError: If variable not found in any source
        """
        # Check context vars first
        if var_name in context_vars:
            return str(context_vars[var_name])

        # Check environment variables
        if var_name in os.environ:
            return os.environ[var_name]

        # Check builtins
        if var_name in self.BUILTINS:
            return self.BUILTINS[var_name]()

        # Variable not found
        raise VariableMissingError(f"Variable '{var_name}' not found in context, environment, or builtins")
