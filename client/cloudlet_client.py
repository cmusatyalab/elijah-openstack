#!/usr/bin/env python
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
import sys
import os
import httplib
import json
import math
import subprocess
import urllib

from pprint import pprint
from optparse import OptionParser
from urlparse import urlparse
from tempfile import mkdtemp
from client_util import CLOUDLET_TYPE
from client_util import CLOUDLET_COMMAND
from client_util import find_matching_flavor
from client_util import get_resource_size
from client_util import create_flavor

from elijah.provisioning.package import PackagingUtil
from elijah.provisioning.package import _FileFile
import elijah.provisioning.memory_util as elijah_memory_util
from elijah.provisioning.package import BaseVMPackage
import glanceclient as glance_client
import zipfile
import shutil


class CloudletClientError(Exception):
    pass


def get_list(server_address, token, end_point, request_list):
    if not request_list in ('images', 'flavors', 'extensions', 'servers'):
        sys.stderr.write(
            "Error, Cannot support listing for %s\n" %
            request_list)
        sys.exit(1)

    params = urllib.urlencode({})
    headers = {"X-Auth-Token": token, "Content-type": "application/json"}
    if request_list == 'extensions':
        end_string = "%s/%s" % (end_point[2], request_list)
    else:
        end_string = "%s/%s/detail" % (end_point[2], request_list)

    # HTTP response
    conn = httplib.HTTPConnection(end_point[1])
    conn.request("GET", end_string, params, headers)
    response = conn.getresponse()
    data = response.read()
    dd = json.loads(data)
    conn.close()
    return dd[request_list]


def request_synthesis(server_address, token, end_point, key_name=None,
                      server_name=None, overlay_url=None):
    # read meta data from vm overlay URL
    from elijah.provisioning.package import VMOverlayPackage
    try:
        from elijah.provisioning import msgpack
    except ImportError as e:
        import msgpack

    overlay_package = VMOverlayPackage(overlay_url)
    meta_raw = overlay_package.read_meta()
    meta_info = msgpack.unpackb(meta_raw)
    requested_basevm_id = meta_info['base_vm_sha256']

    # find matching base VM
    image_list = get_list(server_address, token, end_point, "images")
    basevm_uuid = None
    basevm_xml = None
    basevm_name = None
    basevm_disk = 0
    for image in image_list:
        properties = image.get("metadata", None)
        if properties is None or len(properties) == 0:
            continue
        if properties.get(CLOUDLET_TYPE.PROPERTY_KEY_CLOUDLET_TYPE) != \
                CLOUDLET_TYPE.IMAGE_TYPE_BASE_DISK:
            continue
        base_sha256_uuid = properties.get(CLOUDLET_TYPE.PROPERTY_KEY_BASE_UUID)
        if base_sha256_uuid == requested_basevm_id:
            basevm_uuid = image['id']
            basevm_name = image['name']
            basevm_xml = properties.get(
                CLOUDLET_TYPE.PROPERTY_KEY_BASE_RESOURCE,
                None)
            basevm_disk = image.get('minDisk', 0)
            break
    if basevm_uuid is None:
        raise CloudletClientError("Cannot find matching Base VM with (%s)" %
                                  str(requested_basevm_id))

    # find matching flavor.
    if basevm_xml is None:
        msg = "Cannot find resource allocation information of base VM (%s)" %\
                str(requested_basevm_id)
        raise CloudletClientError(msg)
    cpu_count, memory_mb = get_resource_size(basevm_xml)
    flavor_list = get_list(server_address, token, end_point, "flavors")
    flavor_ref, flavor_id = find_matching_flavor(flavor_list, cpu_count,
                                                 memory_mb, basevm_disk)
    if flavor_ref == None or flavor_id == None:
        msg = "Cannot find matching flavor: vcpu (%d), ram (%d MB), disk (%d GB)\n" % (
            cpu_count, memory_mb, basevm_disk)
        msg += "Please create the matching at your OpenStack"
        raise CloudletClientError(msg)

    # generate request
    meta_data = {"overlay_url": overlay_url}
    s = {
        "server": {
            "name": server_name, "imageRef": str(basevm_uuid),
            "flavorRef": flavor_id, "metadata": meta_data,
            "min_count": "1", "max_count": "1",
            "key_name": key_name,
            }}
    params = json.dumps(s)
    headers = {"X-Auth-Token": token, "Content-type": "application/json"}
    conn = httplib.HTTPConnection(end_point[1])
    conn.request("POST", "%s/servers" % end_point[2], params, headers)
    sys.stdout.write("request new server: %s/servers\n" % (end_point[2]))
    response = conn.getresponse()
    data = response.read()
    dd = json.loads(data)
    conn.close()
    return dd


