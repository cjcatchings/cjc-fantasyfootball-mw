from db.dbcontext import get_db_client
from db.mongo.client.mongo_client import FantasyFootballMongoClient
from config.ffconfig import get_env_config
from db.common.data.waiver import WaiverProcessor
from pymongo.write_concern import WriteConcern
from pymongo.read_concern import ReadConcern
from pymongo.read_preferences import ReadPreference
from bson import ObjectId, json_util
from functools import reduce
import json

DATABASE_NAME = "waiver_request"

free_agents_added = []


class MongoWaiverProcessor(WaiverProcessor):

    __LEAGUE_CODE = "NPM"

    def __init__(self):
        self.db_client: FantasyFootballMongoClient = get_db_client()
        self.cfg = get_env_config()
        self.database = self.db_client[self.cfg['MongoAppDbName']]
        self.collection = self.database[DATABASE_NAME]
        self.player_collection = self.database['player']
        self.manager_collection = self.database['manager']
        self.league_collection = self.database['league']
        self.waiver_collection_updates = []
        self.player_collection_updates = []
        self.manager_collection_updates = []

    def process_waivers(self):
        weekly_waiver_summary = []
        waiver_period = self.__get_current_waiver_period()
        managers = list(self.manager_collection.find().sort(['waiver_priority']))
        def __waiver_reducer(waiver_dict, wvr):
            waiver_dict[wvr['requestor']] = wvr
            return waiver_dict
        waivers_to_process = reduce(__waiver_reducer, self.collection.find({'period': waiver_period}), {})
        while len(managers) > 0:
            current_manager = managers[-1]
            if current_manager['code'] not in waivers_to_process.keys():
                managers.pop()
                continue
            if len(waivers_to_process[current_manager['code']]['claim_detail']) > 0:
                waiver = waivers_to_process[current_manager['code']]['claim_detail'].pop()
                waiver_validation = self.__is_waiver_request_valid(waiver, current_manager)
                if type(waiver_validation) is not str:
                    self.__process_waiver_request(waiver, current_manager)
                    waiver['status'] = 'PROCESSED'
                    manager_to_move = managers.pop()
                    managers.insert(0, manager_to_move)
                else:
                    self.__discard_waiver_request(waiver, current_manager, waiver_validation)
                    waiver['status'] = 'NOT_PROCESSED'
                    print(waiver_validation)
                    waiver['not_processed_reason'] = waiver_validation
                weekly_waiver_summary.append(waiver)
            else:
                managers.pop()
        self.__perform_bulk_write()
        return weekly_waiver_summary

    def __is_waiver_request_valid(self, waiver_request, requesting_manager):
        ending_roster_size = len(requesting_manager['roster']) + 1
        request_has_drops = 'drop' in waiver_request.keys()
        if request_has_drops:
            ending_roster_size -= len(waiver_request['drop'])
        if ending_roster_size > 16:
            return "Manager roster would exceed the size limit."
        player_to_add = self.player_collection.find_one({'publicId': waiver_request['add']})
        if player_to_add['owner'] != 'fa':
            return "Player to add is not a free agent."
        if waiver_request['add'] in free_agents_added:
            return "Player was already added to another team."
        if request_has_drops:
            for player_to_drop in waiver_request['drop']:
                player_found_on_roster = False
                for roster_key in requesting_manager['roster']:
                    if roster_key in ['BENCH', 'IR']:
                        player_found = filter(lambda p: p['publicId'] == player_to_drop,
                                              requesting_manager['roster'][roster_key])
                        if len(list(player_found)) > 0:
                            player_found_on_roster = True
                            break
                    else:
                        if requesting_manager['roster'][roster_key]['publicId'] == player_to_drop:
                            player_found_on_roster = True
                            break
                if not player_found_on_roster:
                    return "Player to drop not currently on team's roster or has already been dropped."
        return True

    def __discard_waiver_request(self, waiver_request, requesting_manager, reason):
        waiver_req_update = {'filter': {
            'requestor': requesting_manager['code'],
            'period': self.__get_current_waiver_period()
        }, 'update': {
            '$set': {
                'claim_detail.$[element].status': 'NOT_PROCESSED',
                'claim_detail.$[element].not_processed_reason': reason
            }
        }, 'arrayFilters': [{
            'element.mgr_priority': {'$eq': waiver_request['mgr_priority']}
        }]}
        self.waiver_collection_updates.append(waiver_req_update)
        return {'status': 'SUCCESS'}

    def __process_waiver_request(self, waiver_request, requesting_manager):
        #Waiver request table - read from and mark as processed
        waiver_req_update = {'filter': {
            'requestor': requesting_manager['code'],
            'period': self.__get_current_waiver_period()
        }, 'update': {
            '$set': {'claim_detail.$[element].status': 'PROCESSED'}
        }, 'arrayFilters': [{
            'element.mgr_priority': {'$eq': waiver_request['mgr_priority']}
        }]}
        self.waiver_collection_updates.append(waiver_req_update)
        #Player table - set player owner to new manager
        player_req_update = {'filter': {
            'publicId': waiver_request['add']
        }, 'update': {
            '$set': {'owner': requesting_manager['code']}
        }}
        self.player_collection_updates.append(player_req_update)
        if 'drop' in waiver_request.keys():
            for dropped_player in waiver_request['drop']:
                player_req_update = {
                    'filter': {'publicId': dropped_player},
                    'update': {'$set': {'owner': 'fa'}}
                }
                self.player_collection_updates.append(player_req_update)
        #Roster table - update roster (incl drops)
        player_to_add = self.player_collection.find_one({'publicId': waiver_request['add']})
        player_to_add['owner'] = requesting_manager['code']
        roster_req_update = {'filter': {
            'code': requesting_manager['code']
        }, 'update': {
            '$push': {
                'roster.BENCH': player_to_add
            }
        }}
        self.manager_collection_updates.append(roster_req_update)
        if 'drop' in waiver_request.keys():
            for dropped_player in waiver_request['drop']:
                roster_req_update = {
                    'filter': {'code': requesting_manager['code']}
                }
                for roster_key in requesting_manager['roster'].keys():
                    if roster_key == 'BENCH':
                        for bench_player in requesting_manager['roster']['BENCH']:
                            if bench_player['publicId'] == dropped_player:
                                roster_req_update['update'] = {
                                    '$pull': {'roster.BENCH': {'publicId': dropped_player}}
                                }
                                break
                    elif roster_key == 'IR':
                        for bench_player in requesting_manager['roster']['IR']:
                            if bench_player['publicId'] == dropped_player:
                                roster_req_update['update'] = {
                                    '$pull': {'roster.IR': {'publicId': dropped_player}}
                                }
                                break
                    else:
                        if requesting_manager['roster'][roster_key]['publicId'] == dropped_player:
                            roster_req_update['update'] = {
                                '$set': {f'roster.{roster_key}': None }
                            }
                self.manager_collection_updates.append(roster_req_update)
        return {'STATUS': 'success'}

    def __perform_bulk_write(self):
        def __callback(session):
            for waiver_update in self.waiver_collection_updates:
                self.collection.update_one(
                    waiver_update['filter'],
                    waiver_update['update'],
                    array_filters=waiver_update['arrayFilters'],
                    session=session
                )
            for player_update in self.player_collection_updates:
                self.player_collection.update_one(
                    player_update['filter'],
                    player_update['update'],
                    session=session
                )
            for manager_update in self.manager_collection_updates:
                self.manager_collection.update_one(
                    manager_update['filter'],
                    manager_update['update'],
                    session=session
                )
        with self.db_client.start_session() as session:
            session.with_transaction(
                callback=__callback,
                read_concern=ReadConcern("local"),
                write_concern=WriteConcern("majority"),
                read_preference=ReadPreference.PRIMARY
            )
        return {"status": "SUCCESS"}

    def __get_current_waiver_period(self):
        league_code = MongoWaiverProcessor.__LEAGUE_CODE
        league_info =  self.league_collection.find_one({"code": league_code})
        if league_info is None:
            return {
                "status": "FAILED",
                "message": f"League '{league_code}' not found"
            }
        return league_info['waiver_period']
