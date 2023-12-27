from db.common.db_client import FantasyFootballDBClient
from db.dbcontext import get_db_client

class Player:

    def __init__(self):
        self.db_client:FantasyFootballDBClient = None

    def get_all_players(self):
        raise NotImplementedError

    def get_available_players(self):
        raise NotImplementedError

    def get_player_detail(self, player_id):
        raise NotImplementedError

    def update_injury_status(self, player_map):
        raise NotImplementedError
