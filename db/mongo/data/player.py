from db.dbcontext import get_db_client
from db.mongo.client.mongo_client import FantasyFootballMongoClient
from config.ffconfig import get_env_config
from db.common.data.player import Player
from bson import json_util
import json

DATABASE_NAME = 'player'


class MongoPlayer(Player):

    def __init__(self):
        self.db_client: FantasyFootballMongoClient = get_db_client()
        self.cfg = get_env_config()
        self.database = self.db_client[self.cfg['MongoAppDbName']]
        self.collection = self.database[DATABASE_NAME]

    @staticmethod
    def __transform_player(player):
        player['priPosition'] = player['position'][0]
        return player

    def get_all_players(self):
        return json.loads(json_util.dumps(list(map(MongoPlayer.__transform_player, self.collection.find()))))

    def get_available_players(self):
        return json.loads(json_util.dumps(list(map(MongoPlayer.__transform_player,self.collection.find({
            "acqStatus": {"$eq": "a"}
        })))))

    def get_player_detail(self, player_id):
        return json.loads(json_util.dumps(self.collection.find_one({
            "publicId": {"$eq": int(player_id)}
        })))