def _request_handoff_recv(server_address, token, end_point,
                          server_name=None, overlay_url=None):
    """Test for handoff receving"""

    # read meta data from vm overlay URL
    from elijah.provisioning.package import VMOverlayPackage
    try:
        from elijah.provisioning import msgpack
    except ImportError as e:
        import msgpack

    overlay_package = VMOverlayPackage(overlay_url)
    meta_raw = overlay_package.read_meta()
    meta_info = msgpack.unpackb(meta_raw)
    requested_basevm_id = meta_info['base_vm_sha256']

    # find matching base VM
    image_list = get_list(server_address, token, end_point, "images")
    basevm_uuid = None
    basevm_xml = None
    basevm_name = None
    basevm_disk = 0
    for image in image_list:
        properties = image.get("metadata", None)
        if properties is None or len(properties) == 0:
            continue
        if properties.get(CLOUDLET_TYPE.PROPERTY_KEY_CLOUDLET_TYPE) != \
                CLOUDLET_TYPE.IMAGE_TYPE_BASE_DISK:
            continue
        base_sha256_uuid = properties.get(CLOUDLET_TYPE.PROPERTY_KEY_BASE_UUID)
        if base_sha256_uuid == requested_basevm_id:
            basevm_uuid = image['id']
            basevm_name = image['name']
            basevm_xml = properties.get(
                CLOUDLET_TYPE.PROPERTY_KEY_BASE_RESOURCE,
                None)
            basevm_disk = image.get('minDisk', 0)
            break
    if basevm_uuid is None:
        raise CloudletClientError(
            "Cannot find matching Base VM with (%s)" %
            str(requested_basevm_id))

    # find matching flavor
    if basevm_xml is None:
        msg = "Cannot find resource allocation information of base VM (%s)" %\
                str(requested_basevm_id)
        raise CloudletClientError(msg)
    cpu_count, memory_mb = get_resource_size(basevm_xml)
    flavor_list = get_list(server_address, token, end_point, "flavors")
    flavor_ref, flavor_id = find_matching_flavor(flavor_list, cpu_count,
                                                 memory_mb, basevm_disk)
    if flavor_ref == None or flavor_id == None:
        msg = "Cannot find matching flavor with vcpu:%d, ram:%d, disk:%d\n" % (
            cpu_count, memory_mb, basevm_disk)
        msg += "Please create one at your OpenStack"
        raise CloudletClientError(msg)

    # generate request
    meta_data = {"handoff_info": overlay_url}
    s = {"server":
         {
             "name": server_name, "imageRef": str(basevm_uuid),
             "flavorRef": flavor_id, "metadata": meta_data,
             "min_count": "1", "max_count": "1",
             "key_name": None,
         }
         }
    params = json.dumps(s)
    headers = {"X-Auth-Token": token, "Content-type": "application/json"}
    conn = httplib.HTTPConnection(end_point[1])
    conn.request("POST", "%s/servers" % end_point[2], params, headers)
    sys.stdout.write("request new server: %s/servers\n" % (end_point[2]))
    response = conn.getresponse()
    data = response.read()
    dd = json.loads(data)
    conn.close()
    return dd


def request_start_stop(server_address, token, end_point,
                       server_name, is_request_start):
    server_list = get_list(server_address, token, end_point, "servers")
    server_id = ''
    for server in server_list:
        if server['name'] == server_name:
            server_id = server['id']
            print "server id : " + server_id
    if not server_id:
        return False, "no such VM named : %s" % server_name

    if is_request_start:
        params = json.dumps({"os-start": "null"})
    else:
        params = json.dumps({"os-stop": "null"})
    headers = {"X-Auth-Token": token, "Content-type": "application/json"}

    conn = httplib.HTTPConnection(end_point[1])
    command = "%s/servers/%s/action" % (end_point[2], server_id)
    conn.request("POST", command, params, headers)
    response = conn.getresponse()
    data = response.read()
    conn.close()
    print data


