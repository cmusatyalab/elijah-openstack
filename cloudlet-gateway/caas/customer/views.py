# -*- coding: utf-8 -*-
"""app views."""
import os
import pdb
import re
from collections import defaultdict
from time import sleep

from flask import Blueprint, render_template, request, flash, url_for, redirect, current_app, abort, json
from heatclient.exc import HTTPConflict, HTTPNotFound, HTTPBadRequest
from subprocess import Popen, PIPE
import redis
from docker.errors import NotFound

from caas.core import openstackutils, dockerutils
from caas.core.dockerutils import get_docker_client, get_services_in_stack, get_stack_published_ports
from caas.core.exc import VMStackCreationError, DockerContainerError, InstanceNotFoundError
from caas.core.machine import Machine
from caas.core.openstackutils import get_stack_ns_entries
from caas.customer.models import Instance, Customer
from caas.extensions import csrf_protect
from caas.provider.models import App as AppModel, Cluster
from caas.utils import get_config_file_path

blueprint = Blueprint('customer', __name__, url_prefix='/customers', static_folder='../static')
csrf_protect.exempt(blueprint)

CLOUDLET_NAMESERVER_IP = 'CLOUDLET_NAMESERVER_IP'
CLOUDLET_NAMESERVER_PORT = 'CLOUDLET_NAMESERVER_PORT'
CLOUDLET_NAMESERVER_PW = 'CLOUDLET_NAMESERVER_PW'
CLOUDLET_INSTANCE_ID = 'CLOUDLET_INSTANCE_ID'


def get_heat_client():
    heat = openstackutils.start_heat_connection(AUTH_URL=os.environ.get("OS_AUTH_URL"),
                                                USERNAME=os.environ.get("OS_USERNAME"),
                                                PASSWORD=os.environ.get("OS_PASSWORD"),
                                                PROJECT_NAME=os.environ.get("OS_PROJECT_NAME"),
                                                TENANT_ID=os.environ.get("OS_TENANT_ID"),
                                                TENANT_NAME=os.environ.get("OS_TENANT_NAME"),
                                                )

    return heat


def create_vm_stack(customer, app, stack_name, config_file_path):
    heat = get_heat_client()
    stack_id = None
    try:
        params = {}
        if app.type == AppModel.APP_TYPE.Mixed.value:
            params[CLOUDLET_INSTANCE_ID] = stack_name
            cluster = Cluster.query.filter_by(id=app.cluster_id).first()
            params[CLOUDLET_NAMESERVER_IP] = cluster.leader_ip
            params[CLOUDLET_NAMESERVER_PORT] = str(cluster.nameserver_port)
            params[CLOUDLET_NAMESERVER_PW] = os.environ.get('REDIS_NAMESERVER_PW', None)
        stack_id = openstackutils.create_stack(heat, template_file=config_file_path,
                                               stack_name=stack_name, instance_name=app.name, parameters=params)
        current_app.logger.debug('succesfully created vm stack: {}'.format(stack_id))
    except HTTPConflict as e:
        current_app.logger.error(
            "failed to create vm stack for {} using app {}. {} already exists".format(customer.name, app.name,
                                                                                      stack_name))
    except HTTPBadRequest as e:
        msg = "failed to create vm stack for {} using app {}. HTTP bad request".format(customer.name, app.name)
        current_app.logger.error(msg)
        abort(400, msg)
    except RuntimeError as e:
        current_app.logger.error(e)
        abort(404, "failed to create vms. error: {}".format(e))
    return stack_id


