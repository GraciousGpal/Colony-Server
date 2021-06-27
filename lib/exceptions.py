from logging import getLogger

log = getLogger(__name__)


class UserDisconnected(Exception):
    pass


class UserNotFoundInRoom(Exception):
    pass


class NewVarCase(Exception):
    def __init__(self, case):
        self.case = case
        log.error(f"Found a new var case.(%s)", case)