def request_cloudlet_base(server_address, token, end_point,
                          server_uuid, cloudlet_base_name):
    server_list = get_list(server_address, token, end_point, "servers")
    server_id = ''
    for server in server_list:
        if server['id'] == server_id:
            server_id = server['id']
            break
    if not server_id:
        raise CloudletClientError(
            "cannot find matching instance with %s", server_uuid)

    params = json.dumps({"cloudlet-base": {"name": cloudlet_base_name}})
    headers = {"X-Auth-Token": token, "Content-type": "application/json"}

    conn = httplib.HTTPConnection(end_point[1])
    command = "%s/servers/%s/action" % (end_point[2], server_id)
    conn.request("POST", command, params, headers)
    response = conn.getresponse()
    data = response.read()
    conn.close()
    print json.dumps(data, indent=2)
    return data


def request_cloudlet_overlay_start(server_address, token, end_point,
                                   image_name, key_name):
    # get right iamge
    image_list = get_list(server_address, token, end_point, "images")
    image_id = ''
    meta = {}
    for image in image_list:
        print "%s == %s" % (image.get('name'), image_name)
        if image.get('name') == image_name:
            metadata = image.get('metadata')
            if metadata and metadata.get('memory_snapshot_id'):
                image_id = image.get('id')
                meta['image_snapshot_id'] = metadata.get('memory_snapshot_id')

    if not image_id:
        raise CloudletClientError("cannot find matching image")

    flavor_ref, flavor_id = get_ref_id(
        server_address, token, end_point, "flavors", "m1.tiny")
    s = {
        "server": {
            "name": image_name+"-overlay", "imageRef": image_id,
            "flavorRef": flavor_id,
            "metadata": meta,
            "min_count": "1", "max_count": "1",
            "key_name": key_name
            }}
    params = json.dumps(s)
    headers = {"X-Auth-Token": token, "Content-type": "application/json"}
    print json.dumps(s, indent=4)

    conn = httplib.HTTPConnection(end_point[1])
    conn.request("POST", "%s/servers" % end_point[2], params, headers)
    print "request new server: %s/servers" % (end_point[2])
    response = conn.getresponse()
    data = response.read()
    dd = json.loads(data)
    conn.close()
    print json.dumps(dd, indent=2)


def request_create_overlay(server_address, token, end_point,
                           instance_uuid, overlay_name):
    server_list = get_list(server_address, token, end_point, "servers")
    server_id = ''
    for server in server_list:
        if server['id'] == instance_uuid:
            server_id = server['id']
    if not server_id:
        msg = "cannot find matching instance UUID (%s)" % instance_uuid
        raise CloudletClientError(msg)

    params = json.dumps(
        {"cloudlet-overlay-finish": {"overlay-name": overlay_name}})
    headers = {"X-Auth-Token": token, "Content-type": "application/json"}

    conn = httplib.HTTPConnection(end_point[1])
    command = "%s/servers/%s/action" % (end_point[2], server_id)
    conn.request("POST", command, params, headers)
    response = conn.getresponse()
    data = response.read()
    dd = json.loads(data)
    conn.close()
    return dd


def request_handoff(server_address, token, end_point,
                    instance_uuid, handoff_url, dest_token=None):
    server_list = get_list(server_address, token, end_point, "servers")
    server_id = ''
    server_name = ''
    for server in server_list:
        if server['id'] == instance_uuid:
            server_id = server['id']
            server_name = server['name']
    if not server_id:
        raise CloudletClientError("cannot find matching UUID (%s)\n" %\
                                  instance_uuid)
    params = json.dumps({
        "cloudlet-handoff": {
            CLOUDLET_COMMAND.PROPERTY_KEY_HANDOFF_URL: handoff_url,
            CLOUDLET_COMMAND.PROPERTY_KEY_HANDOFF_DEST_TOKEN: dest_token,
            CLOUDLET_COMMAND.PROPERTY_KEY_HANDOFF_DEST_VM_NAME: server_name,
        }
    })
    headers = {"X-Auth-Token": token, "Content-type": "application/json"}

    conn = httplib.HTTPConnection(end_point[1])
    command = "%s/servers/%s/action" % (end_point[2], server_id)
    conn.request("POST", command, params, headers)
    response = conn.getresponse()
    data = response.read()
    conn.close()
    print data


