class DecisionConflictError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class DecisionAuthorizationError(Exception):
    pass
