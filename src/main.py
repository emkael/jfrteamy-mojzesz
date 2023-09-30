import io, json, logging, os, sys
import requests

from bcdd.PBNFile import PBNFile
from jfrteamy.db import TeamyDB


def get_digits(t):
    return int(''.join(i for i in t if i.isdigit()))


def clear():
    os.system('cls' if os.name == 'nt' else 'clear')


with open('mojzesz.json') as config_file:
    config = json.load(config_file)

logging_levels = [logging.WARNING, logging.INFO, logging.DEBUG]
logging.basicConfig(
     level=logging_levels[config['settings'].get('info_messages', 0)],
     format= '%(levelname)s:\t%(message)s'
 )

request_auth = None
if 'auth' in config['source']:
    request_auth = (config['source']['auth']['user'], config['source']['auth']['pass'])
request_headers = config['source'].get('headers', {})
r = requests.get(config['source']['url'], auth=request_auth, headers=request_headers)
r.raise_for_status()

with io.StringIO(r.text) as io_stream:
    f = PBNFile(io_stream)

db = TeamyDB(config['mysql'])

clear()

if config['settings']['fetch_lineups'] > 0:

    players = db.fetch_all('SELECT id, team, CONCAT(gname, " ", sname) FROM players')
    rosters = {}
    for player in players:
        team = player[1]
        if team not in rosters:
            rosters[team] = {}
        rosters[team][player[0]] = player[2]

    tables = {}
    for b in f.boards:
        if b.has_field('Round'):
            if b.get_field('Round') == str(config['settings']['pbn_round']):
                table = b.get_field('Table')
                if table not in tables:
                    tables[table] = {}
                tables[table][b.get_field('Room')] = [
                    [b.get_field('North'), b.get_field('South')],
                    [b.get_field('East'), b.get_field('West')]
                ]

    db_tables = db.fetch_all('SELECT tabl, homet, visit FROM segments WHERE rnd = %s AND segment = %s', (
        config['settings']['teamy_round'],
        config['settings']['teamy_segment']
    ))
    round_lineup = {}
    for dbt in db_tables:
        round_lineup[dbt[0]] = dbt[1:]

    for t, rooms in tables.items():
        table = get_digits(t)
        home_team = round_lineup[table][0]
        away_team = round_lineup[table][1]
        home_roster = rosters[home_team]
        away_roster = rosters[away_team]
        lineups = {}
        positions = [['N', 'S'], ['E', 'W']]
        for room, lineup in rooms.items():
            room = room.lower().replace('closed', 'close')
            for which_room in ['open', 'close']:
                roster = home_roster if which_room == 'open' else away_roster
                team = home_team if which_room == 'open' else away_team
                for i in range(0, 2):
                    player = lineup[1 - (room == which_room)][i]
                    player_id = None
                    for roster_id, roster_pl in roster.items():
                        if player == roster_pl:
                            player_id = roster_id
                            position = room + positions[1 - (room == which_room)][i]
                            logging.info('Player in lineup: Table %d, position %s, #%d %s' % (
                                table, position,
                                roster_id, roster_pl))
                            db.fetch(
                                'UPDATE segments SET '+position+' = %s WHERE rnd = %s AND segment = %s AND tabl = %s', (
                                    player_id,
                                    config['settings']['teamy_round'], config['settings']['teamy_segment'],
                                    table
                                )
                            )
                    if player_id is None:
                        logging.warning('Player %s not found in team %d', (player, team))

board_mapping = {}
for b in db.fetch_all('SELECT brd, bno FROM boards WHERE rnd = %s AND segment = %s', (
        config['settings']['teamy_round'], config['settings']['teamy_segment'])):
    board_mapping[b[1]] = b[0]

