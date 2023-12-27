from flask import Blueprint, request
from db.mongo.data.trade import MongoTrade
from db.common.data.trade import Trade
from db.dbcontext import get_db_type
from auth import authentication

trade_bp = Blueprint('trade', __name__)

#TODO maybe try to abstract this out
def __get_db_specific_trade_adapter():
    if get_db_type() == "mongo":
        return MongoTrade()
    return None

trade_adapter:Trade = __get_db_specific_trade_adapter()

@trade_bp.route("/fantasyfootball/trade", methods=['POST'])
@authentication.validate_token
def propose_trade(user_context=None):
    trade_detail = request.json
    try:
        return trade_adapter.propose_trade(trade_detail, user_context['ff_manager_code'])
    except ValueError:
        return __error_response("Invalid trade data", 400)

#TODO maybe try to abstract this out
def __error_response(message, response_code):
    return {
        "status": "FAILED",
        "message": message
    }, response_code
