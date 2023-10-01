class FieldNotFoundException(Exception):
    pass


class ParScoreInvalidException(FieldNotFoundException):
    pass


class DDTableInvalidException(FieldNotFoundException):
    pass