for b in f.boards:
    if b.has_field('Round'):
        if b.get_field('Round') == str(config['settings']['pbn_round']):
            board = int(b.get_field('Board'))
            if board not in board_mapping:
                logging.error('board %d not meant to be played in segment %d-%d' % (
                    board, config['settings']['teamy_round'], config['settings']['teamy_segment']))
                continue
            board_no = board_mapping[board]
            table = get_digits(b.get_field('Table'))
            room = 1 if b.get_field('Room') == 'Open' else 2
            while True:
                current_score = db.fetch('SELECT declarer, contract, result, lead, score FROM scores ' +
                                         'WHERE rnd = %s AND segment = %s AND tabl = %s AND room = %s AND board = %s', (
                                             config['settings']['teamy_round'], config['settings']['teamy_segment'],
                                             table, room, board_no))
                if current_score:
                    break
                logging.info('record in scores table does not exist - creating')
                db.fetch('INSERT INTO scores(rnd, segment, tabl, room, board, mecz, butler, processed, tims) VALUES(%s, %s, %s, %s, %s, 0, 0, 1, NOW())', (
                    config['settings']['teamy_round'], config['settings']['teamy_segment'],
                    table, room, board_no))

            declarer = b.get_field('Declarer')
            contract = b.get_field('Contract').replace('*', ' x').replace('x x', 'xx')
            if contract[0].isdigit():
                contract = contract[0] + ' ' + contract[1:]
                result = int(b.get_field('Result')) - get_digits(contract) - 6
                score = int(b.get_field('Score').replace('NS ', '')) # co z pasami?
            else: # passed-out hand
                contract = contract.upper()
                result = 0
                score = 0
            lead = '' # wtf?

            update_score = True
            if current_score[4] is not None:
                if not config['settings']['overwrite_scores']:
                    update_score = False
                    if score != current_score[4]:
                        logging.warning('result in board %d, table %d-%d changed and is not going to be overwritten!' % (
                            board, table, room))
                    else:
                        logging.info('not overwriting result in board %d, table %d-%d' % (
                            board, table, room))
            if update_score:
                params = (contract, declarer, result, lead, score)
                logging.info('updating result in board %d, table %d-%d: %s' % (
                            board, table, room, params))
                db.fetch('UPDATE scores SET contract = %s, declarer = %s, result = %s, lead = %s, score = %s, '+
                         'tims = NOW(), processed = 0, mecz = 1, butler = 1 '+
                         'WHERE rnd = %s AND segment = %s AND board = %s AND tabl = %s AND room = %s', (
                    params + (config['settings']['teamy_round'], config['settings']['teamy_segment'], board_no, table, room)))

            if not b.has_field('Auction'):
                logging.info('no bidding for board %d, table %d-%d' % (
                    board, table, room))
                continue
            bidding = b.get_auction()
            dealer = bidding[0]
            if dealer != b.get_field('Dealer'):
                logging.warning('bidding does not start from the dealer in board %d, table %d-%d' % (
                    board, table, room))
            bidding = ' '.join(bidding[1:]).split(' ')
            html_bidding = []
            lin_bidding = []
            for bid in bidding:
                if bid == 'Pass':
                    lin_bidding.append('p')
                    html_bidding.append('pass')
                    continue
                bid = bid.replace('NT', 'N')
                html_bid = bid
                for suit in ['C', 'D', 'H', 'S', 'N']:
                    html_bid = html_bid.replace(suit, "<img src='images/%s.gif'>" % (suit))
                html_bidding.append(html_bid)
                lin_bidding.append(bid)
            lin_bidding = 'mb|'.join([bid + '|' for bid in lin_bidding]) + 'pg||'
            players = ['W', 'N', 'E', 'S']
            html_bidding = ['&nbsp;'] * players.index(dealer) + html_bidding + ['&nbsp;'] * ((4 - players.index(dealer)) % 4)
            html = "<table border=0><tr><td align='center'>&nbsp;&nbsp;&nbsp;W&nbsp;&nbsp;&nbsp;</td><td align='center'>&nbsp;&nbsp;&nbsp;N&nbsp;&nbsp;&nbsp;</td><td align='center'>&nbsp;&nbsp;&nbsp;E&nbsp;&nbsp;&nbsp;</td><td align='center'>&nbsp;&nbsp;&nbsp;S&nbsp;&nbsp;&nbsp;</td></tr>"
            for i in range(0, len(html_bidding)):
                if i % 4 == 0:
                    html += '<tr>'
                html += "<td align='center'>"
                html += html_bidding[i]
                html += "</td>"
                if i % 4 == 3:
                    html += "</tr>"
            html += '</table>'
            logging.info('updating bidding in board %d, table %d-%d' % (
                board, table, room))
            db.fetch('UPDATE scores SET auction = %s, bbo = %s, '+
                     'tims = NOW(), processed = 0 '+
                     'WHERE rnd = %s AND segment = %s AND board = %s AND tabl = %s AND room = %s', (
                         html, lin_bidding, config['settings']['teamy_round'], config['settings']['teamy_segment'], board_no, table, room))
