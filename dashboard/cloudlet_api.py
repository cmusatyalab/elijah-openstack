# Elijah: Cloudlet Infrastructure for Mobile Computing
#
#   Author: Kiryong Ha <krha@cmu.edu>
#
#   Copyright (C) 2011-2014 Carnegie Mellon University
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#
import logging

import glanceclient as glance_client

from django.conf import settings
from novaclient.v1_1 import client as nova_client
import httplib
import json
from urlparse import urlparse
from openstack_dashboard.api.base import url_for


LOG = logging.getLogger(__name__)


def request_create_overlay(request, instance_id):
    token = request.user.token.id
    management_url = url_for(request, 'compute')
    end_point = urlparse(management_url)

    overlay_name = "overlay-" + str(instance_id)
    params = json.dumps({
        "cloudlet-overlay-finish": {
            "overlay-name": overlay_name
        }
    })
    headers = {"X-Auth-Token": token, "Content-type": "application/json"}

    conn = httplib.HTTPConnection(end_point[1])
    command = "%s/servers/%s/action" % (end_point[2], instance_id)
    conn.request("POST", command, params, headers)
    response = conn.getresponse()
    data = response.read()
    dd = json.loads(data)
    conn.close()

    return dd


def request_synthesis(request, vm_name, base_disk_id, flavor_id, key_name,
                      security_group_id, overlay_url):
    token = request.user.token.id
    management_url = url_for(request, 'compute')
    end_point = urlparse(management_url)

    # other data
    meta_data = {"overlay_url": overlay_url}
    s = {
        "server": {
            "name": vm_name, "imageRef": base_disk_id,
            "flavorRef": flavor_id, "metadata": meta_data,
            "min_count": "1", "max_count": "1",
            "security_group": security_group_id,
            "key_name": key_name,
            }}
    params = json.dumps(s)
    headers = {"X-Auth-Token": token, "Content-type": "application/json"}

    conn = httplib.HTTPConnection(end_point[1])
    conn.request("POST", "%s/servers" % end_point[2], params, headers)
    response = conn.getresponse()
    data = response.read()
    dd = json.loads(data)
    conn.close()
    return dd


def request_handoff(request, instance_id, handoff_url,
                    dest_token, dest_vmname):
    token = request.user.token.id
    management_url = url_for(request, 'compute')
    end_point = urlparse(management_url)

    params = json.dumps({
        "cloudlet-handoff": {
            "handoff_url": handoff_url,
            "dest_token": dest_token,
            "dest_vmname": dest_vmname,
        }
    })
    headers = {"X-Auth-Token": token, "Content-type": "application/json"}

    conn = httplib.HTTPConnection(end_point[1])
    command = "%s/servers/%s/action" % (end_point[2], instance_id)
    conn.request("POST", command, params, headers)
    response = conn.getresponse()
    data = response.read()
    conn.close()
    dd = json.loads(data)
    return dd


