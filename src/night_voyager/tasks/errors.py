class TaskConflictError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class TaskAuthorizationError(Exception):
    pass


class TaskLeaseLostError(Exception):
    pass


class TaskTransientError(Exception):
    pass