def create_ct_stack(customer, app, stack_name, config_file_path):
    current_app.logger.debug("starting to create dockers for {}".format(stack_name))
    cluster = app.cluster
    leader_name = '{}-0'.format(cluster.name)
    cmd = 'eval $(docker-machine env {}) && '.format(leader_name)
    host_env = os.environ.copy()
    if app.type == AppModel.APP_TYPE.Mixed.value:
        host_env[CLOUDLET_INSTANCE_ID] = stack_name
        host_env[CLOUDLET_NAMESERVER_IP] = cluster.leader_ip
        host_env[CLOUDLET_NAMESERVER_PORT] = str(cluster.nameserver_port)
        host_env[CLOUDLET_NAMESERVER_PW] = os.environ.get('REDIS_NAMESERVER_PW', None)
    cmd += 'docker stack deploy -c {} {}'.format(config_file_path, stack_name)
    p = Popen(cmd, stdin=PIPE, stdout=PIPE, stderr=PIPE, env=host_env, shell=True)
    # TODO: may need to change into non-blocking
    stdout, stderr = p.communicate()
    current_app.logger.debug("docker stdout: {}".format(stdout))
    current_app.logger.debug("docker stderr: {}".format(stderr))
    error_code = p.returncode
    if error_code:
        raise DockerContainerError(
            'docker stack error code {}. Failed to deploy containers from {}'.format(error_code, config_file_path))
    current_app.logger.debug('succesfully created container stack: {}'.format(stack_name))
    # using stack_name as stack id. see issue 4
    return stack_name


def delete_ct_stack(customer, app, stack_name):
    current_app.logger.debug("starting to delete dockers for {}".format(stack_name))
    cluster = app.cluster
    leader_name = '{}-0'.format(cluster.name)
    cmd = 'eval $(docker-machine env {}) && '.format(leader_name)
    host_env = os.environ.copy()
    cmd += 'docker stack rm {}'.format(stack_name)
    p = Popen(cmd, stdin=PIPE, stdout=PIPE, stderr=PIPE, env=host_env, shell=True)
    stdout, stderr = p.communicate()
    current_app.logger.debug("docker stdout: {}".format(stdout))
    current_app.logger.debug("docker stderr: {}".format(stderr))
    error_code = p.returncode


# TODO: move this to background celery task
# @celery.task()
def add_hostnames_to_nameserver(cluster, stack_name, stack_ids):
    current_app.logger.debug("adding hostnames to nameserver... ")
    ns_r = redis.StrictRedis(host=cluster.leader_public_ip, port=int(cluster.nameserver_port),
                             password=os.environ.get('REDIS_NAMESERVER_PW', None))
    # vms
    heat = get_heat_client()
    try:
        # TODO: when failed, stuck here
        vm_ns_entries = get_stack_ns_entries(heat, stack_ids[AppModel.APP_TYPE.VMs], ns_entry_prefix=stack_name)
        ns_r.mset(vm_ns_entries)
        current_app.logger.debug("added vms ns entries: {}".format(vm_ns_entries))
    except HTTPNotFound as e:
        current_app.logger.error("no such vm stack found. vm hostnames not added")
    except VMStackCreationError as e:
        current_app.logger.error(e)

    # containers
    dc = get_docker_client(cluster.leader_name)
    try:
        dses = get_services_in_stack(dc, stack_ids[AppModel.APP_TYPE.Containers])
        for ds in dses:
            ct_ns_entries = {}
            for port in ds.attrs['Endpoint']['Ports']:
                if 'PublishedPort' in port:
                    ct_ns_entry_key = '{}.{}'.format(port['TargetPort'], stack_name)
                    ct_ns_entries[ct_ns_entry_key] = port['PublishedPort']
            ns_r.mset(ct_ns_entries)
            current_app.logger.debug("added container service {} ns entries: {}".format(ds, ct_ns_entries))
    except KeyError as e:
        current_app.logger.error(e)
        current_app.logger.error("No Port key found in service {}. container ports not added".format(
            stack_ids[AppModel.APP_TYPE.Containers]))
    except NotFound as e:
        current_app.logger.error(e)
        current_app.logger.error("Container service ({}) not found. container ports not added".format(
            stack_ids[AppModel.APP_TYPE.Containers]))


