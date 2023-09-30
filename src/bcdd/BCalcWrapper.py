'''
Wrapper class for libbcalcDDS.dll
'''

import os
from ctypes import cdll, c_char_p, c_void_p

from .Exceptions import DllNotFoundException


class BCalcWrapper(object):

    DENOMINATIONS = [ 'C', 'D', 'H', 'S', 'N' ]
    PLAYERS = [ 'N', 'E', 'S', 'W' ]

    def __init__(self):
        dllPath = os.path.join(
            os.path.dirname(__file__),
            '..')
        try:
            self.libbcalcdds = cdll.LoadLibrary(os.path.join(
                dllPath, 'libbcalcdds.dll'))
        except OSError:
            try:
                self.libbcalcdds = cdll.LoadLibrary(os.path.join(
                    dllPath, 'libbcalcdds.so'))
            except OSError:
                self.libbcalcdds = None
        if self.libbcalcdds is None:
            raise DllNotFoundException()

    def __getattr__(self, attrname):
        def _dynamic_method(*args):
            function = getattr(self.libbcalcdds, 'bcalcDDS_' + attrname)
            if attrname == 'new':
                function.restype = c_void_p
            else:
                if attrname == 'getLastError':
                    function.restype = c_char_p
                function.argtypes = [c_void_p]
            return function(*args)
        return _dynamic_method

    def declarerToLeader(self, player):
        return (player + 1) % 4
