# -*- coding: utf-8 -*-
"""app views."""
import os
from functools import partial

import requests
import ruamel.yaml
from flask import (Blueprint, Response, abort, current_app, flash, redirect,
                   render_template, request, send_from_directory,
                   stream_with_context, url_for)
from flask_login import current_user, login_required

from caas.provider import forms, controller
from caas.provider.api import rm_config_files
from caas.provider.models import App as AppModel
from caas.provider.models import Cluster
from caas import utils

blueprint = Blueprint('provider', __name__, url_prefix='/providers', static_folder='../static')


@blueprint.route('/members')
@login_required
def members():
    """show current apps"""
    return render_template('providers/members.html')


@blueprint.route('/', methods=["GET", "POST"])
@blueprint.route('/apps', methods=["GET", "POST"])
@login_required
def apps():
    """show current apps"""
    # get clusters for current user
    clusters = Cluster.query.filter_by(user_id=current_user.id).all()
    cluster_choices = [(cluster.name, cluster.name) for cluster in clusters]
    appform = forms.NewAppForm(cluster_choices)
    clusterform = forms.NewClusterForm()
    form_handlers = {
        "Create Cluster": partial(controller.handle_clusterform, clusterform),
        "Create App": partial(controller.handle_clusterform, appform),
    }
    if request.method == 'POST':
        success, current_form = form_handlers[request.form["form_name"]]()
        if not success:
            utils.flash_errors(current_form)
    display_info = {}
    for app in current_user.apps:
        display_info[app.name] = app.config_file_name[AppModel.APP_TYPE(app.type)]
    cluster_monitor_urls = {}
    # for cluster in clusters:
    #     cluster_monitor_urls[cluster.name] = '{}{}:8080'.format(current_app.config['LELPROXY'],
    #                                                             cluster.leader_public_ip)
    return render_template('providers/services.html',
                           apps=display_info, clusters=clusters, appform=appform,
                           clusterform=clusterform, cluster_monitor_urls=cluster_monitor_urls)


@blueprint.route('/delete/<string:appname>', methods=["GET"])
def delete_apps(appname):
    new_apps = AppModel.query.filter_by(name=appname, user_id=current_user.id).all()
    if new_apps:
        for new_app in new_apps:
            current_app.logger.debug("deleting app {}".format(new_app))
            rm_config_files(new_app)
            new_app.delete()
        flash('Deleted application {}'.format(appname), 'success')
    redirect_url = request.args.get('next') or url_for('provider.apps')
    return redirect(redirect_url)


def read_config_data(app, app_type):
    with open(os.path.join(current_app.config['UPLOADED_CONFIG_FILE_DIR'],
                           app.config_file_name[app_type]), 'r') as f:
        config_data = ruamel.yaml.load(f.read(), ruamel.yaml.RoundTripLoader)
    return config_data


@blueprint.route('/config_files/<string:appname>', methods=["GET"])
@login_required
def config_files(appname):
    app = AppModel.query.filter_by(name=appname).first()
    if not app:
        abort(404, "{} doesn't exist".format(appname))
    app_type = AppModel.APP_TYPE(app.type)
    config_data = {}
    if app_type != AppModel.APP_TYPE.Mixed:
        part_config_data = read_config_data(app, app_type)
        config_data[app_type.value] = part_config_data
    else:  # app_type == AppModel.APP_TYPE.Mixed:
        vm_config_data = read_config_data(app, AppModel.APP_TYPE.VMs)
        config_data[AppModel.APP_TYPE.VMs.value] = vm_config_data
        ct_config_data = read_config_data(app, AppModel.APP_TYPE.Containers)
        config_data[AppModel.APP_TYPE.Containers.value] = ct_config_data
    return Response(ruamel.yaml.dump(config_data, Dumper=ruamel.yaml.RoundTripDumper), mimetype='text/plain')
