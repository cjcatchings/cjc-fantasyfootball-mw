from pymongo import MongoClient
from db.common.db_client import FantasyFootballDBClient


class FantasyFootballMongoClient(MongoClient, FantasyFootballDBClient):

    def __init__(self, config):
        self.__config = config
        self.dbtype = "mongo"
        MongoClient.__init__(self, self.__get_mongo_connection_string())

    def __get_mongo_connection_string(self):
        self.validate_mongo_params()
        username = self.__config["MongoUsername"]
        password = self.__config["MongoPassword"]
        host = self.__config["MongoHost"]
        port = self.__config["MongoPort"]
        mongo_url_string = f"mongodb://{username}:{password}@{host}"
        if self.__config["MongoEnv"] == "local":
            mongo_url_string = f"{mongo_url_string}:{port}"
        direct_connection = "true"
        if 'DirectConnection' in self.__config.keys():
            direct_connection = self.__config['DirectConnection']
        print(direct_connection)
        mongo_url_string = f"{mongo_url_string}/?directConnection={direct_connection}"
        print(mongo_url_string)
        return mongo_url_string

    def validate_mongo_params(self):
        required_mongo_env_vars = {
            "MongoEnv": ["local", "atlas"],
            "MongoHost": "*",
            "MongoPort": "*",
            "MongoUsername": "*",
            "MongoPassword": "*",
            "MongoAuthDbName": "*",
            "MongoAppDbName": "*"
        }
        missing_env_vars = []
        invalid_env_var_values = []
        for env_var in required_mongo_env_vars.keys():
            if env_var not in self.__config.keys():
                missing_env_vars.append(env_var)
            elif type(required_mongo_env_vars[env_var]) == list \
                    and self.__config[env_var] not in required_mongo_env_vars[env_var]:
                invalid_env_var_values.append(f"{env_var}: {self.__config[env_var]}")
        if len(missing_env_vars) > 0:
            raise ValueError(f"Config is missing the following required Mongo env vars: {','.join(missing_env_vars)}")
        if len(invalid_env_var_values) > 0:
            raise ValueError(f"The following Mongo env vars have invalid values: {','.join(invalid_env_var_values)}")
