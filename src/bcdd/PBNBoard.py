import re

from .Exceptions import FieldNotFoundException, DDTableInvalidException


class PBNField(object):

    def __init__(self, key=None, value=None, raw_data=None):
        self.key = key
        self.value = value
        self.raw_field = '[%s "%s"]' % (self.key, str(self.value)) \
                         if self.key is not None else raw_data

class PBNBoard(object):

    line_pattern = re.compile(r'\[(.*) "(.*)"\]')
    ability_pattern = re.compile(r'\b([NESW]):([0-9A-D]{5})\b')
    optimum_result_table_pattern = re.compile(
        r'^([NESW])\s+([CDHSN])T?\s+(\d+)$')

    DENOMINATIONS = [ 'C', 'D', 'H', 'S', 'N' ]
    PLAYERS = [ 'N', 'E', 'S', 'W' ]

    def __init__(self, lines, line_no=None):
        self.line_number = line_no
        self._has_optimum_result_table = None
        self._has_ability = None
        self.fields = []
        for line in lines:
            field = PBNField(raw_data=line)
            line_parse = self.line_pattern.match(line)
            if line_parse:
                field.key = line_parse.group(1)
                field.value = line_parse.group(2)
            self.fields.append(field)

    def has_field(self, key):
        for field in self.fields:
            if key == field.key:
                return True
        return False

    def get_field(self, key, default=None):
        for field in self.fields:
            if key == field.key:
                return field.value
        if default is not None:
            return default
        raise FieldNotFoundException(key + ' field not found')

    def delete_field(self, key):
        to_remove = []
        for field in self.fields:
            if key == field.key:
                to_remove.append(field)
        for remove in to_remove:
            self.fields.remove(remove)

    def get_event(self):
        return self.get_field('Event')

    def write_event(self, name):
        for i in range(0, len(self.fields)):
            if 'Board' == self.fields[i].key:
                self.fields.insert(i, PBNField(key='Event', value=name))
                break

    def get_layout(self):
        return self.get_field('Deal')

    def get_number(self):
        return self.get_field('Board')

    def get_vulnerable(self):
        return self.get_field('Vulnerable')

    def get_dealer(self):
        return self.get_field('Dealer')

    def validate_ability(self, ability):
        matches = self.ability_pattern.findall(ability)
        if not len(matches):
            self._has_ability = False
            raise DDTableInvalidException('Invalid Ability line: ' + ability)
        players = []
        for match in matches:
            if match[0] in players:
                self._has_ability = False
                raise DDTableInvalidException(
                    'Duplicate entry in Ability: ' + match[0])
            else:
                players.append(match[1])
        self._has_ability = False
        return matches

    def get_ability(self):
        return self.get_field('Ability')

    def delete_ability(self):
        self.delete_field('Ability')

    def write_ability(self, dd_table):
        sb = ''
        for i in range(0, 4):
            sb += PBNBoard.PLAYERS[i]
            sb += ':'
            sb += ''.join(['%X' % (j) for j in dd_table[i]])[::-1]
            sb += ' '
        self.fields.append(PBNField(key='Ability', value=sb.strip()))

    def get_minimax(self):
        return self.get_field('Minimax')

    def delete_minimax(self):
        self.delete_field('Minimax')

    def write_minimax(self, contract):
        minimax = '7NS0' if contract.score == 0 \
                  else '%d%s%s%s%d' % (
                          contract.level,
                          contract.denomination,
                          'D' if contract.doubled else '',
                          contract.declarer,
                          contract.score)
        self.fields.append(PBNField(key='Minimax', value=minimax))

    def get_optimum_score(self):
        return self.get_field('OptimumScore')

    def delete_optimum_score(self):
        self.delete_field('OptimumScore')

    def write_optimum_score(self, contract):
        self.fields.append(
            PBNField(key='OptimumScore',
                     value='NS %d' % (contract.score)))

    def get_optimum_result(self):
        return self.get_field('OptimumResult')

    def validate_optimum_result_table(self, table):
        matches = []
        duplicates = []
        for line in table:
            match = self.optimum_result_table_pattern.match(line)
            if not match:
                self._has_optimum_result_table = False
                raise DDTableInvalidException(
                    'Invalid OptimumResultTable line: ' + line)
            position = match.group(1) + ' - ' + match.group(2)
            if position in duplicates:
                self._has_optimum_result_table = False
                raise DDTableInvalidException(
                    'Duplicate OptimumResultTable line: ' + line)
            else:
                duplicates.append(position)
            matches.append(match)
        self._has_optimum_result_table = True
        return matches

    def get_optimum_result_table(self):
        try:
            return self.get_extended_raw_field('OptimumResultTable')
        except FieldNotFoundException:
            self._has_optimum_result_table = False
            raise

    def get_auction(self):
        return self.get_extended_raw_field('Auction', with_header=True)

    def get_play_data(self):
        if self.has_field('Play'):
            return self.get_extended_raw_field('Play', with_header=False)
        return None

    def get_extended_raw_field(self, field_name, with_header=False):
        field_found = False
        result = []
        for field in self.fields:
            if field_name == field.key:
                field_found = True
                if with_header:
                    result.append(field.value)
            else:
                if field_found:
                    if field.key is None:
                        result.append(field.raw_field)
                    else:
                        break
        if not field_found:
            raise FieldNotFoundException('%s field not found' % (field_name))
        return result

    def delete_optimum_result_table(self):
        field_found = False
        to_remove = []
        for field in self.fields:
            if 'OptimumResultTable' == field.key:
                field_found = True
                to_remove.append(field)
            else:
                if field_found:
                    if field.key is None:
                        to_remove.append(field)
                    else:
                        break
        for remove in to_remove:
            self.fields.remove(remove)

    def write_optimum_result_table(self, dd_table):
        self.fields.append(PBNField(
            key='OptimumResultTable',
            value=r'Declarer;Denomination\2R;Result\2R'))
        for i in range(0, 4):
            for j in range(0, 5):
                self.fields.append(PBNField(
                    raw_data='%s %s%s %d' % (
                        PBNBoard.PLAYERS[i],
                        PBNBoard.DENOMINATIONS[j],
                        'T' if PBNBoard.DENOMINATIONS[j] == 'N' else '',
                        dd_table[i][j])))

    def save_par_contract(self, contract, jfr_only=False):
        if not jfr_only:
            self.delete_optimum_score()
            self.write_optimum_score(contract)
        self.delete_minimax()
        self.write_minimax(contract)

    def save_dd_table(self, dd_table, jfr_only=False):
        if not jfr_only:
            if self._has_optimum_result_table is None:
                try:
                    optimum_result_table = self.validate_optimum_result_table(
                        self.get_optimum_result_table())
                    self._has_optimum_result_table = True
                except FieldNotFoundException:
                    self._has_optimum_result_table = False
            if not self._has_optimum_result_table:
                self.delete_optimum_result_table()
                self.write_optimum_result_table(dd_table)
        if self._has_ability is None:
            try:
                ability = self.validate_ability(
                    self.get_ability())
                self._has_ability = True
            except FieldNotFoundException:
                self._has_ability = False
        if not self._has_ability:
            self.delete_ability()
            self.write_ability(dd_table)
