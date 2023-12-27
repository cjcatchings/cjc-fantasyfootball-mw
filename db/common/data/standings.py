from db.common.db_client import FantasyFootballDBClient
from db.dbcontext import get_db_client


class Standings:

    def __init__(self):
        self.db_client:FantasyFootballDBClient = get_db_client()
        self.players = None

    def get_standings(self):
        return NotImplementedError