def request_cloudlet_ipaddress(server_address, token, end_point, server_uuid):
    params = urllib.urlencode({})
    # HTTP response
    conn = httplib.HTTPConnection(end_point[1])
    headers = {"X-Auth-Token": token, "Content-type": "application/json"}
    end_string = "%s/servers/%s" % (end_point[2], server_uuid)
    conn.request("GET", end_string, params, headers)
    response = conn.getresponse()
    data = response.read()
    dd = json.loads(data)
    conn.close()

    floating_ip = None
    if dd.get('server', None) is None:
        raise CloudletClientError("cannot find matching server : %s" %
                                  server_uuid)
    if dd['server'].get('addresses', None) is not None:
        ipinfo_list = dd['server']['addresses'].get('private', None)
        if ipinfo_list is not None:
            for each_ipinfo in ipinfo_list:
                if "OS-EXT-IPS:type" in each_ipinfo:
                    floating_ip = str(each_ipinfo['addr'])

    status = dd['server']['status']
    return status, floating_ip


def get_token(server_address, user, password, tenant_name):
    url = "%s:5000" % server_address
    params = {
        "auth":
        {"passwordCredentials": {"username": user, "password": password},
         "tenantName": tenant_name}
        }
    headers = {"Content-Type": "application/json"}

    # HTTP connection
    conn = httplib.HTTPConnection(url)
    # print json.dumps(params, indent=4)
    # print headers
    conn.request("POST", "/v2.0/tokens", json.dumps(params), headers)

    # HTTP response
    response = conn.getresponse()
    data = response.read()
    dd = json.loads(data)
    conn.close()

    # print json.dumps(dd, indent=4)
    try:
        api_token = dd['access']['token']['id']
        service_list = dd['access']['serviceCatalog']
        nova_endpoint = None
        glance_endpoint = None
        for service in service_list:
            if service['name'] == 'nova':
                nova_endpoint = service['endpoints'][0]['publicURL']
            elif service['name'] == 'glance':
                glance_endpoint = service['endpoints'][0]['publicURL']
    except KeyError as e:
        sys.stderr.write(str(e) + "\n")
        sys.stderr.write("Malformed return from OpenStack\n")
        sys.stderr.write(str(dd))
        sys.exit(1)
    return api_token, nova_endpoint, glance_endpoint


def overlay_download(server_address, token, glance_endpoint,
                     image_name, output_file):
    """
    glance API has been changed so the below code does not work
    http://api.openstack.org/api-ref-image.html
    """

    fout = open(output_file, "wb")
    _PIPE = subprocess.PIPE
    cmd = "glance image-download %s" % (image_name)
    proc = subprocess.Popen(cmd.split(" "), stdout=fout, stderr=_PIPE)
    out, err = proc.communicate()
    if err:
        print err


