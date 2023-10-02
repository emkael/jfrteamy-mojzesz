import io, json, logging, os, sys, time
import requests

from bcdd.PBNFile import PBNFile
from jfrteamy.db import TeamyDB


def get_digits(t):
    return int(''.join(i for i in t if i.isdigit()))


def clear():
    os.system('cls' if os.name == 'nt' else 'clear')


def get_config():
    with open('mojzesz.json') as config_file:
        config = json.load(config_file)
    return config


def setup_logging(config):
    logging_levels = [logging.WARNING, logging.INFO, logging.DEBUG]
    logging.basicConfig(
        level=logging_levels[config['settings'].get('info_messages', 0)],
        format= '%(levelname)s:\t%(message)s'
    )


def get_pbn_source(config):
    request_auth = None
    if 'auth' in config:
        request_auth = (config['auth'].get('user', ''), config['auth'].get('pass', ''))
    request_headers = config.get('headers', {})

    logging.info('Fetching %s', config['url'])
    r = requests.get(config['url'], auth=request_auth, headers=request_headers)
    r.raise_for_status()

    remote_content = r.text
    logging.info('Fetched %d bytes', len(remote_content))

    with io.StringIO(remote_content) as io_stream:
        f = PBNFile(io_stream)
    return f

def get_team_rosters(db):
    players = db.fetch_all('SELECT id, team, CONCAT(gname, " ", sname) FROM players')
    rosters = {}
    for player in players:
        team = player[1]
        if team not in rosters:
            rosters[team] = {}
        rosters[team][player[0]] = player[2]
    return rosters


def get_round_lineup(db, round_no, segment_no):
    db_tables = db.fetch_all('SELECT tabl, homet, visit FROM segments WHERE rnd = %s AND segment = %s', (
        round_no, segment_no
    ))
    round_lineup = {}
    for dbt in db_tables:
        round_lineup[dbt[0]] = dbt[1:]
    return round_lineup


def get_pbn_lineups(pbn, round_no):
    tables = {}
    for b in pbn.boards:
        if b.has_field('Round'):
            if b.get_field('Round') == str(round_no):
                table = b.get_field('Table')
                if table not in tables:
                    tables[table] = {}
                tables[table][b.get_field('Room')] = [
                    [b.get_field('North'), b.get_field('South')],
                    [b.get_field('East'), b.get_field('West')]
                ]
    return tables


def fetch_lineups(pbn, db, settings):
    rosters = get_team_rosters(db)
    tables = get_pbn_lineups(pbn, settings['teamy_round'])
    round_lineup = get_round_lineup(db, settings['teamy_round'], settings['teamy_segment'])

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
                # I have no idea how to name this variable,
                # it's something like "the room in which the currently processed team sits on NS if they're home and EW if away"
                roster = home_roster if which_room == 'open' else away_roster
                team = home_team if which_room == 'open' else away_team
                for i in range(0, 2):
                    player = lineup[1 - (room == which_room)][i]
                    player_id = None
                    for roster_id, roster_pl in roster.items():
                        if player == roster_pl:
                            player_id = roster_id
                            position = room + positions[1 - (room == which_room)][i]
                            logging.info('Player in lineup: Table %d, position %s, #%d %s',
                                         table, position, roster_id, roster_pl)
                            db.fetch(
                                'UPDATE segments SET '+position+' = %s WHERE rnd = %s AND segment = %s AND tabl = %s', (
                                    player_id,
                                    settings['teamy_round'], settings['teamy_segment'],
                                    table
                                )
                            )
                    if player_id is None:
                        logging.warning('Player %s not found in team %d', player, team)


def get_board_mapping(db, round_no, segment_no):
    board_mapping = {}
    for b in db.fetch_all('SELECT brd, bno FROM boards WHERE rnd = %s AND segment = %s', (
            round_no, segment_no)):
        board_mapping[b[1]] = b[0]
    return board_mapping


def get_current_db_score(db, round_no, segment_no, table, room, board_no):
    while True:
        current_score = db.fetch('SELECT declarer, contract, result, lead, score FROM scores ' +
                                 'WHERE rnd = %s AND segment = %s AND tabl = %s AND room = %s AND board = %s', (
                                     round_no, segment_no, table, room, board_no))
        if current_score:
            break
        logging.info('record in scores table does not exist - creating')
        db.fetch('INSERT INTO scores(rnd, segment, tabl, room, board, mecz, butler, processed, tims) VALUES(%s, %s, %s, %s, %s, 0, 0, 1, NOW())', (
            round_no, segment_no, table, room, board_no))
    return current_score


def get_pbn_score(b):
    declarer = b.get_field('Declarer')
    contract = b.get_field('Contract').replace('*', ' x').replace('x x', 'xx')
    if contract[0].isdigit():
        contract = contract[0] + ' ' + contract[1:]
        result = int(b.get_field('Result')) - get_digits(contract) - 6
        score = int(b.get_field('Score').replace('NS ', '')) # co z pasami?
        play_data = b.get_play_data()
        if play_data:
            play_data = ' '.join(play_data).split(' ')
            if play_data:
                lead = play_data[0].strip()
                lead = lead[0] + ' ' + lead[1]
    else: # passed-out hand
        contract = contract.upper()
        result = 0
        score = 0
    return declarer, contract, result, score, lead


