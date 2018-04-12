"""core configuration"""


class Config(object):
    DOCKER_MACHINE_PATH = "/usr/local/bin/docker-machine"
    SWARM_TOKEN_ATTR = "JoinTokens"
    SWARM_TOKEN_MANAGER_ROLE = "Manager"
    SWARM_TOKEN_WORKER_ROLE = "Worker"
    LOG_CONFIG_DICT = {
        "version": 1,
        'disable_existing_loggers': False,
        "handlers": {
            'console': {
                'class': 'logging.StreamHandler',
                'level': 'DEBUG',
                'formatter': 'myFormatter',
                'stream': 'ext://sys.stdout',
            },
        },
        "loggers": {
            "core": {
                "handlers": ["console"],
                "level": "DEBUG",
            }
        },
        "formatters": {
            "myFormatter": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            }
        }
    }
