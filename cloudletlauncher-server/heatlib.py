#!/usr/bin/env python

import time

def start_heat_connection(AUTH_URL = "http://172.16.0.2:5000/v3",
                          #AUTH_URL = "http://10.3.0.243:35357/v3",
                          USERNAME = "admin",
                          PASSWORD = "rabbitseatcarrots",
                          PROJECT_NAME = "admin",
                          USER_DOMAIN_ID = "default",
                          USER_DOMAIN_NAME = "default",
                          PROJECT_DOMAIN_ID = "default"):

    from heatclient import client
    from keystoneauth1 import loading
    from keystoneauth1 import session

    loader = loading.get_plugin_loader('password')
    auth = loader.load_from_options(auth_url = AUTH_URL,
                                    username = USERNAME,
                                    password = PASSWORD,
                                    project_name = PROJECT_NAME,
                                    user_domain_name = USER_DOMAIN_NAME,
                                    user_domain_id = USER_DOMAIN_ID,
                                    project_domain_id = PROJECT_DOMAIN_ID,)
    sess = session.Session(auth = auth)
    heat = client.Client('1', session = sess)
    heat.stacks.list()

    return heat

def create_stack(heat, template_file = 'template.yaml', stack_name = 'default_stack', instance_name = None):
    stack_id = ""
    with open(template_file, 'r') as template:
        template_str = template.read()
        if instance_name is not None:
            template_str = template_str.replace('default_instance', instance_name)
        ret = heat.stacks.create(stack_name = stack_name, template = template_str, parameters = {})
        stack_id = ret['stack']['id']
    return stack_id

def delete_stack(heat, stack_id):
    stack = heat.stacks.delete(stack_id)

def get_stack_ip(heat, stack_id):
    stack = heat.stacks.get(stack_id)
    while stack.stack_status != "CREATE_COMPLETE":
        return None

    vm_ip = None
    for item in stack.outputs:
        if item['output_key'] == "instance_ip":
            vm_ip = item['output_value']
            break
    return vm_ip

if __name__ == "__main__":
    heat = start_heat_connection()
    stack_id = create_stack(heat)
    print stack_id
