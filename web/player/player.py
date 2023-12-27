from flask import Blueprint
from db.mongo.data.player import MongoPlayer
from db.common.data.player import Player
from db.dbcontext import get_db_type
from auth import authentication

player_bp = Blueprint('player', __name__)


#TODO maybe try to abstract this out
def __get_db_specific_player_adapter():
    if get_db_type() == "mongo":
        return MongoPlayer()
    return None


player_adapter:Player = __get_db_specific_player_adapter()


@player_bp.route("/fantasyfootball/players", defaults={'id_or_cmd': 'available'}, methods=['GET'])
@player_bp.route("/fantasyfootball/players/<id_or_cmd>", methods=['GET'])
@authentication.validate_token
@authentication.user_context_required
def get_players(id_or_cmd, user_context=None):
    if id_or_cmd in [None, 'all']:
        return player_adapter.get_all_players()
    if id_or_cmd == 'available':
        return player_adapter.get_available_players()
    try:
        return player_adapter.get_player_detail(id_or_cmd)
    except ValueError:
        return __error_response("Invalid player ID", 400)


#TODO maybe try to abstract this out
def __error_response(message, response_code):
    return {
        "status": "FAILED",
        "message": message
    }, response_code
