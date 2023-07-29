class CodedogError(Exception):
    def __init__(self, message: str = None, code: int = -1):
        self.message = "" if message is None else message
        self.code = code
