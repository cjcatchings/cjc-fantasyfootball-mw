from db.common.db_client import FantasyFootballDBClient
from db.dbcontext import get_db_client

class Roster:

    def __init__(self):
        self.db_client:FantasyFootballDBClient = get_db_client()
        self.players = None

    def get_roster(self, userid):
        raise NotImplementedError

    @staticmethod
    def player_ownership_required(url_func):
        raise NotImplementedError

    def drop_player(self, usercontext, playerid):
        raise NotImplementedError

    def move_player_to_bench(self, usercontext, playerid):
        raise NotImplementedError

    def move_player_to_position(self, usercontext, playerid, position):
        raise NotImplementedError

    def move_player_to_ir(self, usercontext, playerid):
        raise NotImplementedError

    def submit_waiver_claim(self, ff_manager_code, claim_detail):
        raise NotImplementedError
