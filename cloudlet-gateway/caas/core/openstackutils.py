#!/usr/bin/env python
import os
import pdb
import re
import time

from flask import current_app, abort
from subprocess import Popen, PIPE

from caas.core.exc import VMStackCreationError, OpenStackError


def start_heat_connection(AUTH_URL=None,
                          USERNAME=None,
                          PASSWORD=None,
                          PROJECT_NAME=None,
                          TENANT_ID=None,
                          TENANT_NAME=None,
                          USER_DOMAIN_ID="default",
                          USER_DOMAIN_NAME="default",
                          PROJECT_DOMAIN_ID="default"):
    from heatclient import client
    from keystoneauth1 import loading
    from keystoneauth1 import session

    loader = loading.get_plugin_loader('password')
    auth = loader.load_from_options(auth_url=AUTH_URL,
                                    username=USERNAME,
                                    password=PASSWORD,
                                    project_name=PROJECT_NAME,
                                    user_domain_name=USER_DOMAIN_NAME,
                                    user_domain_id=USER_DOMAIN_ID,
                                    project_domain_id=PROJECT_DOMAIN_ID)

    # auth = loader.load_from_options(auth_url=AUTH_URL,
    #                                 username=USERNAME,
    #                                 password=PASSWORD,
    #                                 tenant_id=TENANT_ID,
    #                                 tenant_name=TENANT_NAME,
    #                                 project_name=PROJECT_NAME)

    sess = session.Session(auth=auth)
    heat = client.Client('1', session=sess)
    heat.stacks.list()

    return heat


def create_stack(heat, template_file='template.yaml', stack_name='default_stack', instance_name=None, parameters={}):
    stack_id = ""
    with open(template_file, 'r') as template:
        template_str = template.read()
        ret = heat.stacks.create(stack_name=stack_name, template=template_str, parameters=parameters)
        stack_id = ret['stack']['id']
    return stack_id


def delete_stack(heat, stack_id):
    stack = heat.stacks.delete(stack_id)


def wait_for_stack_status(heat, stack_id):
    while True:
        stack = heat.stacks.get(stack_id)
        current_app.logger.debug('vm stack {} status: {}'.format(stack_id, stack.status))
        if 'FAILED' in stack.status:
            raise VMStackCreationError(stack.identifier)
        elif 'COMPLETE' in stack.status:
            return stack
        time.sleep(1)


def get_stack_ns_entries(heat, stack_id, ns_heat_prefix='ns_', ns_entry_prefix=''):
    stack = wait_for_stack_status(heat, stack_id)
    ns_entries = {}
    ip_pat = re.compile(r"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})", re.UNICODE)
    for item in stack.outputs:
        entry_key = item['output_key']
        if ns_heat_prefix in entry_key:
            ns_entry_key = '{}.{}'.format(entry_key[len(ns_heat_prefix):], ns_entry_prefix)
            # regular expression to match ip addresses only
            ip_mat = ip_pat.search(item['output_value'])
            if ip_mat:
                ip = ip_mat.group(1)
                ns_entries[ns_entry_key] = ip
    return ns_entries


def get_stack_info(heat, stack_id):
    stack = heat.stacks.get(stack_id)
    resp = {}
    resp['status'] = stack.stack_status
    if 'COMPLETE' in stack.stack_status:
        if hasattr(stack, 'outputs'):
            for item in stack.outputs:
                resp[item['output_key']] = item['output_value']
    return resp


def is_stack_provisioned(heat, vm_stack_id):
    stack_status = get_stack_info(heat, vm_stack_id)
    if 'COMPLETE' in stack_status['status']:
        return True
    else:
        return False

# no need to deal with floating ip should only use internal ip for now
def get_floating_ip():
    cmd = "nova floating-ip-list | awk -F '[[:space:]]*|[[:space:]]*' '$6==\"-\" {print $4}'"
    p = Popen(cmd, stdin=PIPE, stdout=PIPE, stderr=PIPE, env=os.environ.copy(), shell=True)
    stdout, stderr = p.communicate()
    error_code = p.returncode
    if error_code:
        abort(400, 'something went wrong when trying to get an available floating ip')
    pat = re.compile("\d{1,3}.\d{1,3}.\d{1,3}.\d{1,3}")
    match = pat.match(stdout)
    floating_ip = None
    if match:
        floating_ip = match.group(0)
    return floating_ip


def os_allocate_floating_ip():
    cmd = "nova floating-ip-create | awk 'match($0,/([0-9]+\.)+[0-9]+/) {print substr($0,RSTART,RLENGTH)}' "
    p = Popen(cmd, stdin=PIPE, stdout=PIPE, stderr=PIPE, env=os.environ.copy(), shell=True)
    stdout, stderr = p.communicate()
    error_code = p.returncode
    if error_code:
        abort(400, 'something went wrong when allocating a floating ip')
    # remove extra \n if there is
    stdout = stdout.replace('\n', '')
    current_app.logger.debug(stdout)
    current_app.logger.debug(stderr)
    return str(stdout)


def get_fixed_ip_from_floating_ip(ip):
    cmd = "nova floating-ip-list | awk -F '[[:space:]]*|[[:space:]]*' '$4==\"{}\" {{print $8}}'".format(ip)
    p = Popen(cmd, stdin=PIPE, stdout=PIPE, stderr=PIPE, env=os.environ.copy(), shell=True)
    stdout, stderr = p.communicate()
    error_code = p.returncode
    if error_code:
        raise OpenStackError("Failed to get fixed ip for floating ip {}".format(ip))
    return stdout.strip(' \t\n\r')


def get_floating_ip_id(ip):
    cmd = "nova floating-ip-list | awk -F '[[:space:]]*|[[:space:]]*' '$4==\"{}\" {{print $2}}'".format(ip)
    p = Popen(cmd, stdin=PIPE, stdout=PIPE, stderr=PIPE, env=os.environ.copy(), shell=True)
    stdout, stderr = p.communicate()
    error_code = p.returncode
    if error_code:
        abort(400, 'something went wrong when find the ID of floating ip {}'.format(ip))
    current_app.logger.debug(stdout)
    pat = re.compile("\d+")
    match = pat.match(stdout)
    floating_ip_id = match.group(0)
    return floating_ip_id


if __name__ == "__main__":
    heat = start_heat_connection()
    stack_id = create_stack(heat)
    print stack_id


