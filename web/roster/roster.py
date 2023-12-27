from flask import Blueprint, request
from db.mongo.data.roster import MongoRoster
from db.common.data.roster import Roster
from db.dbcontext import get_db_type
from auth import authentication

roster_bp = Blueprint('roster', __name__)


#TODO maybe try to abstract this out
def __get_db_specific_roster_adapter():
    if get_db_type() == "mongo":
        return MongoRoster()
    return None


roster_adapter:Roster = __get_db_specific_roster_adapter()

@roster_bp.route("/fantasyfootball/roster", defaults={'manager_code': None}, methods=['GET'])
@roster_bp.route("/fantasyfootball/roster/<manager_code>", methods=['GET'])
@authentication.validate_token
def get_roster(manager_code, user_context=None):
    try:
        if manager_code is None:
            return roster_adapter.get_roster(user_context['ff_manager_code'])
        return roster_adapter.get_roster(manager_code)
    except ValueError:
        return __error_response("Invalid player ID", 400)

@roster_bp.route("/fantasyfootball/roster/drop/<playerid>", methods=['POST'])
@authentication.validate_token
@authentication.user_context_required
def drop_player(playerid, user_context=None):
    try:
        return roster_adapter.drop_player(user_context['ff_manager_code'], int(playerid))
    except ValueError:
        return __error_response("Invalid player ID", 400)

@roster_bp.route("/fantasyfootball/roster/bench/<playerid>", methods=['POST'])
@authentication.validate_token
@authentication.user_context_required
def move_player_to_bench(playerid, user_context=None):
    try:
        return roster_adapter.move_player_to_bench(user_context['ff_manager_code'], int(playerid))
    except ValueError:
        return __error_response("Invalid player ID", 400)

@roster_bp.route("/fantasyfootball/roster/move/<playerid>/<new_position>", methods=['POST'])
@authentication.validate_token
@authentication.user_context_required
def move_player_to_position(playerid, new_position, user_context=None):
    try:
        return roster_adapter.move_player_to_position(user_context['ff_manager_code'], int(playerid), new_position)
    except ValueError:
        return __error_response("Invalid player ID", 400)

@roster_bp.route("/fantasyfootball/roster/ir/<playerid>", methods=['POST'])
@authentication.validate_token
@authentication.user_context_required
def move_player_to_ir(playerid, user_context=None):
    try:
        return roster_adapter.move_player_to_ir(user_context['ff_manager_code'], int(playerid))
    except ValueError:
        return __error_response("Invalid player ID", 400)

@roster_bp.route("/fantasyfootball/roster/claim", methods=['POST'])
@authentication.validate_token
@authentication.user_context_required
def submit_waiver_claim(user_context=None):
    #TODO maybe cache this on server?
    try:
        claim_detail = request.json
        return roster_adapter.submit_waiver_claim(user_context['ff_manager_code'], claim_detail)
    except ValueError:
        return __error_response("Invalid waiver detail", 400)


#TODO maybe try to abstract this out
def __error_response(message, response_code):
    return {
        "status": "FAILED",
        "message": message
    }, response_code