def request_import_basevm(server_address, token, 
                          endpoint, glance_endpoint,
                          import_filepath, basevm_name):
    def _create_param(filepath, image_name, image_type, disk_size, mem_size):
        properties = {
            "image_type": "snapshot",
            "image_location": "snapshot",
            CLOUDLET_TYPE.PROPERTY_KEY_CLOUDLET: "True",
            CLOUDLET_TYPE.PROPERTY_KEY_CLOUDLET_TYPE: image_type,
            CLOUDLET_TYPE.PROPERTY_KEY_BASE_UUID: base_hashvalue,
            }
        param = {
            "name": "%s" % image_name,
            "data": open(filepath, "rb"),
            "size": os.path.getsize(filepath),
            "is_public": True,
            "disk_format": "raw",
            "container_format": "bare",
            "min_disk": disk_size,
            "min_ram": mem_size,
            "properties": properties,
            }
        return param
    (base_hashvalue, disk_name, memory_name, diskhash_name, memoryhash_name) = \
        PackagingUtil._get_basevm_attribute(import_filepath)

    # check duplicated base VM
    image_list = get_list(server_address, token, endpoint, "images")
    for image in image_list:
        properties = image.get("metadata", None)
        if properties is None or len(properties) == 0:
            continue
        if properties.get(CLOUDLET_TYPE.PROPERTY_KEY_CLOUDLET_TYPE) != \
                CLOUDLET_TYPE.IMAGE_TYPE_BASE_DISK:
            continue
        base_sha256_uuid = properties.get(CLOUDLET_TYPE.PROPERTY_KEY_BASE_UUID)
        if base_sha256_uuid == base_hashvalue:
            msg = "Duplicated base VM is already exists on the system\n"
            msg += "Image UUID of duplicated Base VM: %s\n" % image['id']
            raise CloudletClientError(msg)

    # decompress files
    temp_dir = mkdtemp(prefix="cloudlet-base-")
    sys.stdout.write(
        "Decompressing zipfile(%s) to temp dir(%s)\n" %
        (import_filepath, temp_dir))
    zipbase = zipfile.ZipFile(
        _FileFile("file:///%s" % os.path.abspath(import_filepath)), 'r')
    zipbase.extractall(temp_dir)
    disk_path = os.path.join(temp_dir, disk_name)
    memory_path = os.path.join(temp_dir, memory_name)
    diskhash_path = os.path.join(temp_dir, diskhash_name)
    memoryhash_path = os.path.join(temp_dir, memoryhash_name)

    # create new flavor if nothing matches
    memory_header = elijah_memory_util._QemuMemoryHeader(open(memory_path))
    libvirt_xml_str = memory_header.xml
    cpu_count, memory_size_mb = get_resource_size(libvirt_xml_str)
    disk_gb = int(math.ceil(os.path.getsize(disk_path)/1024.0/1024.0/1024.0))
    flavor_list = get_list(server_address, token, endpoint, "flavors")
    flavor_ref, flavor_id = find_matching_flavor(flavor_list, cpu_count,
                                                 memory_size_mb, disk_gb)
    if flavor_id == None:
       flavor_name = "cloudlet-flavor-%s" % basevm_name
       flavor_ref, flavor_id = create_flavor(server_address,
                                             token,
                                             endpoint,
                                             cpu_count,
                                             memory_size_mb,
                                             disk_gb,
                                             flavor_name)
       sys.stdout.write("Create new flavor for the base VM\n")

    # upload Base VM
    disk_param = _create_param(disk_path, basevm_name + "-disk",
                               CLOUDLET_TYPE.IMAGE_TYPE_BASE_DISK,
                               disk_gb, memory_size_mb)
    memory_param = _create_param(memory_path, basevm_name + "-memory",
                                 CLOUDLET_TYPE.IMAGE_TYPE_BASE_MEM,
                                 disk_gb, memory_size_mb)
    diskhash_param = _create_param(diskhash_path, basevm_name + "-diskhash",
                                   CLOUDLET_TYPE.IMAGE_TYPE_BASE_DISK_HASH,
                                   disk_gb, memory_size_mb)
    memoryhash_param = _create_param(memoryhash_path, basevm_name + "-memhash",
                                     CLOUDLET_TYPE.IMAGE_TYPE_BASE_MEM_HASH,
                                     disk_gb, memory_size_mb)
    url = "://".join((glance_endpoint.scheme, glance_endpoint.netloc))
    gclient = glance_client.Client('1', url, token=token, insecure=True)
    sys.stdout.write("upload base memory to glance\n")
    glance_memory = gclient.images.create(**memory_param)
    sys.stdout.write("upload base disk hash to glance\n")
    glance_diskhash = gclient.images.create(**diskhash_param)
    sys.stdout.write("upload base memory hash to glance\n")
    glance_memoryhash = gclient.images.create(**memoryhash_param)

    # upload Base disk at the last to have references for other image files
    glance_ref = {
        CLOUDLET_TYPE.IMAGE_TYPE_BASE_MEM: glance_memory.id,
        CLOUDLET_TYPE.IMAGE_TYPE_BASE_DISK_HASH: glance_diskhash.id,
        CLOUDLET_TYPE.IMAGE_TYPE_BASE_MEM_HASH: glance_memoryhash.id,
        CLOUDLET_TYPE.PROPERTY_KEY_BASE_RESOURCE:
        libvirt_xml_str.replace("\n", "")  # API cannot send '\n'
        }
    disk_param['properties'].update(glance_ref)
    sys.stdout.write("upload base disk to glance\n")
    glance_disk = gclient.images.create(**disk_param)

    # delete temp dir
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)

    return glance_disk


