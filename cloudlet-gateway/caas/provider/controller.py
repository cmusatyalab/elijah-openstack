# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

from flask import (flash, redirect, render_template, request,
                   send_from_directory, current_app, stream_with_context, url_for)
from flask_login import current_user
from logzero import logger

from caas import utils
from caas.cluster import base, clusterControllerManager
from caas.provider.api import create_application, rm_config_files
from caas.provider.models import Cluster

cluster_type = 'libvirt'
cluster_type_args = ["qemu:///system"]
cluster_type_kwargs = {}
default_image_format = 'qcow2'
default_image_path = '/home/junjuew/passthrough-test/ubuntu-16.04-nvidia-docker-openrtist-tensorflow-benchmark.qcow2'


@utils.validate_form
def handle_appform(appform):
    uploaded_file = appform.config_file.data
    app_name = appform.appname.data
    user_id = current_user.id
    cluster = Cluster.query.filter_by(name=appform.clustername.data, user_id=current_user.id).first()
    create_application(app_name, user_id, uploaded_file, cluster)
    flash('Created a new app', 'success')
    redirect_url = request.args.get('next') or url_for('provider.apps')
    return redirect(redirect_url)


def _cluster_exists(clustername):
    cluster = Cluster.query.filter_by(name=clustername, user_id=current_user.id).first()
    return bool(cluster)


def _create_config(clusterform):
    iface = None
    if clusterform.network.data == 'Bridge':
        iface = base.BridgeNetworkInterface(clusterform.network_bridge_name.data)
    image_format = default_image_format
    image_path = default_image_path
    if clusterform.clustertype.data == 'Custom':
        image_format = clusterform.cluster_custom_vm_image_format.data
        image_path = clusterform.cluster_custom_vm_image_path.data
    vm_res_config = base.ResourceConfig(name=clusterform.clustername.data,
                                        cpu=clusterform.vCPUs.data,
                                        memory=clusterform.vMem.data,
                                        image_format=image_format,
                                        image_path=image_path,
                                        network_interfaces=[iface])
    current_app.logger.debug("cluster configuration: {}".format(vm_res_config))
    return vm_res_config


def _create_cluster_by_config(vm_res_config):
    controller = clusterControllerManager.get_controller(cluster_type, *cluster_type_args, **cluster_type_kwargs)
    controller.create(vm_res_config)
    # TODO(junjuew): how to add machine to the cluster?
    new_cluster = Cluster(name=vm_res_config.name, size=1, user_id=current_user.id)
    new_cluster.save()


def _create_cluster(clusterform):
    res_config = _create_config(clusterform)
    _create_cluster_by_config(res_config)


@utils.validate_form
def handle_clusterform(clusterform):
    if _cluster_exists(clusterform.clustername.data):
        flash('Cluster named {} already exists.'.format(clusterform.clustername), 'error')
    else:
        try:
            _create_cluster(clusterform)
            flash('Created a new cluster', 'success')
        except Exception as e:
            flash('Failed to create the specified cluster using libvirt: {}'.format(e), 'error')
    redirect_url = request.args.get('next') or url_for('provider.apps')
    return redirect(redirect_url)