def update_score(db, pbn_board, round_no, segment_no, table, room, board_no, real_board_no=None, overwrite=False):
    if real_board_no is None:
        real_board_no = board_no

    current_score = get_current_db_score(db, round_no, segment_no, table, room, board_no)
    declarer, contract, result, score, lead = get_pbn_score(pbn_board)

    update_score = True
    if current_score[4] is not None:
        if not overwrite:
            update_score = False
            if score != current_score[4]:
                logging.warning('result in board %d, table %d-%d changed and is NOT going to be overwritten!',
                                real_board_no, table, room)
            else:
                logging.info('not overwriting result in board %d, table %d-%d',
                             real_board_no, table, room)

    if update_score:
        params = (contract, declarer, result, lead, score)
        logging.info('updating result in board %d, table %d-%d: %s',
                     real_board_no, table, room, params)
        db.fetch('UPDATE scores SET contract = %s, declarer = %s, result = %s, lead = %s, score = %s, '+
                 'tims = NOW(), processed = 0, mecz = 1, butler = 1 '+
                 'WHERE rnd = %s AND segment = %s AND board = %s AND tabl = %s AND room = %s', (
                     params + (round_no, segment_no, board_no, table, room)))


def get_pbn_bidding(pbn):
    bidding = pbn.get_auction()
    return bidding[0], ' '.join(bidding[1:]).split(' ')


def get_lin_bidding(bidding):
    lin_bidding = []
    for bid in bidding:
        if bid.lower() == 'pass':
            lin_bidding.append('p')
            continue
        lin_bidding.append(bid.replace('NT', 'N'))
    lin_bidding = 'mb|'.join([bid + '|' for bid in lin_bidding]) + 'pg||'
    return lin_bidding


def get_html_bidding(bidding, dealer):
    html_bidding = []
    for bid in bidding:
        if bid.lower() == 'pass':
            html_bidding.append('pass')
            continue
        html_bid = bid.replace('NT', 'N')
        for suit in ['C', 'D', 'H', 'S', 'N']:
            html_bid = html_bid.replace(suit, "<img src='images/%s.gif'>" % (suit))
        html_bidding.append(html_bid)
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
    return html


def update_auction(db, pbn_board, round_no, segment_no, table, room, board_no, real_board_no=None):
    if real_board_no is None:
        real_board_no = board_no

    if not pbn_board.has_field('Auction'):
        logging.info('no bidding for board %d, table %d-%d',
                     real_board_no, table, room)
        return

    dealer, bidding = get_pbn_bidding(pbn_board)
    if dealer != pbn_board.get_field('Dealer'):
        logging.warning('bidding does not start from the dealer in board %d, table %d-%d',
                        real_board_no, table, room)

    html_bidding = get_html_bidding(bidding, dealer)
    lin_bidding = get_lin_bidding(bidding)

    logging.info('updating bidding in board %d, table %d-%d',
                 real_board_no, table, room)
    db.fetch('UPDATE scores SET auction = %s, bbo = %s, '+
            'tims = NOW(), processed = 0 '+
             'WHERE rnd = %s AND segment = %s AND board = %s AND tabl = %s AND room = %s', (
                 html_bidding, lin_bidding, round_no, segment_no, board_no, table, room))


def fetch_scores(pbn, db, settings):
    board_mapping = get_board_mapping(db, settings['teamy_round'], settings['teamy_segment'])
    for b in pbn.boards:
        if b.has_field('Round'):
            if b.get_field('Round') == str(settings['pbn_round']):
                board = int(b.get_field('Board'))

                if board not in board_mapping:
                    logging.error('board %d not meant to be played in segment %d-%d',
                                  board, settings['teamy_round'], settings['teamy_segment'])
                    continue

                board_no = board_mapping[board]
                table = get_digits(b.get_field('Table'))
                room = 1 if b.get_field('Room') == 'Open' else 2

                update_score(db, b, settings['teamy_round'], settings['teamy_segment'], table, room, board_no,
                             real_board_no=board, overwrite=settings['overwrite_scores'])

                update_auction(db, b, settings['teamy_round'], settings['teamy_segment'], table, room, board_no,
                               real_board_no=board)


def main_loop():
    settings = {}
    try:
        config = get_config()
        setup_logging(config)
        settings = config.get('settings', {})

        db = TeamyDB(config.get('mysql'))
        pbn = get_pbn_source(config.get('source'))

        if settings.get('fetch_lineups', 0) > 0:
            fetch_lineups(pbn, db, settings)

        fetch_scores(pbn, db, settings)
    except Exception as ex:
        logging.error(ex)

    return settings.get('job_interval', 60)


if __name__ == '__main__':
    while True:
        clear()
        interval = main_loop()
        logging.info('Waiting %d seconds...', interval)
        time.sleep(interval)
