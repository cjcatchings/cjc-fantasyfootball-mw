from db.common.db_client import FantasyFootballDBClient
from db.dbcontext import get_db_client


class Trade:

    def __init__(self):
        self.db_client:FantasyFootballDBClient = get_db_client()
        self.players = None

    def propose_trade(self, trade_detail, ff_manager_code):
        return NotImplementedError

    def get_trade_detail(self, trade_id, ff_manager_code):
        return NotImplementedError

    def get_pending_trades_for_manager(self, ff_manager_code):
        return NotImplementedError

    def accept_trade(self, trade_id):
        return NotImplementedError

    def decline_trade(self, trade_id, reason_detail):
        return NotImplementedError

    def propose_counter_offer(self, trade_id, counter_offer_detail):
        return NotImplementedError

    def process_trade(self, trade_id):
        return NotImplementedError

    def veto_trade(self, trade_id):
        return NotImplementedError
