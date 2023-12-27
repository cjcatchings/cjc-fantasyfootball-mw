from db.common.data.standings import Standings
from db.mongo.client.mongo_client import FantasyFootballMongoClient
from db.dbcontext import get_db_client
from config.ffconfig import get_env_config
from bson import json_util
from functools import reduce
import json

DATABASE_NAME = "standings"

class MongoStandings(Standings):

    def __init__(self):
        self.db_client:FantasyFootballMongoClient = get_db_client()
        self.cfg = get_env_config()
        self.database = self.db_client[self.cfg['MongoAppDbName']]
        self.collection = self.database[DATABASE_NAME]
        self.manager_collection = self.database['manager']
        self.players = None

    def get_standings(self):
        def mgr_names(mg_dict, mgr):
            mg_dict[mgr['code']] = mgr['team_name']
            return mg_dict
        manager_names = reduce(mgr_names, self.manager_collection.find(), {})
        def standings_with_name(s_list, team):
            team['teamname'] = manager_names[team['teamcode']]
            s_list.append(team)
            return s_list
        standings_result = reduce(standings_with_name, self.collection.find(), [])
        return json.loads(json_util.dumps(standings_result))
