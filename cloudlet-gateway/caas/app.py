# -*- coding: utf-8 -*-
"""The app module, containing the app factory function."""
import os

import logging
import pdb

import sys
from flask import Flask, render_template, request, redirect

from caas import commands, public, provider, auth, customer
from caas.assets import assets
from caas.extensions import bcrypt, cache, csrf_protect, db, debug_toolbar, login_manager, migrate, jwt
from caas.provider.models import User, Cluster
from caas.provider.models import App as AppModel
from caas.settings import ProdConfig



def create_directories(app):
    uploaded_config_file_dir = app.config['UPLOADED_CONFIG_FILE_DIR']
    if not os.path.exists(uploaded_config_file_dir):
        os.makedirs(uploaded_config_file_dir)


def register_loggers(app):
    # app.logger.addHandler(logging.StreamHandler(sys.stdout))
    app.logger.setLevel(logging.DEBUG)


def populate_db():
    default_user = os.environ.get("DEFAULT_PROVIDER")
    default_user_pw = os.environ.get("DEFAULT_PROVIDER_PW")
    if not User.query.filter_by(username=default_user).first():
        User.create(username=default_user, email="{}@{}".format(default_user, default_user),
                    password=default_user_pw, active=True)
    current_user = User.query.filter_by(username=default_user).first()

    default_cluster = 'test-swarm'
    default_cluster_sz = 2
    if not Cluster.query.filter_by(name=default_cluster).first():
        Cluster.create(name=default_cluster, size=default_cluster_sz, user_id=current_user.id)
        current_cluster = Cluster.query.filter_by(name=default_cluster).first()
        db.session.add(current_cluster)
        db.session.commit()

        # default_app = 'lego'
    # if not AppModel.query.filter_by(name=default_app).first():
    #     AppModel.create(name=default_app, cluster_id=current_cluster.id, user_id=current_user.id)
    # current_app = AppModel.query.filter_by(name=default_app).first()
    # current_cluster.app.append(current_app)



def create_app(config_object=ProdConfig):
    """An application factory, as explained here: http://flask.pocoo.org/docs/patterns/appfactories/.

    :param config_object: The configuration object to use.
    """
    app = Flask(__name__.split('.')[0])
    app.config.from_object(config_object)
    register_extensions(app)
    register_blueprints(app)
    register_errorhandlers(app)
    register_shellcontext(app)
    register_commands(app)

    create_directories(app)
    register_loggers(app)
    app.before_first_request(populate_db)
    return app


def register_extensions(app):
    """Register Flask extensions."""
    assets.init_app(app)
    bcrypt.init_app(app)
    cache.init_app(app)
    db.init_app(app)
    csrf_protect.init_app(app)
    login_manager.init_app(app)
    debug_toolbar.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    return None


def register_blueprints(app):
    """Register Flask blueprints."""
    app.register_blueprint(public.views.blueprint)
    app.register_blueprint(provider.views.blueprint)
    app.register_blueprint(provider.api.blueprint)
    app.register_blueprint(auth.views.blueprint)
    app.register_blueprint(customer.views.blueprint)
    return None


def register_errorhandlers(app):
    """Register error handlers."""

    def render_error(error):
        """Render error template."""
        # If a HTTPException, pull the `code` attribute; default to 500
        error_code = getattr(error, 'code', 500)
        return render_template('{0}.html'.format(error_code)), error_code

    for errcode in [401, 404, 500]:
        app.errorhandler(errcode)(render_error)
    return None


def register_shellcontext(app):
    """Register shell context objects."""

    def shell_context():
        """Shell context objects."""
        return {
            'db': db,
            'User': provider.models.User,
            'App': provider.models.App,
            'Customer': customer.models.Customer,
            'Cluster': provider.models.Cluster,
            'Instance': customer.models.Instance
        }

    app.shell_context_processor(shell_context)


def register_commands(app):
    """Register Click commands."""
    app.cli.add_command(commands.test)
    app.cli.add_command(commands.lint)
    app.cli.add_command(commands.clean)
    app.cli.add_command(commands.urls)
