from db.common.data.schedule import Schedule
from db.mongo.client.mongo_client import FantasyFootballMongoClient
from db.dbcontext import get_db_client
from config.ffconfig import get_env_config
from bson import json_util
from functools import reduce
import json

DATABASE_NAME = "schedule"

MANAGER_CODE_MAP = {}

class MongoSchedule(Schedule):

    def __init__(self):
        self.db_client:FantasyFootballMongoClient = get_db_client()
        self.cfg = get_env_config()
        self.database = self.db_client[self.cfg['MongoAppDbName']]
        self.collection = self.database[DATABASE_NAME]
        self.manager_collection = self.database['manager']
        self.players = None

    def get_schedule_for_week(self, week):
        if week not in range(1,17):
            return MongoSchedule.__error_response(f"Invalid week: {week}", 415)
        return json.loads(json_util.dumps(reduce(self.__add_team_name, self.collection.find_one({"week": week})['matchups'], [])))

    def get_schedule_for_manager(self, manager):
        manager_schedule = {}
        manager_schedule_from_db = self.collection.find({},{
            'week': 1,
            'matchups': {
                '$elemMatch': {
                    '$or':[
                        {'home': {'$eq': manager}},
                        {'away': {'$eq': manager}}
                    ]
                }
            }
        })
        for week in manager_schedule_from_db:
            pop_matchup = week['matchups'][0]
            is_home = pop_matchup['home'] == manager
            if is_home:
                opponent = pop_matchup['away']
            else:
                opponent = pop_matchup['home']
            manager_schedule[int(week['week'])] = {
                'isHome': is_home,
                'opponent': opponent,
                'opponentName': self.__get_team_code_map()[opponent]
            }
        return json.loads(json_util.dumps(manager_schedule))

    def __add_team_name(self, schedule_list, matchup):
        matchup['home'] = {'teamcode': matchup['home']}
        matchup['away'] = {'teamcode': matchup['away']}
        matchup['home']['teamname'] = self.__get_team_code_map()[matchup['home']['teamcode']]
        matchup['away']['teamname'] = self.__get_team_code_map()[matchup['away']['teamcode']]
        schedule_list.append(matchup)
        return schedule_list

    # TODO maybe try to abstract this out
    def __error_response(message, response_code):
        return {
            "status": "FAILED",
            "message": message
        }, response_code

    # TODO maybe load to server-side cache
    def __get_team_code_map(self) -> dict:
        global MANAGER_CODE_MAP
        if not MANAGER_CODE_MAP:
            def map_code_to_team(teammap, team):
                teammap[team['code']] = team['team_name']
                return teammap
            MANAGER_CODE_MAP = reduce(map_code_to_team, self.manager_collection.find(), {})
        return MANAGER_CODE_MAP
