from db.common.data.trade import Trade
from db.mongo.data.roster import MongoRoster
from db.mongo.client.mongo_client import FantasyFootballMongoClient
from db.dbcontext import get_db_client
from config.ffconfig import get_env_config
from bson import ObjectId, json_util
from pymongo.write_concern import WriteConcern
from pymongo.read_concern import ReadConcern
from pymongo.read_preferences import ReadPreference
import json

DATABASE_NAME = "trade"

class MongoTrade(Trade):

    def __init__(self):
        self.db_client:FantasyFootballMongoClient = get_db_client()
        self.cfg = get_env_config()
        self.database = self.db_client[self.cfg['MongoAppDbName']]
        self.collection = self.database[DATABASE_NAME]
        self.manager_collection = self.database['manager']
        self.player_collection = self.database['player']

    def commissioner_role_required(url_func):
        def url_func_wrapper(self, ff_manager_code, trade_id, automated_job=False):
            if not automated_job:
                manager = self.manager_collection.find_one({'code': ff_manager_code})
                if manager is None:
                    return MongoTrade.__error_response(f"Manager {ff_manager_code} not found", 415)
                if 'role' not in manager.keys() or manager['role'] != 'LEAGUE_COMMISSIONER':
                    return MongoTrade.__error_response("You are not authorized to perform this transaction.", 401)
            return url_func(self, ff_manager_code, trade_id)
        url_func_wrapper.__name__ = url_func.__name__
        return url_func_wrapper

    def propose_trade(self, trade_detail, ff_manager_code, session=None, run_validation=True):
        if run_validation:
            payload_validation_result = self.__validate_payload(trade_detail, ff_manager_code)
            if type(payload_validation_result) is str:
                return {"status": "FAILED", "message": payload_validation_result}, 415
            trade_detail['requestor'] = ff_manager_code
            trade_detail['status'] = "PROPOSED"
            trade_validation_result = self.__validate_trade_request(trade_detail, ff_manager_code, "PROPOSED")
            if type(trade_validation_result) is str:
                return {"status": "FAILED", "message": trade_validation_result}, 415
        insert_trade_result = self.collection.insert_one(trade_detail, session=None)
        #TODO Notify counter-party and commissioner
        return {"status": "SUCCESS", "result": str(insert_trade_result.inserted_id)}

    def accept_trade(self, trade_id):
        trade_from_db = self.__get_trade_from_database(trade_id)
        if trade_from_db is None:
            return {"status": "FAILED", "message": "Trade not found."}
        trade_validation_resp = self.__validate_trade_request(trade_from_db)
        if type(trade_validation_resp) is str:
            return {"status": "FAILED", "message": trade_validation_resp}
        self.collection.update_one(
            {'_id': trade_from_db['_id']},
            {'status': 'ACCEPTED'}
        )
        #TODO notify league
        return {'status': 'SUCCESS'}

    @commissioner_role_required
    def process_trade(self, trade_id):
        #TODO maybe abstract this out?
        trade_from_db = self.__get_trade_from_database(trade_id)
        if trade_from_db is None:
            return {"status": "FAILED", "message": "Trade not found."}
        trade_validation_resp = self.__validate_trade_request(trade_from_db)
        if type(trade_validation_resp) is str:
            return {"status": "FAILED", "message": trade_validation_resp}
        manager_updates = []
        player_updates = []
        mgr_rosters = {}
        for mgr_code in trade_from_db['detail'].keys():
            mgr_rosters[mgr_code] = self.manager_collection.find_one({'code': mgr_code})['roster']
            for playerid in trade_from_db['detail'][mgr_code]:
                player = None
                ix = 0
                while player is None and ix < len(mgr_rosters.keys()):
                    player = MongoRoster.find_player_in_roster(playerid, list(mgr_rosters.keys())[ix])
                    ix += 1
                if player is None:
                    return {"status": "FAILED", "message": f"Player {playerid} is not on roster '{mgr_code}'"}
                manager_update = {'filter': {'code': player['owner']}}
                pos_key = list(player.keys())[0]
                if pos_key in ['BENCH', 'IR']:
                    manager_update['update'] = {
                        {'$pull': {f'roster.{pos_key}':{'publicId': playerid}}}
                    }
                else:
                    manager_update['update'] = {
                        {'$set': {f'roster.{pos_key}': None}}
                    }
                player_updates.append({
                    'filter':{'publicId': playerid},
                    'update': {'$set': {'owner': mgr_code}}
                })
                player_to_add = self.player_collection.find_one({'publicId': playerid})
                player_to_add['owner'] = mgr_code
                manager_update['update']['$push'] = {
                    'roster.BENCH': player_to_add
                }
                manager_updates.append(manager_update)

        def __callback(session):
            self.collection.update_one(
                {'_id': trade_from_db['_id']},
                {'status': 'PROCESSED'},
                session=session
            )
            for player_update in player_updates:
                self.player_collection.update_one(
                    player_update['filter'],
                    player_update['update'],
                    session=session
                )
            for manager_update in manager_updates:
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
        return {'status': 'SUCCESS'}

    def decline_trade(self, trade_id, reason_detail, session=None, run_validation=True):
        if run_validation:
            trade_from_db = self.__get_trade_from_database(trade_id)
            if trade_from_db is None:
                return {"status": "FAILED", "message": "Trade not found."}
        self.collection.update_one(
            {'_id': trade_from_db},
            {'$set': {'status': 'DECLINED'}},
            session=session
        )
        #TODO notify counter party and commissioner
        return {'status': 'SUCCESS'}

    def propose_counter_offer(self, trade_id, ff_manager_code, counter_offer_detail):
        trade_from_db = self.__get_trade_from_database(trade_id)
        if trade_from_db is None:
            return {"status": "FAILED", "message": "Trade not found."}
        trade_validation_resp = self.__validate_trade_request(trade_from_db)
        if type(trade_validation_resp) is str:
            return {"status": "FAILED", "message": trade_validation_resp}
        def __callback(session):
            self.decline_trade(trade_id, None, session, run_validation=False)
            self.propose_trade(counter_offer_detail, ff_manager_code, session=session, run_validation=False)
        with self.db_client.start_session() as session:
            session.with_transaction(
                callback=__callback,
                read_concern=ReadConcern("local"),
                write_concern=WriteConcern("majority"),
                read_preference=ReadPreference.PRIMARY
            )
        return {'status': 'SUCCESS'}

    @commissioner_role_required
    def veto_trade(self, trade_id):
        trade_from_db = self.__get_trade_from_database(trade_id)
        if trade_from_db is None:
            return {"status": "FAILED", "message": "Trade not found."}
        self.collection.update_one(
            {'_id': trade_from_db['_id']},
            {'status': 'VETOED'}
        )
        return {'status': 'SUCCESS'}
    def __get_trade_from_database(self, trade_id):
        return self.collection.find_one({'_id': ObjectId(trade_id)})

    #TODO need to revisit this as well as any other usage of len on roster
    def __validate_trade_request(self, trade_detail, ff_manager_code, txtype):
        roster_details = {}
        for manager_code in trade_detail['detail'].keys():
            manager_detail = self.manager_collection.find_one({'code': manager_code})
            if manager_detail is None or 'roster' not in manager_detail.keys():
                return f"Roster for '{manager_code} not found."
            roster_details[manager_code] = {'roster': manager_detail['roster']}
        for manager_code in trade_detail['detail'].keys():
            for playerid in trade_detail['detail'][manager_code]:
                player_found_on_other_roster = False
                for other_manager in list(filter(lambda m: m != manager_code, trade_detail['detail'].keys())):
                    if MongoRoster.find_player_in_roster(playerid, roster_details[other_manager]['roster']) is not None:
                        player_found_on_other_roster = True
                        break
                if not player_found_on_other_roster:
                    return f"Player {playerid} not found on any roster of trade parties."
            roster_details[manager_code]['size'] = len(roster_details[manager_code]['roster'])
        num_of_new_players_for_requestor = len(trade_detail['detail'][ff_manager_code])
        num_of_new_players_for_recipient = len(trade_detail['detail'][trade_detail['recipient']])
        if roster_details[ff_manager_code]['size'] + num_of_new_players_for_requestor - num_of_new_players_for_recipient > 16:
            return "Requestor roster would be too large from this trade."
        if roster_details[trade_detail['recipient']]['size'] - num_of_new_players_for_requestor + num_of_new_players_for_recipient > 16:
            return "Recipient roster would be too large for this trade."
        return True


    def __validate_payload(self, trade_detail, ff_manager_code):
        if type(trade_detail) is not dict:
            return "Invalid data type for trade request."
        valid_keys = ["recipient", "detail"]
        detail = None
        recipient = None
        for trade_key in trade_detail.keys():
            if trade_key not in valid_keys:
                return "Invalid data found in trade request."
            if trade_key == "detail":
                detail = trade_detail['detail']
            elif trade_key == 'recipient':
                if trade_detail['recipient'] == ff_manager_code:
                    return "Invalid recipient."
                recipient = trade_detail['recipient']
        if detail is None or recipient is None:
            return "Trade detail missing data."
        trade_detail_keys = trade_detail['detail'].keys()
        if recipient not in trade_detail_keys or ff_manager_code not in trade_detail_keys:
            return "Trade detail missing party data."
        for trade_detail_key in trade_detail_keys:
            if False in [type(pid) is int for pid in trade_detail['detail'][trade_detail_key]]:
                return "Invalid player ID in trade request."
        return True

    def __search_for_duplicate_trade(self, trade_detail):
        pass

    def __notify_trade_recipient(self):
        pass

    def __notify_league_of_approved_trade(self):
        pass

    @staticmethod
    def __error_response(message, http_response):
        return {
            "status": "FAILED",
            "message": message
        }, http_response