def delete_hostnames_from_nameserver(cluster, stack_name, stack_ids):
    current_app.logger.debug("removing hostnames to nameserver... ")
    ns_r = redis.StrictRedis(host=cluster.leader_public_ip, port=int(cluster.nameserver_port),
                             password=os.environ.get('REDIS_NAMESERVER_PW', None))
    # vms
    heat = get_heat_client()
    try:
        vm_ns_entries = get_stack_ns_entries(heat, stack_ids[AppModel.APP_TYPE.VMs], ns_entry_prefix=stack_name)
        for key, _ in vm_ns_entries.iteritems():
            ns_r.delete(key)
        current_app.logger.debug("added vms ns entries: {}".format(vm_ns_entries))
    except HTTPNotFound as e:
        current_app.logger.error("no such vm stack found. vm hostnames not removed")
    except VMStackCreationError as e:
        current_app.logger.error(e)

    # containers
    dc = get_docker_client(cluster.leader_name)
    try:
        dses = get_services_in_stack(dc, stack_ids[AppModel.APP_TYPE.Containers])
        for ds in dses:
            ct_ns_entries = {}
            for port in ds.attrs['Endpoint']['Ports']:
                if 'PublishedPort' in port:
                    ct_ns_entry_key = '{}.{}'.format(port['TargetPort'], stack_name)
                    ct_ns_entries[ct_ns_entry_key] = port['PublishedPort']
            for key, _ in ct_ns_entries.iteritems():
                ns_r.delete(key)
            current_app.logger.debug("removed container service {} ns entries: {}".format(ds, ct_ns_entries))
    except KeyError as e:
        current_app.logger.error(e)
        current_app.logger.error("No Port key found in service {}. There are no container ports".format(
            stack_ids[AppModel.APP_TYPE.Containers]))
    except NotFound as e:
        current_app.logger.error(e)
        current_app.logger.error("Container service ({}) not found. container ports not added".format(
            stack_ids[AppModel.APP_TYPE.Containers]))


def create_instance(customer, app):
    creation_funcs = {
        AppModel.APP_TYPE.VMs: create_vm_stack,
        AppModel.APP_TYPE.Containers: create_ct_stack,
    }
    cluster = Cluster.query.filter_by(id=app.cluster_id).first()
    # start vm
    # start container
    # pass in the nameserver ip and port
    stack_ids = defaultdict(lambda: None)
    stack_name = '{}-{}-{}'.format(customer.name, app.name, len(customer.instance))
    # store meta data first, to avoid unnecessary conflicts in names
    instance = Instance.create(vm_stack_id=None,
                               ct_stack_id=None,
                               name=stack_name,
                               app_id=app.id,
                               customer_id=customer.id)
    customer.instance.append(instance)
    customer.update(instance=customer.instance)

    for key in AppModel.APP_TYPE:
        config_file_path = get_config_file_path(app.config_file_name[key])
        if key in creation_funcs and os.path.isfile(config_file_path):
            stack_ids[key] = creation_funcs[key](customer, app, stack_name, config_file_path)

    instance.update(vm_stack_id=stack_ids[AppModel.APP_TYPE.VMs])
    instance.update(ct_stack_id=stack_ids[AppModel.APP_TYPE.Containers])
    current_app.logger.debug("instance vm stack id {}".format(instance.vm_stack_id))
    current_app.logger.debug("instance container stack id {}".format(instance.ct_stack_id))
    # inject the instance id and names into the nameserver
    # if app.type == AppModel.APP_TYPE.Mixed.value:
    #     add_hostnames_to_nameserver.delay(cluster, stack_name, stack_ids)


def delete_instance(customer, app):
    heat = get_heat_client()
    instances = Instance.query.filter_by(app_id=app.id, customer_id=customer.id).all()
    if not instances:
        current_app.logger.error(
            "failed to delete app {1} for user {0}. The instance is not found".format(customer.name, app.name))
        # TODO: need to make sure client can handle 404
        abort(404, "no such instances to delete")

    ns_r = None
    cluster = None
    if app.type == AppModel.APP_TYPE.Mixed.value:
        cluster = Cluster.query.filter_by(id=app.cluster_id).first()
        ns_r = redis.StrictRedis(host=cluster.leader_public_ip, port=int(cluster.nameserver_port),
                                 password=os.environ.get('REDIS_NAMESERVER_PW', None))

    for instance in instances:
        current_app.logger.debug("starting to delete instance {}".format(instance))
        if ns_r:
            # remove its key from nameserver first
            delete_hostnames_from_nameserver(cluster, instance.name, instance.stack_ids)
        try:
            openstackutils.delete_stack(heat, instance.vm_stack_id)
        except HTTPNotFound as e:
            current_app.logger.debug('no vm to delete for app {} serving customer {}'.format(customer, app))
        delete_ct_stack(customer, app, instance.ct_stack_id)
        instance.delete()


