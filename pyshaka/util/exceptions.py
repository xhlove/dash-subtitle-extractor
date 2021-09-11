class Error(Exception):
    '''Base class for shaka errors.'''


class SeverityError(Error):
    '''Severity Error.'''


class CategoryError(Error):
    '''Category Error.'''


class InvalidMp4VTT(Error):
    '''Code INVALID_MP4_VTT Error.'''
    def __init__(self, reason: str):
        self.reason = reason

    def __str__(self):
        return self.reason


class OutOfBoundsError(Error):
    '''Code BUFFER_READ_OUT_OF_BOUNDS Error.'''


class IntOverflowError(Error):
    '''Code JS_INTEGER_OVERFLOW Error.'''