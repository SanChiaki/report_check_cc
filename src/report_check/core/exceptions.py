class CheckError(Exception):
    """Base error for the checking system."""
    def __init__(self, message: str, code: str = "CHECK_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


class RuleValidationError(CheckError):
    def __init__(self, message: str):
        super().__init__(message, "RULE_VALIDATION_ERROR")


class ExcelParseError(CheckError):
    def __init__(self, message: str):
        super().__init__(message, "EXCEL_PARSE_ERROR")


class ModelError(CheckError):
    def __init__(self, message: str):
        super().__init__(message, "MODEL_ERROR")


class FileTooLargeError(CheckError):
    def __init__(self, message: str):
        super().__init__(message, "FILE_TOO_LARGE")


class FileFormatError(CheckError):
    def __init__(self, message: str):
        super().__init__(message, "FILE_FORMAT_ERROR")


class VariableMissingError(CheckError):
    def __init__(self, message: str):
        super().__init__(message, "VARIABLE_MISSING")