def request_export_basevm(server_address, token, end_point,
                          basedisk_uuid, output_file):
    image_list = get_list(server_address, token, end_point, "images")

    base_sha256_uuid = None
    basememory_uuid = None
    diskhash_uuid = None
    memoryhash_uuid = None
    for image in image_list:
        properties = image.get("metadata", None)
        if properties is None or len(properties) == 0:
            continue
        if properties.get(CLOUDLET_TYPE.PROPERTY_KEY_CLOUDLET_TYPE) != \
                CLOUDLET_TYPE.IMAGE_TYPE_BASE_DISK:
            continue
        base_sha256_uuid = properties.get(CLOUDLET_TYPE.PROPERTY_KEY_BASE_UUID)
        if basedisk_uuid == image['id']:
            basememory_uuid = properties.get(CLOUDLET_TYPE.IMAGE_TYPE_BASE_MEM)
            diskhash_uuid = properties.get(
                CLOUDLET_TYPE.IMAGE_TYPE_BASE_DISK_HASH)
            memoryhash_uuid = properties.get(
                CLOUDLET_TYPE.IMAGE_TYPE_BASE_MEM_HASH)
            break

    if base_sha256_uuid is None or basememory_uuid is None or \
            diskhash_uuid is None or memoryhash_uuid is None:
        raise CloudletClientError("Cannot find relevant files for (%s)" %
                                  str(basedisk_uuid))

    temp_dir = mkdtemp(prefix="cloudlet-basevm-")
    download_list = {
        basedisk_uuid: os.path.join(temp_dir, 'base_disk.img'),
        basememory_uuid: os.path.join(temp_dir, 'base_memory.img'),
        diskhash_uuid: os.path.join(temp_dir, 'base_disk_hash'),
        memoryhash_uuid: os.path.join(temp_dir, 'base_memory_hash'),
        }

    for (uuid, filename) in download_list.iteritems():
        sys.stdout.write("Downloaing %s at (%s)..\n" %
                         (os.path.basename(filename), filename))
        sys.stdout.flush()
        overlay_download(server_address, token, end_point, uuid, filename)
    sys.stdout.write("start packaging...(this can take a while)")
    BaseVMPackage.create(output_file, base_sha256_uuid,
                         download_list[basedisk_uuid],
                         download_list[basememory_uuid],
                         download_list[diskhash_uuid],
                         download_list[memoryhash_uuid])

    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)


def print_usage(commands):
    usage = "\n%prog -c credential_file command [option]\n"
    usage += "Command list:\n"
    MAX_SPACE = 20
    for (comm, desc) in commands.iteritems():
        space = ""
        if len(comm) < MAX_SPACE:
            space = " " * (20-len(comm))
        usage += "  %s%s : %s\n" % (comm, space, desc)
    return usage


def _parse_credential_file(infile):
    cred_dict = json.loads(open(infile, "r").read())
    for each_key in ['account', 'password', 'tenant', 'server_addr']:
        if each_key not in cred_dict:
            raise CloudletClientError("No %s info at %s" % (each_key, infile))
    return cred_dict['account'], cred_dict['password'], cred_dict['tenant'], cred_dict['server_addr']


def process_command_line(argv, commands):
    parser = OptionParser(usage=print_usage(commands),
                          version="Cloudlet Synthesys(piping) 0.1")
    parser.add_option(
        '-c', '--credential', action='store', type='string',
        dest='credential_file', default=None,
        help='path to the credential file')

    settings, args = parser.parse_args(argv)
    if settings.credential_file is None:
        msg = ("\nSpecify file path to a credential information of the OpenStack"
               "\ncredential file is a JSON formatted file that has 'account',"
               "\n'password', 'tenent', and 'server_addr' as key.\n"
               "\nExample)"
               "\n$ cat ./cred_openstack"
               "\n{"
               "\n    \"account\": \"myaccount\","
               "\n    \"password\": \"mypassword\","
               "\n    \"tenant\": \"demo\","
               "\n    \"server_addr\": \"myopenstack.com\""
               "\n}\n")
        parser.error(msg)
    try:
        cred_info = _parse_credential_file(settings.credential_file)
        user_name, password, tenant_name, server_addr = cred_info
        settings.user_name = user_name
        settings.password = password
        settings.tenant_name = tenant_name
        settings.server_address = server_addr
    except CloudletClientError as e:
        sys.stderr.write(str(e))
        sys.exit(1)


    if not len(args) != 0:
        parser.error(
            "Need command, Choose among :\n  %s" %
            " | ".join(commands))
    mode = str(args[0]).lower()
    if mode not in commands.keys():
        parser.error(
            "Invalid Command, Choose among :\n  %s" %
            " | ".join(commands))

    return settings, args


def get_extension(server_address, token, end_point, extension_name):
    ext_list = get_list(server_address, token, end_point, "extensions")

    if extension_name:
        for ext in ext_list:
            if ext['name'] == extension_name:
                return ext
    else:
        return ext_list


