from ctypes import c_char_p
from copy import copy

from .BCalcWrapper import BCalcWrapper
from .Exceptions import DDTableInvalidException, FieldNotFoundException


class DDTable(object):

    def _get_empty_table(self):
        table = []
        row = [-1] * 5
        for col in range(0, 4):
            table.append(copy(row))
        return table

    def _validate_table(self, table):
        for row in table:
            for t in row:
                if (t > 13) or (t < 0):
                    raise DDTableInvalidException(
                        'Invalid number of tricks: %d' % (t)
                    )
        return table

    _banner_displayed = False

    def __init__(self, board):
        self._board = board;
        self._wrapper = BCalcWrapper()

    def _check_for_error(self, solver):
        error = self._wrapper.getLastError(solver)
        if error:
            raise DDTableInvalidException(
                'BCalc error: %s' % (c_char_p(error).value.decode('ascii')))

    def get_bcalc_table(self, show_banner=True):
        if not DDTable._banner_displayed and show_banner:
            print('Double dummy analysis provided by BCalc.')
            print('BCalc is awesome, check it out: http://bcalc.w8.pl')
            DDTable._banner_displayed = True
        result = self._get_empty_table()
        deal = self._board.get_layout()
        solver = self._wrapper.new(b"PBN", deal.encode(), 0, 0)
        self._check_for_error(solver)
        for denom in range(0, 5):
            self._wrapper.setTrumpAndReset(solver, denom)
            for player in range(0, 4):
                leader = self._wrapper.declarerToLeader(player)
                self._wrapper.setPlayerOnLeadAndReset(solver, leader)
                result[player][denom] = 13 - self._wrapper.getTricksToTake(
                    solver)
                self._check_for_error(solver)
        self._wrapper.delete(solver);
        return self._validate_table(result)

    def get_jfr_table(self):
        result = self._get_empty_table()
        ability = self._board.get_ability()
        abilities = self._board.validate_ability(ability)
        for player_ability in abilities:
            player = player_ability[0]
            player_id = BCalcWrapper.PLAYERS.index(player)
            denom_id = 4
            for tricks in player_ability[1]:
                result[player_id][denom_id] = int(tricks, 16)
                denom_id -= 1
        return self._validate_table(result)

    def get_pbn_table(self):
        table = self._board.get_optimum_result_table()
        parsed_table = self._board.validate_optimum_result_table(table)
        result = self._get_empty_table()
        for line_match in parsed_table:
            player = line_match.group(1)[0]
            denom = line_match.group(2)[0]
            tricks = int(line_match.group(3))
            player_id = BCalcWrapper.PLAYERS.index(player)
            denom_id = BCalcWrapper.DENOMINATIONS.index(denom)
            result[player_id][denom_id] = tricks
        return self._validate_table(result)

    def get_dd_table(self, show_banner=True):
        try:
            return self.get_jfr_table()
        except FieldNotFoundException:
            try:
                return self.get_pbn_table()
            except FieldNotFoundException:
                return self.get_bcalc_table(show_banner)

    def print_table(self, dd_table):
        print('\t' + '\t'.join(BCalcWrapper.DENOMINATIONS))
        for i in range(0, 4):
            print('%s%s' % (
                self._wrapper.PLAYERS[i],
                ''.join(['\t' + str(tricks) for tricks in dd_table[i]])))
