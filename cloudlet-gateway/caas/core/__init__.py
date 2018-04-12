import logging
import logging.config
import settings
config = settings.Config()
logging.config.dictConfig(config.LOG_CONFIG_DICT)