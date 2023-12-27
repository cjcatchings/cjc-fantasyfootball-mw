from db.common.db_client import FantasyFootballDBClient
from db.dbcontext import get_db_client


class Schedule:

    def __init__(self):
        self.db_client:FantasyFootballDBClient = get_db_client()
        self.players = None

    def get_schedule_for_week(self, week):
        return NotImplementedError

    def get_schedule_for_manager(self, manager):
        return NotImplementedError
