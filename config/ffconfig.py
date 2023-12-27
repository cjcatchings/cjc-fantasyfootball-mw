import configparser
from os import environ
from pathlib import Path
import contextvars

__CONFIG_FILE_PATH = "dev/config.ini"
__env = 'DEFAULT'
if 'FF_PYENV' in environ.keys():
    __env = environ['FF_PYENV']
__cfg = None


def init_env_config():
    cfgfile = configparser.ConfigParser()
    cfgfile.optionxform = str
    cfgfile.read(Path(__file__).parent / __CONFIG_FILE_PATH)
    global __cfg
    __cfg = contextvars.ContextVar("cfg")
    config_section = cfgfile["DEFAULT"]
    if __env in cfgfile.sections():
        config_section = cfgfile[__env]
    if 'UseEnvVars' in config_section.keys() and config_section['UseEnvVars'] == "True":
        print("Config file settings will be overridden by env variables")
        print(f"envkeys: {environ.keys()}")
        for cfkey in config_section.keys():
            print(f"config_key: {cfkey}")
            if cfkey in environ.keys():
                config_section[cfkey] = environ[cfkey]
    __cfg.set(config_section)


def get_env_config():
    global __cfg
    if __cfg is None:
        init_env_config()
    return __cfg.get()
