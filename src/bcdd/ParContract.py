import functools

from .BCalcWrapper import BCalcWrapper as bcw
from .Exceptions import ParScoreInvalidException


class ParContract(object):
    def __init__(self, level=0, denom='', declarer='', doubled=False, score=0):
        self.level = level
        self.denomination = denom
        self.declarer = declarer
        self.doubled = doubled
        self.score = score

    def validate(self):
        if self.score == 0:
            return self
        if (self.level < 1) or (self.level > 7):
            raise ParScoreInvalidException(
                'Invalid par contract level: %d' % (self.level))
        if self.denomination not in 'CDHSN':
            raise ParScoreInvalidException(
                'Invalid par contract denomination: ' + self.denomination)
        if self.declarer not in 'NESW':
            raise ParScoreInvalidException(
                'Invalid par contract declarer: ' + self.declarer)
        return self

    def __repr__(self):
        if self.score == 0:
            return 'PASS'
        return '%d%s%s %s %+d' % (
            self.level,
            self.denomination,
            'x' if self.doubled else '',
            self.declarer,
            self.score)

    def __eq__(self, other):
        return hash(self) == hash(other)

    def __hash__(self):
        return self.score + self.level + 10000 * (
            ord(self.denomination[0]) if self.denomination else 0)

    def calculate_score(self, tricks, vulnerable=False):
        if self.level == 0:
            return 0
        score = 0
        if self.level + 6 > tricks:
            undertricks = self.level + 6 - tricks
            if self.doubled:
                while True:
                    if undertricks == 1:
                        # first undertrick: 100 non-vul, 200 vul
                        score -= 200 if vulnerable else 100
                    else:
                        if (undertricks <= 3) and not vulnerable:
                            # second non-vul undertrick: 200
                            score -= 200
                        else:
                            # further undertricks: 300
                            score -= 300
                    undertricks -= 1
                    if undertricks == 0:
                        break;
            else:
                score = -100 if vulnerable else -50
                score *= undertricks
        else:
            par_tricks = self.level
            while True:
                if (self.denomination == 'N') and (par_tricks == 1):
                    # first non-trump trick: 40
                    score += 40
                else:
                    # other tricks
                    score += 30 if self.denomination in 'NSH' else 20
                par_tricks -= 1
                if par_tricks == 0:
                    break
            overtricks = tricks - self.level - 6
            if self.doubled:
                score *= 2
                score += 50
            # game premium
            score += (500 if vulnerable else 300) if (score >= 100) else 50
            if self.doubled:
                score += overtricks * (200 if vulnerable else 100)
            else:
                score += overtricks * (20 if self.denomination in 'CD' else 30)
            if self.level == 7:
                # grand slam premium
                score += 1500 if vulnerable else 1000
            elif self.level == 6:
                # small slam premium
                score += 750 if vulnerable else 500
        if self.declarer in 'EW':
            score = -score
        return score

    def __gt__(self, other):
        denomination = bcw.DENOMINATIONS.index(self.denomination) \
                       if self.denomination in bcw.DENOMINATIONS \
                          else -1
        other_denomination = bcw.DENOMINATIONS.index(
            other.denomination) \
            if other.denomination in bcw.DENOMINATIONS else -1
        return (self.level > other.level) \
            or ((self.level == other.level) \
                and (denomination > other_denomination))

    def get_defense(self, dd_table, vulnerable):
        declarer_index = bcw.PLAYERS.index(self.declarer) \
                         if self.declarer in bcw.PLAYERS else -1
        denomination_index = bcw.DENOMINATIONS.index(self.denomination) \
                             if self.denomination in bcw.DENOMINATIONS else -1
        if (self.level != 0) \
           and (self.level + 6
                <= dd_table[declarer_index][denomination_index]):
            defenders_indexes = []
            defenders_indexes.append((declarer_index + 1) % 4);
            defenders_indexes.append((declarer_index + 3) % 4);
            possible_defense = []
            score_squared = self.score * self.score
            for i in range(0, 5):
                level = self.level
                if i <= denomination_index:
                    level += 1
                if level <= 7:
                    for defender in defenders_indexes:
                        if level + 6 > dd_table[defender][i]:
                            defense = ParContract(
                                level,
                                bcw.DENOMINATIONS[i],
                                bcw.PLAYERS[defender],
                                True,
                                0)
                            defense.score = defense.calculate_score(
                                dd_table[defender][i],
                                vulnerable)
                            if score_squared > self.score * defense.score:
                                possible_defense.append(defense)
            if possible_defense:
                possible_defense.sort(
                    key=lambda x: abs(x.score - self.score))
                optimum_defense = possible_defense[-1]
                possible_defense = [defense for defense in possible_defense
                                    if defense.score == optimum_defense.score]
                for defense in possible_defense:
                    # Lowest from the most profitable sacrifices
                    if optimum_defense > defense:
                        optimum_defense = defense
                return optimum_defense
        return None