def get_ref_id(server_address, token, end_point, ref_string, name):
    support_ref_string = ("images", "flavors")
    if not ref_string in support_ref_string:
        sys.stderr.write(
            "We support only %s, but requested reference is %s",
            " ".join(support_ref_string),
            ref_string)
        sys.exit(1)

    params = urllib.urlencode({})
    headers = {"X-Auth-Token": token, "Content-type": "application/json"}
    conn = httplib.HTTPConnection(end_point[1])
    conn.request("GET", "%s/%s" % (end_point[2], ref_string), params, headers)
    print "requesting %s/%s" % (end_point[2], ref_string)

    # HTTP response
    response = conn.getresponse()
    data = response.read()
    dd = json.loads(data)
    conn.close()

    # Server image URL
    n = len(dd[ref_string])
    for i in range(n):
        if dd[ref_string][i]['name'] == name:
            image_ref = dd[ref_string][i]["links"][0]["href"]
            return image_ref, dd[ref_string][i]['id']

    raise Exception("No such name: %s" % name)


def get_cloudlet_base_list(server_address, uname, password):
    from glance import client
    glance_client = client.get_client(
        server_address,
        username=uname,
        password=password)
    image_list = glance_client.get_images()
    for image in image_list:
        print "image list : %s" % image.get('name')


