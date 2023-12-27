from config.ffconfig import get_env_config
import pymongo
from db.mongo.client.mongo_client import FantasyFootballMongoClient
import contextvars

__config = get_env_config()
__mongo_client = None
__dynamo_client = None

dbtype = None

def get_db_type():
    return dbtype

def init_db_client():
    if "DbType" not in __config.keys():
        raise KeyError("DBTYPE not in config.ini")
    global dbtype
    dbtype = __config["DbType"]
    if dbtype == "mongo":
        global __mongo_client
        __mongo_client = contextvars.ContextVar("db_client")
        print("new client")
        new_client = FantasyFootballMongoClient(__config)
        __mongo_client.set(new_client)
    elif dbtype == "dynamo":
        global __dynamo_client
        __dynamo_client = contextvars.ContextVar("db_client")
    else:
        raise ValueError(f"Invalid DBType: {dbtype}")

def get_db_client():
    if dbtype is None:
        init_db_client()
    if dbtype == "mongo":
        return __mongo_client.get()
    return __dynamo_client.get()
