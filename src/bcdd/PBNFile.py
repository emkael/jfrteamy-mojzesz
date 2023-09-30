import shutil
import tempfile

from .PBNBoard import PBNBoard

class PBNFile(object):

    def __init__(self, filename):
        self._filename = filename
        self.output_file = None
        self.boards = []
        lines = []
        with open(self._filename) as pbn_file:
            contents = pbn_file.readlines()
        first_line = 1
        for line_no in range(0, len(contents)):
            line = contents[line_no].strip()
            if not line:
                if len(lines) > 0:
                    self.boards.append(PBNBoard(lines, first_line))
                    lines = []
                    first_line = line_no + 2
            else:
                lines.append(line)
        if len(lines) > 0:
            self.boards.append(PBNBoard(lines, first_line))
        if not self.boards[0].has_field('Event'):
            self.boards[0].write_event('')

    def write_board(self, board):
        if self.output_file is None:
            self.output_file = tempfile.NamedTemporaryFile(
                mode='w', delete=False)
        for field in board.fields:
            self.output_file.write(field.raw_field + '\r\n')
        self.output_file.write('\r\n')

    def save(self):
        if self.output_file is None:
            raise IOError('No boards written to PBN file, unable to save it.')
        tmp_path = self.output_file.name
        self.output_file.close()
        shutil.move(tmp_path, self._filename)
