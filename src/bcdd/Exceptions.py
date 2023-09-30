class FileNotFoundError(Exception):
    pass


class DllNotFoundException(Exception):
    pass


class FieldNotFoundException(Exception):
    pass


class ParScoreInvalidException(FieldNotFoundException):
    pass


class DDTableInvalidException(FieldNotFoundException):
    pass
