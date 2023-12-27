from flask import Blueprint
from db.mongo.data.schedule import MongoSchedule
from db.common.data.schedule import Schedule
from db.dbcontext import get_db_type
from auth import authentication
import re

schedule_bp = Blueprint('schedule', __name__)

#TODO maybe try to abstract this out
def __get_db_specific_schedule_adapter():
    if get_db_type() == "mongo":
        return MongoSchedule()
    return None


wk_expr = re.compile(r"^\d{1,2}$")

schedule_adapter:Schedule = __get_db_specific_schedule_adapter()

@schedule_bp.route("/fantasyfootball/schedule/<week_or_team>", methods=['GET'])
@schedule_bp.route("/fantasyfootball/schedule", defaults={'week_or_team': None}, methods=['GET'])
@authentication.validate_token
def get_schedule(week_or_team, user_context=None):
    if week_or_team is None:
        return schedule_adapter.get_schedule_for_manager(user_context['ff_manager_code'])
    if wk_expr.match(week_or_team) is not None:
        try:
            return schedule_adapter.get_schedule_for_week(int(week_or_team))
        except ValueError:
            return {"status": "FAILED", "message": f"Invalid week value {week_or_team}"}, 415
    return schedule_adapter.get_schedule_for_manager(week_or_team)
