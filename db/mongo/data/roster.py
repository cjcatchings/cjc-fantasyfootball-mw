from db.dbcontext import get_db_client
from db.mongo.client.mongo_client import FantasyFootballMongoClient
from config.ffconfig import get_env_config
from db.common.data.roster import Roster
from pymongo.write_concern import WriteConcern
from pymongo.read_concern import ReadConcern
from pymongo.read_preferences import ReadPreference
from bson import json_util, ObjectId
import json

DATABASE_NAME = "manager"


class MongoRoster(Roster):
    __STARTING_POSITIONS = ['QB', 'RB', 'WR1', 'WR2', 'TE', 'FLEX1', 'FLEX2', 'DST', 'HC']

    def __init__(self):
        self.db_client: FantasyFootballMongoClient = get_db_client()
        self.cfg = get_env_config()
        self.database = self.db_client[self.cfg['MongoAppDbName']]
        self.collection = self.database[DATABASE_NAME]
        self.player_collection = self.database['player']
        self.waiver_req_collection = self.database['waiver_request']
        self.league_collection = self.database['league']

    #TODO move to utility method?
    @staticmethod
    def find_player_in_roster(playerid, roster):
        for roster_key in roster.keys():
            if roster_key in MongoRoster.__STARTING_POSITIONS:
                if roster[roster_key] is not None and roster[roster_key]['publicId'] == playerid:
                    return {roster_key: roster[roster_key]}
            else:
                for player in roster[roster_key]:
                    if player['publicId'] == playerid:
                        return {roster_key: player}
        return None

    def invalid_player_in_ir(url_func):
        def url_func_wrapper(self, ff_manager_code, playerid, new_position=None):
            user_roster = self.roster_collection.find_one({
                'code': {'$eq': ff_manager_code}
            })
            if user_roster is None:
                return MongoRoster.__error_response(f"Team '{ff_manager_code} not found.", 415)
            ir_players = user_roster['roster']['IR']
            for p in ir_players:
                if p['injStatus'] not in ['o', 'ir']:
                    return MongoRoster.__error_response(f"You have invalid players in IR slots.", 415)
            url_func_wrapper.__name__ = url_func.__name__
            if new_position is None:
                return url_func(self, ff_manager_code, playerid)
            return url_func(self, ff_manager_code, playerid, new_position)

    def player_ownership_required(url_func):
        def url_func_wrapper(self, ff_manager_code, playerid, new_position=None):
            roster_collection = self.collection
            if roster_collection is None:
                return MongoRoster.__error_response("Server-side error #1001.", 500)
            if ff_manager_code is None:
                return MongoRoster.__error_response("A manager code context is needed to perform transactions.", 415)
            #TODO validate that player_id is int
            user_roster = roster_collection.find_one({
                'code': {'$eq': ff_manager_code}
            })
            if user_roster is None:
                return MongoRoster.__error_response(f"Team '{ff_manager_code} not found.", 415)
            user_roster_players = user_roster['roster']
            full_player_info = MongoRoster.find_player_in_roster(playerid, user_roster_players)
            if full_player_info is None:
                return MongoRoster.__error_response("Player must be on owner roster to perform transactions on him.", 401)
            url_func_wrapper.__name__ = url_func.__name__
            if new_position is None:
                return url_func(self, ff_manager_code, full_player_info)
            return url_func(self, ff_manager_code, full_player_info, new_position)

        url_func_wrapper.__name__ = url_func.__name__
        return url_func_wrapper

    def get_roster(self, ff_manager_code):
        print(ff_manager_code)
        roster = json.loads(json_util.dumps(self.collection.find_one({
            'code': {'$eq': ff_manager_code}
        })))
        if roster is None:
            return {
                "status": "FAILED",
                "message": f"Roster for '{ff_manager_code}' not found"
            }
        return self.__transform_roster(roster['roster'])

    @staticmethod
    def __error_response(message, http_response):
        return {
            "status": "FAILED",
            "message": message
        }, http_response

    @player_ownership_required
    def drop_player(self, ff_manager_code, player):
        update_cmd = {}
        player_pos = player.keys()[0]
        if player_pos in ['BENCH', 'IR']:
            update_cmd = {'$pull': {f'roster.{player_pos}': {'publicId': player[player_pos]['publicId']}}}
        else:
            update_cmd = {'$set': {f'roster.{player_pos}': None}}

        def __callback(session):
            self.collection.update_one(
                {'code': {'$eq': ff_manager_code}},
                update_cmd,
                session=session
            )
            self.player_collection.update_one(
                {'publicId': {'$eq': player[player_pos]['publicId']}},
                {'$set': {'owner': 'fa'}},
                session=session
            )
        with self.db_client.start_session() as session:
            session.with_transaction(
                callback=__callback,
                read_concern=ReadConcern("local"),
                write_concern=WriteConcern("majority"),
                read_preference=ReadPreference.PRIMARY
            )
        return json.loads(json_util.dumps(self.__transform_roster(self.collection.find_one({'code': ff_manager_code})['roster'])))

    @player_ownership_required
    def move_player_to_bench(self, ff_manager_code, player):
        current_slot = list(player.keys())[0]
        if current_slot in MongoRoster.__STARTING_POSITIONS:
            self.collection.update_one(
                {'code': {'$eq': ff_manager_code}},
                {
                    '$set': {f'roster.{current_slot}': None},
                    '$push': {'roster.BENCH': player[current_slot]}
                }
            )
        elif current_slot == 'IR':
            self.collection.update_one(
                {'code': {'$eq': ff_manager_code}},
                {
                    '$pull': {'roster.IR': {'publicId': player[current_slot]['publicId']}},
                    '$push': {'roster.BENCH': player[current_slot]}
                }
            )
        return json.loads(json_util.dumps(self.__transform_roster(self.collection.find_one({'code': ff_manager_code})['roster'])))

    @player_ownership_required
    def move_player_to_position(self, ff_manager_code, player, new_position):
        player_id_to_pull = None
        player_to_push = None
        array_filters = None
        if new_position not in ['QB', 'RB', 'WR1', 'WR2', 'TE', 'FLEX1', 'FLEX2', 'DST', 'HC']:
            return MongoRoster.__error_response(f"Position {new_position} invalid.", 415)
        current_position = list(player.keys())[0]
        if not MongoRoster.__is_player_allowed_in_position(player, new_position):
            return MongoRoster.__error_response(f"Player with positions {player[current_position]['position']} is not allowed in {new_position} slot.", 415)
        if current_position == new_position:
            return {"status": "NO_ACTION"}
        update = {'$set': {f'roster.{new_position}': player[current_position]}}
        if current_position in ['BENCH', 'IR']:
            player_id_to_pull = player[current_position]['publicId']
            #update['$pull'] = {f'roster.{current_position}': {'publicId': player[current_position]['publicId']}}
        else:
            update['$set'][f'roster.{current_position}'] = None
        #If a player exists in the new position, swap player slots if player is allowed in that position.  Otherwise move that player to BENCH
        current_roster = self.collection.find_one({'code': ff_manager_code})['roster']
        if current_roster[new_position] is not None:
            if(current_position not in ['BENCH', 'IR']
                    and MongoRoster.__is_player_allowed_in_position({new_position: current_roster[new_position]}, current_position)):
                update['$set'][f'roster.{current_position}'] = current_roster[new_position]
            else:
                player_to_push = current_roster[new_position]
                #update['$push'] = {f'roster.BENCH': current_roster[new_position]}
        #If a push and a pull from the BENCH array needs to happen, just replace one with the other
        if player_id_to_pull is not None and player_to_push is not None:
            update['$set'][f'roster.{current_position}.$[elem]'] = player_to_push
            array_filters = [{'elem.publicId':{'$eq': player_id_to_pull}}]
        elif player_id_to_pull is not None:
            update['$pull'] = {f'roster.{current_position}': {'publicId': player[current_position]['publicId']}}
        elif player_to_push is not None:
            update['$push'] = {f'roster.BENCH': current_roster[new_position]}
        self.collection.update_one(
            {'code': ff_manager_code},
            update,
            array_filters=array_filters
        )
        return json.loads(json_util.dumps(self.__transform_roster(self.collection.find_one({'code': ff_manager_code})['roster'])))

    @player_ownership_required
    def move_player_to_ir(self, ff_manager_code, player):
        if not MongoRoster.__is_player_allowed_in_position(player, 'IR'):
            return MongoRoster.__error_response("Player does not qualify for IR.", 415)
        current_position = list(player.keys())[0]
        if current_position == 'IR':
            return {'status': 'NO_ACTION'}
        update = {'$push': {f'roster.IR': player[current_position]}}
        if current_position == 'BENCH':
            update['$pull'] = {f'roster.BENCH': {'publicId': player[current_position]}}
        else:
            update['$set'] = {f'roster.{current_position}': None}
        self.collection.update_one(
            {'code': ff_manager_code},
            update
        )
        return json.loads(json_util.dumps(self.__transform_roster(self.collection.find_one({'code': ff_manager_code})['roster'])))

    def submit_waiver_claim(self, ff_manager_code, claims_detail):
        roster = self.get_roster(ff_manager_code)
        claim_period = self.league_collection.find_one({'code': self.cfg['leagueId']})['waiver_period']
        for claim in claims_detail:
            validation_response = self.__validate_waiver_claim_data(claim, roster)
            if type(validation_response) == str:
                return MongoRoster.__error_response(validation_response, 415)
            claim['status'] = 'PENDING'

        existing_waiver_claim = self.waiver_req_collection.find_one({
            'period': claim_period,
            'requestor': ff_manager_code
        })
        if existing_waiver_claim is None:
            self.waiver_req_collection.insert_one({
                'period': claim_period,
                'requestor': ff_manager_code,
                'claim_detail': claims_detail
            })
        else:
            self.waiver_req_collection.update_one(
                {'period': claim_period, 'requestor': ff_manager_code},
                {'claim_detail': claims_detail}
            )

        return {'status': 'SUBMITTED'}

    def delete_waiver_claim(self, claim_detail):
        self.waiver_req_collection.delete_one({'_id': ObjectId(claim_detail['_id'])})
        return {'status': 'SUCCESS'}

    def __validate_waiver_claim_data(self, claim_detail, roster):
        if type(claim_detail) != dict:
            return "Invalid claim detail."
        if 'add' not in claim_detail.keys():
            return "Waiver claim contains no players to add."
        for players_to_add in self.player_collection.find({'publicId': claim_detail['add']}):
            if players_to_add['owner'] != 'fa':
                return "Cannot add players that are not free agents."
        resulting_roster_size = MongoRoster.__get_roster_size(roster) + 1
        print(claim_detail.keys())
        if 'drop' in claim_detail.keys():
            for player_to_drop in claim_detail['drop']:
                if MongoRoster.find_player_in_roster(player_to_drop, roster) is None:
                    return "Player must be on your roster in order to drop him."
            resulting_roster_size -= len(claim_detail['drop'])
        if resulting_roster_size > 16:
            return "Select player(s) to drop before submitting waiver claim."
        return True

    @staticmethod
    def __get_roster_size(roster):
        size = 0
        for key in roster.keys():
            if type(roster[key]) == list:
                size += len(roster[key])
            elif roster[key] is not None:
                size += 1
        return size

    def __transform_roster(self, roster):
        for roster_role in roster.keys():
            if roster_role in ['BENCH', 'IR']:
                for ix, non_starter in enumerate(roster[roster_role]):
                    roster[roster_role][ix]['priPosition'] = non_starter['position'][0]
            elif roster[roster_role] is not None:
                roster[roster_role]['priPosition'] = roster[roster_role]['position'][0]
        return roster

    #TODO maybe move to a dict?
    @staticmethod
    def __is_player_allowed_in_position(player, position):
        if position == 'BENCH':
            return True
        current_position = list(player.keys())[0]
        if position == 'IR':
            return player[current_position]['injStatus'] in ['o', 'ir']
        for pp in player[current_position]['position']:
            if pp == 'WR' and position in ['WR1', 'WR2', 'FLEX1', 'FLEX2']:
                return True
            if pp == 'RB' and position in ['RB', 'FLEX1', 'FLEX2']:
                return True
            if pp == 'TE' and position in ['TE', 'FLEX1', 'FLEX2']:
                return True
            if pp == 'QB' and position == 'QB':
                return True
            if pp == 'DST' and position == 'DST':
                return True
            if pp == 'HC' and position == 'HC':
                return True
        return False
