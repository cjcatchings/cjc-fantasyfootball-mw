from flask import Blueprint
from db.mongo.data.standings import MongoStandings
from db.common.data.standings import Standings
from db.dbcontext import get_db_type
from auth import authentication

standings_bp = Blueprint('standings', __name__)

#TODO maybe try to abstract this out
def __get_db_specific_standings_adapter():
    if get_db_type() == "mongo":
        return MongoStandings()
    return None

standings_adapter:Standings = __get_db_specific_standings_adapter()

@standings_bp.route("/fantasyfootball/standings", methods=['GET'])
@authentication.validate_token
def get_roster(user_context=None):
    return standings_adapter.get_standings()
