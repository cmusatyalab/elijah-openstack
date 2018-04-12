#!/usr/bin/env python
import os
import pdb
import re
import time

from flask import current_app, abort
from subprocess import Popen, PIPE
import docker

from caas.core.exc import VMStackCreationError
from caas.core.machine import Machine


def get_docker_client(machine_name):
    dm = Machine()
    leader_env_str = dm.env(machine=machine_name).split('\n')
    pat = re.compile(r'export (.*)="(.*)"')
    denv = {}
    for env_str in leader_env_str:
        mat = pat.match(str(env_str))
        if mat:
            denv[mat.group(1)] = mat.group(2)
    c = None
    if denv["DOCKER_TLS_VERIFY"] == "1":
        cert_path = denv["DOCKER_CERT_PATH"]
        tls_config = docker.tls.TLSConfig(
            client_cert=(os.path.join(cert_path, 'cert.pem'), os.path.join(cert_path, 'key.pem'))
        )
        c = docker.DockerClient(base_url=denv['DOCKER_HOST'], version="auto", tls=tls_config)
    else:
        c = docker.DockerClient(base_url=denv['DOCKER_HOST'], version="auto")
    return c


def get_services_in_stack(dc, stack_name):
    return dc.services.list(filters={'name': stack_name})


def get_service_published_port(ds):
    # {'TargetPort':'PublishedPort'}
    published_ports = {}
    if 'Endpoint' in ds.attrs and 'Ports' in ds.attrs['Endpoint']:
        for port in ds.attrs['Endpoint']['Ports']:
            if 'PublishedPort' in port:
                published_ports[str(port['TargetPort'])] = str(port['PublishedPort'])
    return published_ports


def get_compose_service_name(ds):
    '''
    docker's service name is tied with stack it's created in.
     This function returns the service name as in compose file
    :param ds: 
    :return: 
    '''
    sname = ds.name
    if 'Spec' in ds.attrs and 'Labels' in ds.attrs['Spec']:
        lbs = ds.attrs['Spec']['Labels']
        # docker stack name space, get stack name
        stack_prefix = lbs.get('com.docker.stack.namespace', '')
        # 'stackname_' is used by docker stack as a prefix
        if stack_prefix:
            sname = sname[len(stack_prefix)+1:]
    return sname


def get_stack_published_ports(dc, stack_name):
    stack_ports_info = {}
    dses = get_services_in_stack(dc, stack_name)
    for ds in dses:
        ds_published_ports = get_service_published_port(ds)
        name = get_compose_service_name(ds)
        stack_ports_info[name] = ds_published_ports
    return stack_ports_info


def is_stack_provisioned(dc, stack_name):
    dses = get_services_in_stack(dc, stack_name)
    for ds in dses:
        tasks = ds.tasks()
        for task in tasks:
            # pdb.set_trace()
            # TODO to finish
            pass
    return True
