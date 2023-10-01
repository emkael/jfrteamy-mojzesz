import re

from .PBNBoard import PBNBoard as pbb
from .ParContract import ParContract
from .Exceptions import FieldNotFoundException


class ParScore(object):
    _pbn_contract_pattern = re.compile(r'(\d)([CDHSN])(X?)\s+([NESW])')
    _pbn_score_pattern = re.compile(r'(NS|EW)\s+(-?\d})')
    _jfr_contract_pattern = re.compile(r'^(\d)([CDHSN])(D?)([NESW])(-?\d+)$')

    def __init__(self, board):
        self._board = board

    def get_pbn_par_contract(self):
        contract_field = self._board.get_optimum_result()
        if 'Pass' == contract_field:
            return ParContract()
        contract_match = self._pbn_contract_pattern.match(contract_field)
        if not contract_match:
            raise ParScoreInvalidException(
                'Invalid format for OptimumResult field: ' + contract_field)
        score_field = self._board.get_optimum_score()
        score_match = self._pbn_score_pattern.match(score_field)
        if not score_match:
            raise ParScoreInvalidException(
                'Invalid format for OptimumScore field: ' + scoreField)
        score = int(score_match.group(2))
        if 'EW' == score_match.group(1):
            score = -score
        contract = ParContract(
            int(contract_match.group(1)),
            contract_match.group(2)[0],
            contract_match.group(4)[0],
            'X' == contract_match.group(3),
            score)
        return contract.validate()

    def get_jfr_par_contract(self):
        par_string = self._board.get_minimax()
        par_match = self._jfr_contract_pattern.match(par_string)
        if not par_match:
            raise ParScoreInvalidException(
                'Invalid format for Minimax field: ' + par_string)
        if '0' == par_match.group(4):
            return ParContract() # pass-out
        contract = ParContract(
            int(par_match.group(1)),
            par_match.group(2)[0],
            par_match.group(4)[0],
            'D' == par_match.group(3),
            int(par_match.group(5)))
        return contract.validate()

    def _determine_vulnerability(self, vulnerability, declarer):
        vulnerability = vulnerability.upper()
        return vulnerability in ['ALL', 'BOTH'] \
            or (vulnerability not in ['LOVE', 'NONE'] \
                and declarer in vulnerability)

    def _get_highest_makeable_contract(self, dd_table,
                                       for_ns=True, for_ew=True):
        contract = ParContract()
        tricks = 0
        for i in range(3, -1, -1):
            if ((i % 2 == 0) and for_ns) \
               or ((i % 2 == 1) and for_ew):
                for j in range(0, 5):
                    level = dd_table[i][j] - 6
                    denomination = pbb.DENOMINATIONS.index(
                        contract.denomination) \
                        if contract.denomination in pbb.DENOMINATIONS \
                           else -1
                    if (level > contract.level) \
                       or ((level == contract.level) \
                           and (j > denomination)):
                        contract.level = level
                        contract.denomination = pbb.DENOMINATIONS[j]
                        contract.declarer = pbb.PLAYERS[i]
                        tricks = dd_table[i][j]
        vulnerability = self._board.get_vulnerable().upper()
        vulnerable = self._determine_vulnerability(
            vulnerability, contract.declarer)
        contract.score = contract.calculate_score(tricks, vulnerable)
        return contract

    def get_dd_table_par_contract(self, dd_table):
        dealer = self._board.get_dealer()
        vulnerability = self._board.get_vulnerable().upper()
        ns_highest = self._get_highest_makeable_contract(
            dd_table, True, False);
        ew_highest = self._get_highest_makeable_contract(
            dd_table, False, True)
        if ns_highest == ew_highest:
            return ns_highest.validate() \
                if dealer in ['N', 'S'] else ew_highest.validate()
        highest = max(ns_highest, ew_highest)
        other_side_highest = min(ew_highest, ns_highest)
        ns_playing = highest.declarer in ['N', 'S']
        defense_vulnerability = self._determine_vulnerability(
            vulnerability, 'E' if ns_playing else 'N')
        highest_defense = highest.get_defense(dd_table, defense_vulnerability)
        if highest_defense is not None:
            # Highest contract has profitable defense
            return highest_defense.validate()
        denomination_index = pbb.DENOMINATIONS.index(highest.denomination) \
                             if highest.denomination in pbb.DENOMINATIONS \
                                else -1
        declarer_index = pbb.PLAYERS.index(highest.declarer) \
                         if highest.declarer in pbb.PLAYERS else -1
        player_indexes = [declarer_index, (declarer_index + 2) % 4]
        vulnerable = self._determine_vulnerability(
            vulnerability, highest.declarer)
        score_squared = highest.score * highest.score
        possible_optimums = []
        for i in range(0, 5):
            for player in player_indexes:
                level = highest.level
                if i > denomination_index:
                    level -= 1
                while level > 0:
                    contract = ParContract(
                        level,
                        pbb.DENOMINATIONS[i],
                        pbb.PLAYERS[player],
                        False, 0)
                    contract.score = contract.calculate_score(
                        dd_table[player][i], vulnerable)
                    if other_side_highest > contract:
                        # Contract is lower than other side's contract
                        break
                    if (highest.score * contract.score) > 0:
                        # Contract makes
                        if abs(contract.score) >= abs(highest.score):
                            # Contract is profitable
                            defense = contract.get_defense(
                                dd_table, defense_vulnerability)
                            if defense is not None \
                               and (contract.score * contract.score) \
                               > (contract.score * defense.score):
                                # Contract has defense
                                possible_optimums.append(defense)
                                # So lower contracts will too.
                                break
                            else:
                                # Contract does not have defense
                                possible_optimums.append(contract)
                        else:
                            # Contract is not profitable
                            break
                    level -= 1
        for contract in possible_optimums:
            if abs(contract.score) > abs(highest.score):
                # Contract is more profitable
                highest = contract
            else:
                if contract.score == highest.score:
                    if highest > contract:
                        # Equally profitable, but lower
                        highest = contract
        return highest.validate()

    def get_par_contract(self, dd_table):
        try:
            return self.get_jfr_par_contract()
        except FieldNotFoundException:
            try:
                return self.get_pbn_par_contract()
            except FieldNotFoundException:
                return self.get_dd_table_par_contract(dd_table)
