# -*- coding: utf-8 -*-
"""Create an application instance."""
import os

#from celery import Celery
from flask.helpers import get_debug_flag

from caas.app import create_app
from caas.settings import DevConfig, ProdConfig


def make_celery(app):
    celery = Celery(app.import_name, backend=app.config['CELERY_RESULT_BACKEND'],
                    broker=app.config['CELERY_BROKER_URL'])
    celery.conf.update(app.config)
    TaskBase = celery.Task

    class ContextTask(TaskBase):
        abstract = True

        def __call__(self, *args, **kwargs):
            with app.app_context():
                return TaskBase.__call__(self, *args, **kwargs)

    celery.Task = ContextTask
    return celery


CONFIG = DevConfig if get_debug_flag() else ProdConfig
app = create_app(CONFIG)
# TODO: celery has some problem of circular import
#celery = make_celery(app)

if __name__ == '__main__':
    context = (os.environ.get('CAAS_CERT', None), os.environ.get('CAAS_KEY', None))
    # app.run(host='0.0.0.0',port=9999,
    #         debug = True, ssl_context=context)
    app.run(host='0.0.0.0', port=9127,
            debug=True, ssl_context=context)
