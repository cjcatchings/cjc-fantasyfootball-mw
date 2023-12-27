from flask import Flask, request

from auth import authentication
from web.player.player import player_bp
from web.roster.roster import roster_bp
from web.standings.standings import standings_bp
from web.schedule.schedule import schedule_bp
from web.trade.trade import trade_bp

app = Flask(__name__)
#TODO move addition of blueprints to method
app.register_blueprint(player_bp)
app.register_blueprint(roster_bp)
app.register_blueprint(standings_bp)
app.register_blueprint(schedule_bp)
app.register_blueprint(trade_bp)

@app.route('/auth/authn', methods=['POST'])
def authenticate_user():
    content_type = request.headers.get('Content-Type')
    if content_type == 'application/json':
        req_body = request.json
        username = req_body.get('username', '')
        password = req_body.get('password', '')
        return authentication.authenticate_user(username, password)
    else:
        return __error_response("Content-Type not supported!", 415)


@app.route("/auth/validate_token", methods=['POST'])
@authentication.validate_token
@authentication.user_context_required
def do_validate_auth_token(user_context=None):
    resp = {
        "authenticated": True,
        "status": "Authenticated",
    }
    # TODO revisit this to optimize
    if bool(request.args.get("withPayload", "False")):
        resp['name'] = user_context['name']
    return resp


def __error_response(message, response_code):
    return {
        "status": "FAILED",
        "message": message
    }, response_code


if __name__ == '__main__':
    app.run(host=("0.0.0.0"), port=5000, debug=True)
