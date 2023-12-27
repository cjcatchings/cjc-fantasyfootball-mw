from datetime import datetime, timedelta
from flask import request
import base64
import hashlib
import jwt
from jwt.exceptions import InvalidSignatureError
from config.ffconfig import get_env_config
from db import dbcontext
from bson import ObjectId

env_config = get_env_config()
mongo_client = dbcontext.get_db_client()
JWT_SECRET = env_config['AuthSecret']
user_cache = {}

def authenticate_user(username, password):
    global mongo_client
    db = mongo_client[env_config['MongoAuthDbName']]
    coll = db[env_config['MongoAuthCollectionName']]
    requesting_user = coll.find_one({'username': username})
    if requesting_user is None:
        return __error_response("Login Failed! IUP", 401)
    salt = base64.b64decode(requesting_user['salt'])
    dbhashkey = base64.b64decode(requesting_user['hashkey'])
    reqhashkey = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt,
        100000,
        dklen=128
    )
    if reqhashkey == dbhashkey:
        raw_token = requesting_user['user_details']
        user_id_str = str(requesting_user['_id'])
        raw_token['userid'] = user_id_str
        now_datetime = datetime.now()
        raw_token['issue_date'] = now_datetime.timestamp()
        raw_token['exp_date'] = (now_datetime + timedelta(hours=1)).timestamp()
        encoded_jwt = jwt.encode(raw_token, JWT_SECRET, algorithm="HS256")
        user_cache[user_id_str] = requesting_user['non_token_detail']["name"]
        return {
            "status": "SUCCESS",
            "authenticated": True,
            "access_token": encoded_jwt,
            "refresh_token": None,
            "username": username,
            "redirect_to": requesting_user['user_details']['landing_page']
        }
    return __error_response("Login Failed! IUP", 401)

def validate_token(url_func):
    def url_func_wrapper(*args, **kwargs):
        if('Authorization' in request.headers.keys()):
            auth_token_split = request.headers['Authorization'].split(" ")
            if(len(auth_token_split) == 2
                and auth_token_split[0] == "Bearer"):
                try:
                    decoded_token = jwt.decode(
                        auth_token_split[1],
                        JWT_SECRET,
                        algorithms=["HS256"]
                    )
                except InvalidSignatureError:
                    return __unauthenticated_response("Invalid access token.", 401)
                #Is this a user token?
                if 'userid' in decoded_token.keys():
                    user_details = {
                        "userid": decoded_token['userid'],
                        "ff_manager_code": decoded_token['ff_manager_code'],
                        "name": get_user_full_name_from_cache(decoded_token['userid'])
                    }
                #Is this a token issued to a service integration?
                elif 'serviceid' in decoded_token.keys():
                    user_details = {
                        "serviceid": decoded_token['serviceid'],
                        "authorized_services": decoded_token['authorized_svcs']
                    }
                token_exp_date = decoded_token['exp_date']
                if(datetime.now().timestamp() <= token_exp_date):
                    kwargs['user_context'] = user_details
                    return url_func(*args, **kwargs)
        return __unauthenticated_response("No valid access token.", 401)
    url_func_wrapper.__name__ = url_func.__name__
    return url_func_wrapper

def user_context_required(url_func):
    def url_func_wrapper(*args, **kwargs):
        if 'user_context' not in kwargs.keys() or kwargs['user_context'] is None:
            return __unauthenticated_response("No user context found.", 401)
        return url_func(*args, **kwargs)
    url_func_wrapper.__name__ = url_func.__name__
    return url_func_wrapper

def get_user_full_name_from_cache(userid):
    if userid not in user_cache.keys():
        user_cache[userid] = mongo_client[env_config['MongoAuthDbName']][env_config['MongoAuthCollectionName']]\
            .find_one({'_id': ObjectId(userid)})['non_token_detail']['name']
    return user_cache[userid]

def __error_response(message, response_code):
    return {
        "status": "FAILED",
        "authenticated": False,
        "message": message
    }, response_code

def __unauthenticated_response(reason, response_code):
    return {
        "status": "Unauthenticated",
        "authenticated": False,
        "reason": reason,
        "name": None
    }, response_code
