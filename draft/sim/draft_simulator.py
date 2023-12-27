from db.dbcontext import get_db_client
from pymongo import MongoClient
from config.ffconfig import get_env_config

cfg = get_env_config()

#TODO clean this up
def simulate_draft(db_client: MongoClient=get_db_client()):
    print('resetting rosters')
    reset_rosters(db_client)
    manager_collection = db_client[cfg['MongoAppDbName']]['manager']
    player_collection = db_client[cfg['MongoAppDbName']]['player']
    print('pulling draft board')
    draft_board = sorted(list(player_collection.find()), key=lambda p: p['rank'])
    print('pulling managers')
    managers = list(manager_collection.find())
    on_the_clock_ix = 0
    player_scan_ix = 0
    first_pick = True
    in_reverse = False
    managers_that_are_done = []
    while len(managers_that_are_done) < len(managers):
        pick_made = False
        mgr_on_the_clock = managers[on_the_clock_ix]
        if mgr_on_the_clock in managers_that_are_done:
            pick_made = True
        else:
            scanned_player = draft_board[player_scan_ix]
            if scanned_player['position'][0] == 'WR' and mgr_on_the_clock['pos_counts']['WR'] < 8:
                if mgr_on_the_clock['roster']['WR1'] is None:
                    pick = draft_board.pop(player_scan_ix)
                    del pick['acqStatus']
                    del pick['owner']
                    pick['_id'] = str(pick['_id'])
                    pick_made = True
                    print(f"{mgr_on_the_clock['code']} picks {pick['name']} ({pick['position'][0]}) to WR1")
                    mgr_on_the_clock['roster']['WR1'] = pick
                    mgr_on_the_clock['pos_counts']['WR'] += 1
                    player_scan_ix = -1
                elif mgr_on_the_clock['roster']['WR2'] is None:
                    pick = draft_board.pop(player_scan_ix)
                    del pick['acqStatus']
                    del pick['owner']
                    pick['_id'] = str(pick['_id'])
                    pick_made = True
                    print(f"{mgr_on_the_clock['code']} picks {pick['name']} ({pick['position'][0]}) to WR2")
                    mgr_on_the_clock['roster']['WR2'] = pick
                    mgr_on_the_clock['pos_counts']['WR'] += 1
                    player_scan_ix = -1
                elif mgr_on_the_clock['roster']['FLEX1'] is None:
                    pick = draft_board.pop(player_scan_ix)
                    del pick['acqStatus']
                    del pick['owner']
                    pick['_id'] = str(pick['_id'])
                    pick_made = True
                    print(f"{mgr_on_the_clock['code']} picks {pick['name']} ({pick['position'][0]}) to FLEX1")
                    mgr_on_the_clock['roster']['FLEX1'] = pick
                    mgr_on_the_clock['pos_counts']['WR'] += 1
                    player_scan_ix = -1
                elif mgr_on_the_clock['roster']['FLEX2'] is None:
                    pick = draft_board.pop(player_scan_ix)
                    del pick['acqStatus']
                    del pick['owner']
                    pick['_id'] = str(pick['_id'])
                    pick_made = True
                    print(f"{mgr_on_the_clock['code']} picks {pick['name']} ({pick['position'][0]}) to FLEX2")
                    mgr_on_the_clock['roster']['FLEX2'] = pick
                    mgr_on_the_clock['pos_counts']['WR'] += 1
                    player_scan_ix = -1
            elif scanned_player['position'][0] != 'WR' and mgr_on_the_clock['roster'][scanned_player['position'][0]] is None \
                    and mgr_on_the_clock['pos_counts'][scanned_player['position'][0]] < \
                    dict({'QB': 4, 'RB': 8, 'TE': 4, 'DST': 2, 'HC': 2})[scanned_player['position'][0]]:
                pick = draft_board.pop(player_scan_ix)
                del(pick['acqStatus'])
                del(pick['owner'])
                pick['_id'] = str(pick['_id'])
                pick_made = True
                print(f"{mgr_on_the_clock['code']} picks {pick['name']} ({pick['position'][0]}) to {scanned_player['position'][0]}")
                mgr_on_the_clock['roster'][scanned_player['position'][0]] = pick
                mgr_on_the_clock['pos_counts'][scanned_player['position'][0]] += 1
                player_scan_ix = -1
            elif scanned_player['position'][0] in ['RB', 'TE'] \
                    and mgr_on_the_clock['pos_counts'][scanned_player['position'][0]] < \
                    dict({'RB': 8, 'TE': 4})[scanned_player['position'][0]]:
                if mgr_on_the_clock['roster']['FLEX1'] is None:
                    pick = draft_board.pop(player_scan_ix)
                    del pick['acqStatus']
                    del pick['owner']
                    pick['_id'] = str(pick['_id'])
                    pick_made = True
                    print(f"{mgr_on_the_clock['code']} picks {pick['name']} ({pick['position'][0]}) to FLEX1")
                    mgr_on_the_clock['roster']['FLEX1'] = pick
                    mgr_on_the_clock['pos_counts'][scanned_player['position'][0]] += 1
                    player_scan_ix = -1
                elif mgr_on_the_clock['roster']['FLEX2'] is None:
                    pick = draft_board.pop(player_scan_ix)
                    del pick['acqStatus']
                    del pick['owner']
                    pick['_id'] = str(pick['_id'])
                    pick_made = True
                    print(f"{mgr_on_the_clock['code']} picks {pick['name']} ({pick['position'][0]}) to FLEX2")
                    mgr_on_the_clock['roster']['FLEX2'] = pick
                    mgr_on_the_clock['pos_counts'][scanned_player['position'][0]] += 1
                    player_scan_ix = -1
            if not pick_made:
                if len(mgr_on_the_clock['roster']['BENCH']) < 7 and mgr_on_the_clock['pos_counts'][scanned_player['position'][0]] < \
                        dict({'QB': 4, 'RB': 8, 'WR': 8, 'TE': 4, 'DST': 2, 'HC': 2})[scanned_player['position'][0]]:
                    pick = draft_board.pop(player_scan_ix)
                    del pick['acqStatus']
                    del pick['owner']
                    pick['_id'] = str(pick['_id'])
                    pick_made = True
                    print(f"{mgr_on_the_clock['code']} picks {pick['name']} ({pick['position'][0]}) to BENCH")
                    mgr_on_the_clock['roster']['BENCH'].append(pick)
                    mgr_on_the_clock['pos_counts'][scanned_player['position'][0]] += 1
                    player_scan_ix = -1
            player_scan_ix += 1
            if roster_is_full(mgr_on_the_clock['roster']):
                print(f"{mgr_on_the_clock['code']} is now done.")
                managers_that_are_done.append(mgr_on_the_clock)
        if pick_made:
            if first_pick:
                first_pick = False
                on_the_clock_ix += 1
            elif in_reverse:
                if on_the_clock_ix == 0:
                    in_reverse = False
                else:
                    on_the_clock_ix -= 1
            else:
                if on_the_clock_ix == 11:
                    in_reverse = True
                else:
                    on_the_clock_ix += 1
    print("Draft done!  Saving to DB now.")
    for manager in managers_that_are_done:
        manager_collection.update_one(
            {'code': manager['code']},
            {'$set': {'roster': manager['roster']}}
        )
        for poskey in manager['roster'].keys():
            if poskey not in ['BENCH', 'IR']:
                player_collection.update_one(
                    {'publicId': manager['roster'][poskey]['publicId']},
                    {'$set': {'owner': manager['code']}}
                )
            elif poskey == 'BENCH':
                for bench_player in manager['roster']['BENCH']:
                    player_collection.update_one(
                        {'publicId': bench_player['publicId']},
                        {'$set': {'owner': manager['code']}}
                    )


def reset_rosters(db_client: MongoClient=get_db_client()):
    manager_collection = db_client[cfg['MongoAppDbName']]['manager']
    player_collection = db_client[cfg['MongoAppDbName']]['player']
    manager_collection.update_many(
        {},
        {'$set':{
            'roster': {
                'QB': None, 'RB': None, 'WR1': None, 'WR2': None, 'FLEX1': None, 'FLEX2': None,
                'TE': None, 'DST': None, 'HC': None, 'BENCH': [], 'IR': []
            },
            'pos_counts': {
                'QB': 0, 'RB': 0, 'WR': 0, 'TE': 0, 'DST': 0, 'HC': 0
            }
        }}
    )
    player_collection.update_many(
        {},
        {'$set': {'owner': 'fa'}}
    )

def roster_is_full(roster):
    for pos in ['QB','RB','WR1','WR2','TE','FLEX1','FLEX2','DST','HC']:
        if roster[pos] is None:
            return False
    return len(roster['BENCH']) == 7