def main(argv=None):
    CMD_CREATE_BASE = "create-base"
    CMD_EXPORT_BASE = "export-base"
    CMD_IMPORT_BASE = "import-base"
    CMD_CREATE_OVERLAY = "create-overlay"
    CMD_DOWNLOAD = "download"
    CMD_SYNTHESIS = "synthesis"
    CMD_HANDOFF = "handoff"
    CMD_HANDOFF_RECV = "handoff-recv"
    CMD_EXT_LIST = "ext-list"
    commands = {
        CMD_CREATE_BASE: "create base vm from the running instance",
        CMD_CREATE_OVERLAY: "create VM overlay from the customizaed VM",
        CMD_DOWNLOAD: "Download VM overlay",
        CMD_SYNTHESIS: "VM Synthesis (Need downloadable URLs for VM overlay)",
        CMD_HANDOFF: "Perform VM handoff to destination URL",
        CMD_HANDOFF_RECV: "Send handoff recv message to the dest OpenStack",
        CMD_EXT_LIST: "List available extensions",
        CMD_EXPORT_BASE: "Export Base VM",
        CMD_IMPORT_BASE: "Import Base VM",
    }

    settings, args = process_command_line(sys.argv[1:], commands)
    token, endpoint, glance_endpoint = \
        get_token(settings.server_address, settings.user_name,
                  settings.password, settings.tenant_name)
    sys.stdout.write("Success to log in to %s for tenant %s..\n" % \
        (settings.server_address, settings.tenant_name))

    if len(args) < 1:
        sys.stderr.write("Need command")
        sys.exit(1)
    if args[0] == CMD_CREATE_BASE:
        if len(args) != 3:
            msg = "Error: creating Base VM needs [VM UUID] and [new name]\n"
            msg += " 1) VM UUID: UUID of a running instance that you want to use for base VM\n"
            msg += " 2) new name: name for base VM\n"
            sys.stderr.write(msg)
            sys.exit(1)
        instance_uuid = args[1]
        snapshot_name = args[2]
        request_cloudlet_base(settings.server_address, token,
                              urlparse(endpoint), instance_uuid,
                              snapshot_name)
    elif args[0] == CMD_CREATE_OVERLAY:
        if len(args) != 3:
            msg = "Error: creating VM overlay needs [VM UUID] and [new name]\n"
            msg += " 1) VM UUID: UUID of a running instance that you want to create VM overlay\n"
            msg += " 2) new name: name for VM overlay\n"
            sys.stderr.write(msg)
            sys.exit(1)
        instance_uuid = args[1]
        snapshot_name = args[2]
        ret = request_create_overlay(settings.server_address,
                                     token,
                                     urlparse(endpoint),
                                     instance_uuid,
                                     snapshot_name)
        pprint(ret)
    elif args[0] == CMD_DOWNLOAD:
        if len(args) != 2:
            msg = "Error: downlading VM overlay needs [Image UUID]\n"
            msg += " 1) Image UUID: UUID of a VM overlay\n"
            sys.stderr.write(msg)
            sys.exit(1)
        image_name = args[1]
        output_name = image_name + ".zip"
        sys.stdout.write("Download %s to %s...\n" % (image_name, output_name))
        overlay_download(settings.server_address, token,
                         urlparse(glance_endpoint),
                         image_name, output_name)
    elif args[0] == CMD_EXPORT_BASE:
        if len(args) != 2:
            msg = "Error: Exporting Base VM needs [Image UUID]\n"
            msg += " 1) Image UUID: UUID of a Base VM (base disk)\n"
            sys.stderr.write(msg)
            sys.exit(1)
        basedisk_uuid = args[1]
        output_path = os.path.join(os.curdir, "base-%s.zip" % basedisk_uuid)
        sys.stdout.write("Export %s to %s...\n" % (basedisk_uuid, output_path))
        if os.path.exists(output_path):
            is_overwrite = raw_input(
                "%s exists. Overwirte it? (y/N) " %
                output_path)
            if is_overwrite != 'y':
                sys.exit(1)
        request_export_basevm(settings.server_address, token,
                              urlparse(endpoint), basedisk_uuid, output_path)
    elif args[0] == CMD_IMPORT_BASE:
        if len(args) != 3:
            msg = "Error: Importing Base VM needs [Path to Base VM file] [Name for Base VM]\n"
            msg += " 1) Path to Base VM file: Absolute path to base VM package\n"
            msg += " 2) Name for Base VM: new name for Base VM\n"
            sys.stderr.write(msg)
            sys.exit(1)
        import_filepath = args[1]
        basevm_name = args[2]
        if os.access(import_filepath, os.R_OK) == False:
            sys.stderr("Cannot access the file at %s" % import_filepath)
            sys.exit(1)
        try:
            request_import_basevm(settings.server_address, token,
                                  urlparse(endpoint), urlparse(glance_endpoint),
                                  import_filepath, basevm_name)
            sys.stdout.write("SUCCESS\n")
        except CloudletClientError as e:
            sys.stderr.write("Error: %s\n" % str(e))
    elif args[0] == CMD_SYNTHESIS:
        if len(args) != 3:
            msg = "Error: synthesis cmd needs [overlay url] and [name of VM]\n"
            sys.stderr.write(msg)
            sys.exit(1)
        overlay_url = str(args[1])
        new_instance_name = str(args[2])
        try:
            ret = request_synthesis(settings.server_address, token,
                                    urlparse(endpoint), key_name=None,
                                    server_name=new_instance_name,
                                    overlay_url=overlay_url)
            pprint(ret)
        except CloudletClientError as e:
            sys.stderr.write("Error: %s\n" % str(e))
    elif args[0] == CMD_HANDOFF:
        if len(args) != 3:
            msg = "Error: VM handoff needs [Instance UUID] []\n"
            msg += " 1) Instance UUID: Absolute path to base VM package\n"
            msg += " 2) Destination Credential : File path of a credential file for destination OpenStacknew\n"
            sys.stderr.write(msg)
            sys.exit(1)
        instance_uuid = str(args[1])
        handoff_dest_credential_file = str(args[2])

        try:
            # get token for the handoff destination
            dest_cred = _parse_credential_file(handoff_dest_credential_file)
            dest_account, dest_passwd, dest_tenant, dest_addr = dest_cred
            dest_token, dest_endpoint, dest_glance_endpoint = \
                get_token(dest_addr, dest_account, dest_passwd,
                            dest_tenant)
            handoff_url = dest_endpoint

            request_handoff(settings.server_address,
                            token, urlparse(endpoint),
                            instance_uuid,
                            handoff_url,
                            dest_token)
        except CloudletClientError as e:
            sys.stderr.write(str(e))
            sys.exit(1)
    elif args[0] == CMD_HANDOFF_RECV:
        if not len(args) == 3:
            msg = "Need overlay_url and name of the instance"
            raise CloudletClientError(msg)

        overlay_url = str(args[1])
        new_instance_name = str(args[2])
        try:
            _request_handoff_recv(settings.server_address, token,
                                  urlparse(endpoint),
                                  server_name=new_instance_name,
                                  overlay_url=overlay_url)
        except CloudletClientError as e:
            sys.stderr.write("Error: %s\n" % str(e))
    elif args[0] == CMD_EXT_LIST:
        filter_name = None
        if len(args) == 2:
            filter_name = args[1]
        ext_info = get_extension(settings.server_address,
                                    token,
                                    urlparse(endpoint),
                                    filter_name)
        sys.stdout.write(json.dumps(ext_info, indent=2) + "\n")
    else:
        sys.stderr.write("No such command")
        sys.exit(1)


if __name__ == "__main__":
    status = main()
    sys.exit(status)