def get_instance_info(customer, app):
    info = {}
    instance = Instance.query.filter_by(app_id=app.id, customer_id=customer.id).first()
    if not instance:
        raise InstanceNotFoundError(
            "Failed to get information app {1} for user {0}. Instance is not found".format(customer.name, app.name))
    if instance.vm_stack_id:
        heat = get_heat_client()
        stack_info = openstackutils.get_stack_info(heat, instance.vm_stack_id)
        info[AppModel.APP_TYPE.VMs.value] = stack_info
    if instance.ct_stack_id:
        cluster = app.cluster
        dc = get_docker_client(cluster.leader_name)
        published_ports = get_stack_published_ports(dc, instance.ct_stack_id)
        ct_info = {'ports': published_ports, 'ip': cluster.leader_public_ip}
        info[AppModel.APP_TYPE.Containers.value] = ct_info
    return info


def is_instance_provisioned(customer, app):
    instance = Instance.query.filter_by(app_id=app.id, customer_id=customer.id).first()
    if not instance:
        raise InstanceNotFoundError(
            "Failed to get information app {1} for user {0}. Instance is not found".format(customer.name, app.name))
    ct_status, vm_status = True, True
    if instance.vm_stack_id:
        heat = get_heat_client()
        vm_status = openstackutils.is_stack_provisioned(heat, instance.vm_stack_id)
    if instance.ct_stack_id:
        # TODO: assume container will always be created at least, since we're using blocking calls to create containers
        # cluster = app.cluster
        # dc = get_docker_client(cluster.leader_name)
        # ct_status = dockerutils.is_stack_provisioned(dc, instance.ct_stack_id)
        ct_status = True
    return ct_status and vm_status


@blueprint.route('/', methods=["GET", "POST"])
def create():
    current_app.logger.debug("request header: {} \n args: {}".format(request.headers, request.args))

    # support for both body and url parameters
    user_name = request.form.get('user_id')
    app_name = request.form.get('app_id')
    if not user_name:
        user_name = request.args.get('user_id')
        app_name = request.args.get('app_id')

    app = AppModel.query.filter_by(name=app_name).first()
    if not app:
        current_app.logger.debug("app not found {} for customer {}".format(app_name, user_name))
        abort(404, "No App Found")

    customer = Customer.query.filter_by(name=user_name).first()
    if not customer:
        customer = Customer.create(name=user_name)

    if request.method == 'POST':
        action = request.form.get('action')
        if not action:
            action = request.args.get('action')
        if action == "create":
            create_instance(customer, app)
        elif action == "delete":
            delete_instance(customer, app)
        else:
            current_app.logger.debug("Invalid action supplied.")
            abort(400, "Valid actions are 'create' and 'delete'")
    else:  # GET

        try:
            if not is_instance_provisioned(customer, app):
                current_app.logger.debug("instance in the middle of provisioning")
                return "None", 200
            if app.type == AppModel.APP_TYPE.Mixed.value:
                cluster = Cluster.query.filter_by(id=app.cluster_id).first()
                instance = Instance.query.filter_by(app_id=app.id, customer_id=customer.id).first()
                stack_name = instance.name
                stack_ids = {AppModel.APP_TYPE.VMs: instance.vm_stack_id,
                             AppModel.APP_TYPE.Containers: instance.ct_stack_id}
                add_hostnames_to_nameserver(cluster, stack_name, stack_ids)
            info = {}
            info = get_instance_info(customer, app)
        except InstanceNotFoundError as e:
            current_app.logger.error(e)
            abort(404, e)
        return json.dumps(info), 200
    return "success", 200
