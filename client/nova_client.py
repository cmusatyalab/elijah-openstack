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
import subprocess
import urllib

from optparse import OptionParser
from urlparse import urlparse
from tempfile import mkdtemp
from util import CLOUDLET_TYPE

from elijah.provisioning.package import PackagingUtil
from elijah.provisioning.package import _FileFile
from elijah.provisioning.package import BaseVMPackage
import glanceclient as glance_client
import zipfile
import shutil



class CloudletClientError(Exception):
    pass


def get_list(server_address, token, end_point, request_list):
    if not request_list in ('images', 'flavors', 'extensions', 'servers'):
        sys.stderr.write("Error, Cannot support listing for %s\n" % request_list)
        sys.exit(1)

    params = urllib.urlencode({})
    headers = { "X-Auth-Token":token, "Content-type":"application/json" }
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
    #print json.dumps(dd, indent=2)
    conn.close()
    return dd[request_list]


def request_new_server(server_address, token, end_point, \
        key_name=None, image_name=None, server_name=None):
    # basic data
    image_ref, image_id = get_ref_id(server_address, token, \
            end_point, "images", image_name)
    flavor_ref, flavor_id = get_ref_id(server_address, token, \
            end_point, "flavors", "m1.tiny")
    # other data
    sMetadata = {}
    s = { \
            "server": { \
                "name": server_name, "imageRef": image_id, \
                "flavorRef": flavor_id, "metadata": sMetadata, \
                "min_count":"1", "max_count":"1",
                "key_name": key_name,
                } }
    params = json.dumps(s)
    headers = { "X-Auth-Token":token, "Content-type":"application/json" }
    #print json.dumps(s, indent=4)

    conn = httplib.HTTPConnection(end_point[1])
    conn.request("POST", "%s/servers" % end_point[2], params, headers)
    print "request new server: %s/servers" % (end_point[2])
    response = conn.getresponse()
    data = response.read()
    dd = json.loads(data)
    conn.close()
    print json.dumps(dd, indent=2)


def request_synthesis(server_address, token, end_point, key_name=None,\
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
    for image in image_list:
        properties = image.get("metadata", None)
        if properties == None or len(properties) == 0:
            continue
        if properties.get(CLOUDLET_TYPE.PROPERTY_KEY_CLOUDLET_TYPE) != \
                CLOUDLET_TYPE.IMAGE_TYPE_BASE_DISK:
            continue
        base_sha256_uuid = properties.get(CLOUDLET_TYPE.PROPERTY_KEY_BASE_UUID)
        if base_sha256_uuid == requested_basevm_id:
            basevm_uuid = image['id']
            break
    if basevm_uuid == None:
        raise CloudletClientError("Cannot find matching Base VM with (%s)" %\
                str(requested_basevm_id))

    # basic data
    flavor_ref, flavor_id = get_ref_id(server_address, token, end_point, "flavors", "m1.tiny")
    # other data
    meta_data = {"overlay_url": overlay_url}
    s = { \
            "server": { \
                "name": server_name, "imageRef": str(basevm_uuid), \
                "flavorRef": flavor_id, "metadata": meta_data, \
                "min_count":"1", "max_count":"1",
                "key_name": key_name,
                } }
    params = json.dumps(s)
    headers = { "X-Auth-Token":token, "Content-type":"application/json" }
    print json.dumps(s, indent=4)
    conn = httplib.HTTPConnection(end_point[1])
    conn.request("POST", "%s/servers" % end_point[2], params, headers)
    print "request new server: %s/servers" % (end_point[2])
    response = conn.getresponse()
    data = response.read()
    dd = json.loads(data)
    conn.close()

    print json.dumps(dd, indent=2)
    return dd

def request_start_stop(server_address, token, end_point, server_name, is_request_start):
    server_list = get_list(server_address, token, end_point, "servers")
    server_id = ''
    for server in server_list:
        if server['name'] == server_name:
            server_id = server['id']
            print "server id : " + server_id
    if not server_id:
        return False, "no such VM named : %s" % server_name

    if is_request_start:
        params = json.dumps({"os-start":"null"})
    else:
        params = json.dumps({"os-stop":"null"})
    headers = { "X-Auth-Token":token, "Content-type":"application/json" }

    conn = httplib.HTTPConnection(end_point[1])
    command = "%s/servers/%s/action" % (end_point[2], server_id)
    print command
    conn.request("POST", command, params, headers)
    response = conn.getresponse()
    data = response.read()
    conn.close()
    print data


def request_cloudlet_base(server_address, token, end_point, server_name, cloudlet_base_name):
    server_list = get_list(server_address, token, end_point, "servers")
    server_id = ''
    for server in server_list:
        if server['name'] == server_name:
            server_id = server['id']
            print "server id : " + server_id
    if not server_id:
        raise CloudletClientError("cannot find matching instance with %s", server_name)

    params = json.dumps({"cloudlet-base":{"name": cloudlet_base_name}})
    headers = { "X-Auth-Token":token, "Content-type":"application/json" }

    conn = httplib.HTTPConnection(end_point[1])
    command = "%s/servers/%s/action" % (end_point[2], server_id)
    conn.request("POST", command, params, headers)
    response = conn.getresponse()
    data = response.read()
    conn.close()
    print json.dumps(data, indent=2)
    return data


def request_cloudlet_overlay_start(server_address, token, end_point, image_name, key_name):
    #get right iamge
    image_list = get_list(server_address, token, end_point, "images")
    image_id = ''
    meta = {}
    for image in image_list:
        print "%s == %s" % (image.get('name'), image_name)
        if image.get('name') == image_name:
            metadata = image.get('metadata')
            if metadata and metadata.get('memory_snapshot_id'):
                image_id = image.get('id')
                meta['image_snapshot_id']=metadata.get('memory_snapshot_id')

    if not image_id:
        raise CloudletClientError("cannot find matching image")

    flavor_ref, flavor_id = get_ref_id(server_address, token, end_point, "flavors", "m1.tiny")
    s = { \
            "server": { \
                "name": image_name+"-overlay", "imageRef": image_id, \
                "flavorRef": flavor_id, \
                "metadata": meta, \
                "min_count":"1", "max_count":"1",\
                "key_name": key_name \
                } }
    params = json.dumps(s)
    headers = { "X-Auth-Token":token, "Content-type":"application/json" }
    print json.dumps(s, indent=4)

    conn = httplib.HTTPConnection(end_point[1])
    conn.request("POST", "%s/servers" % end_point[2], params, headers)
    print "request new server: %s/servers" % (end_point[2])
    response = conn.getresponse()
    data = response.read()
    dd = json.loads(data)
    conn.close()
    print json.dumps(dd, indent=2)


def request_cloudlet_overlay_stop(server_address, token, end_point, \
        instance_uuid, overlay_name):
    server_list = get_list(server_address, token, end_point, "servers")
    server_id = ''
    for server in server_list:
        if server['id'] == instance_uuid:
            server_id = server['id']
    if not server_id:
        raise CloudletClientError("cannot find matching server name")

    params = json.dumps({"cloudlet-overlay-finish":{"overlay-name": overlay_name}})
    headers = { "X-Auth-Token":token, "Content-type":"application/json" }

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
    headers = { "X-Auth-Token":token, "Content-type":"application/json" }
    end_string = "%s/servers/%s" % (end_point[2], server_uuid)
    conn.request("GET", end_string, params, headers)
    response = conn.getresponse()
    data = response.read()
    dd = json.loads(data)
    conn.close()

    floating_ip = None
    if dd.get('server', None) == None:
        raise CloudletClientError("cannot find matching server : %s" % \
                server_uuid)
    if dd['server'].get('addresses', None) != None:
        ipinfo_list = dd['server']['addresses'].get('private', None)
        if ipinfo_list != None:
            for each_ipinfo in ipinfo_list:
                if each_ipinfo.has_key("OS-EXT-IPS:type"):
                    floating_ip = str(each_ipinfo['addr'])

    status = dd['server']['status']
    return status, floating_ip


def get_token(server_address, user, password, tenant_name):
    url = "%s:5000" % server_address
    params = {
            "auth":
                {"passwordCredentials":{"username":user, "password":password},
            "tenantName":tenant_name}
            }
    headers = {"Content-Type": "application/json"}

    # HTTP connection
    conn = httplib.HTTPConnection(url)
    #print json.dumps(params, indent=4)
    #print headers
    conn.request("POST", "/v2.0/tokens", json.dumps(params), headers)

    # HTTP response
    response = conn.getresponse()
    data = response.read()
    dd = json.loads(data)
    conn.close()

    #print json.dumps(dd, indent=4)
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
    except KeyError, e:
        sys.stderr.write(str(e) + "\n")
        sys.stderr.write("Malformed return from OpenStack\n")
        sys.stderr.write(str(dd))
    return api_token, nova_endpoint, glance_endpoint


def overlay_download(server_address, token, glance_endpoint, overlay_name, output_file):
    """ 
    glance API has been changed so the below code does not work
    http://api.openstack.org/api-ref-image.html
    """ 
    
    fout = open(output_file, "wb")
    _PIPE = subprocess.PIPE
    cmd = "glance image-download %s" % (overlay_name)
    proc = subprocess.Popen(cmd.split(" "), stdout=fout, stderr=_PIPE)
    out, err = proc.communicate()
    
    if err:
        print err


def basevm_import(server_address, uname, password, tenant_name, import_filepath, basevm_name):

    token, endpoint, glance_endpoint = \
            get_token(server_address, uname, password, tenant_name)
    (base_hashvalue, disk_name, memory_name, diskhash_name, memoryhash_name) = \
            PackagingUtil._get_basevm_attribute(import_filepath)

    # check duplicated base VM
    image_list = get_list(server_address, token, urlparse(endpoint), "images")
    for image in image_list:
        properties = image.get("metadata", None)
        if properties == None or len(properties) == 0:
            continue
        if properties.get(CLOUDLET_TYPE.PROPERTY_KEY_CLOUDLET_TYPE) != \
                CLOUDLET_TYPE.IMAGE_TYPE_BASE_DISK:
            continue
        base_sha256_uuid = properties.get(CLOUDLET_TYPE.PROPERTY_KEY_BASE_UUID)
        if base_sha256_uuid == base_hashvalue:
            msg = "Duplicated base VM is already exists on the system"
            msg += "UUID of duplicated Base VM: %s" % image['id']
            raise CloudletClientError(msg)

    # decompress files
    temp_dir = mkdtemp(prefix="cloudlet-base-")
    sys.stdout.write("Decompressing zipfile(%s) to temp dir(%s)\n" % (import_filepath, temp_dir))
    zipbase = zipfile.ZipFile(_FileFile("file:///%s" % import_filepath), 'r')
    zipbase.extractall(temp_dir)
    disk_path = os.path.join(temp_dir, disk_name)
    memory_path = os.path.join(temp_dir, memory_name)
    diskhash_path = os.path.join(temp_dir, diskhash_name)
    memoryhash_path = os.path.join(temp_dir, memoryhash_name)

    # upload base disk
    def _create_param(filepath, image_name, image_type):
        properties = {
                "image_type": "snapshot",
                "image_location":"snapshot",
                CLOUDLET_TYPE.PROPERTY_KEY_CLOUDLET:"True",
                CLOUDLET_TYPE.PROPERTY_KEY_CLOUDLET_TYPE:image_type,
                CLOUDLET_TYPE.PROPERTY_KEY_BASE_UUID:base_hashvalue,
            }
        param = {
                "name": "%s" % image_name, 
                "data": open(filepath, "rb"),
                "size": os.path.getsize(filepath),
                "is_public":True,
                "disk_format":"raw",
                "container_format":"bare",
                "properties": properties,
                }
        return param

    disk_param = _create_param(disk_path, basevm_name + "-disk", 
            CLOUDLET_TYPE.IMAGE_TYPE_BASE_DISK) 
    memory_param = _create_param(memory_path, basevm_name + "-memory", 
            CLOUDLET_TYPE.IMAGE_TYPE_BASE_MEM) 
    diskhash_param = _create_param(diskhash_path, basevm_name + "-diskhash", 
            CLOUDLET_TYPE.IMAGE_TYPE_BASE_DISK_HASH) 
    memoryhash_param = _create_param(memoryhash_path, basevm_name + "-memhash", 
            CLOUDLET_TYPE.IMAGE_TYPE_BASE_MEM_HASH) 

    o = urlparse(glance_endpoint)
    url = "://".join((o.scheme, o.netloc))
    gclient = glance_client.Client('1', url, token=token, insecure=True)

    sys.stdout.write("upload base memory to glance\n")
    glance_memory = gclient.images.create(**memory_param)
    sys.stdout.write("upload base disk hash to glance\n")
    glance_diskhash = gclient.images.create(**diskhash_param)
    sys.stdout.write("upload base memory hash to glance\n")
    glance_memoryhash = gclient.images.create(**memoryhash_param)

    glance_ref = {
            CLOUDLET_TYPE.IMAGE_TYPE_BASE_MEM: glance_memory.id,
            CLOUDLET_TYPE.IMAGE_TYPE_BASE_DISK_HASH: glance_diskhash.id,
            CLOUDLET_TYPE.IMAGE_TYPE_BASE_MEM_HASH: glance_memoryhash.id,
            }

    disk_param['properties'].update(glance_ref)
    sys.stdout.write("upload base disk to glance\n")
    glance_disk = gclient.images.create(**disk_param)
    sys.stdout.write("SUCCESS\n")
    return glance_disk


def basevm_download(server_address, token, end_point, basedisk_uuid, output_file):
    image_list = get_list(server_address, token, end_point, "images")

    base_sha256_uuid = None
    basememory_uuid = None
    diskhash_uuid = None
    memoryhash_uuid = None
    for image in image_list:
        properties = image.get("metadata", None)
        if properties == None or len(properties) == 0:
            continue
        if properties.get(CLOUDLET_TYPE.PROPERTY_KEY_CLOUDLET_TYPE) != \
                CLOUDLET_TYPE.IMAGE_TYPE_BASE_DISK:
            continue
        base_sha256_uuid = properties.get(CLOUDLET_TYPE.PROPERTY_KEY_BASE_UUID)
        if basedisk_uuid == image['id']:
            basememory_uuid = properties.get(CLOUDLET_TYPE.IMAGE_TYPE_BASE_MEM)
            diskhash_uuid = properties.get(CLOUDLET_TYPE.IMAGE_TYPE_BASE_DISK_HASH)
            memoryhash_uuid = properties.get(CLOUDLET_TYPE.IMAGE_TYPE_BASE_MEM_HASH)
            break

    if base_sha256_uuid == None or basememory_uuid == None or \
            diskhash_uuid == None or memoryhash_uuid == None:
        raise CloudletClientError("Cannot find relevant files for (%s)" %\
                str(basedisk_uuid))

    temp_dir = mkdtemp(prefix="cloudlet-basevm-")
    download_list = {
            basedisk_uuid: os.path.join(temp_dir, 'base_disk.img'),
            basememory_uuid: os.path.join(temp_dir, 'base_memory.img'),
            diskhash_uuid: os.path.join(temp_dir, 'base_disk_hash'),
            memoryhash_uuid: os.path.join(temp_dir, 'base_memory_hash'),
            }

    for (uuid, filename) in download_list.iteritems():
        sys.stdout.write("Downloaing %s at (%s)..\n" % \
                (os.path.basename(filename), filename))
        sys.stdout.flush()
        overlay_download(server_address, token, end_point, uuid, filename)

    BaseVMPackage.create(output_file, base_sha256_uuid, \
            download_list[basedisk_uuid], 
            download_list[basememory_uuid],
            download_list[diskhash_uuid],
            download_list[memoryhash_uuid])

    if os.path.exists(temp_dir) == True:
        shutil.rmtree(temp_dir)


def print_usage(commands):
    usage = "\n%prog command [option]\n"
    usage += "Command list:\n"
    MAX_SPACE = 20
    for (comm, desc) in commands.iteritems():
        space = ""
        if len(comm) < MAX_SPACE: 
            space = " " * (20-len(comm))
        usage += "  %s%s : %s\n" % (comm, space, desc)
    return usage


def process_command_line(argv, commands):
    parser = OptionParser(usage=print_usage(commands),
            version="Cloudlet Synthesys(piping) 0.1")
    parser.add_option(
            '-s', '--server', action='store', type='string',
            dest='server_address', default='localhost',
            help='set openstack api server address')
    parser.add_option(
            '-u', '--user', action='store', type='string', 
            dest='user_name', help='set username')
    parser.add_option(
            '-p', '--password', action='store', type='string', 
            dest='password', help='set password')
    parser.add_option(
            '-t', '--tenant', action='store', type='string', 
            dest='tenant_name', help='set tenant name')

    settings, args = parser.parse_args(argv)
    if settings.user_name == None:
        msg = "Need username for OpenStack API\n"
        msg += "Check the information using 'nova user-list'"
        parser.error(msg)
    if settings.password == None:
        parser.error("Need password for OpenStack API")
    if settings.tenant_name == None:
        msg = "Need tenant name for OpenStack API\n"
        msg += "Check the information using 'nova tenant-list'"
        parser.error(msg)
    
    if not len(args) != 0:
        parser.error("Need command, Choose among :\n  %s" % " | ".join(commands))
    mode = str(args[0]).lower()
    if mode not in commands.keys():
        parser.error("Invalid Command, Choose among :\n  %s" % " | ".join(commands))

    return settings, args


def get_extension(server_address, token, end_point, extension_name):
    ext_list = get_list(server_address, token, end_point, "extensions")
    #print json.dumps(ext_list, indent=4)

    if extension_name:
        for ext in ext_list:
            if ext['name'] == extension_name:
                return ext
    else:
        return ext_list


def get_ref_id(server_address, token, end_point, ref_string, name):
    support_ref_string = ("images", "flavors")
    if not ref_string in support_ref_string:
        sys.stderr.write("We support only %s, but requested reference is %s", " ".join(support_ref_string), ref_string)
        sys.exit(1)

    params = urllib.urlencode({})
    headers = { "X-Auth-Token":token, "Content-type":"application/json" }
    conn = httplib.HTTPConnection(end_point[1])
    conn.request("GET", "%s/%s" % (end_point[2], ref_string), params, headers)
    print "requesting %s/%s" % (end_point[2], ref_string)
    
    # HTTP response
    response = conn.getresponse()
    data = response.read()
    dd = json.loads(data)
    conn.close()
    #print json.dumps(dd, indent=2)

    # Server image URL
    n = len(dd[ref_string])
    for i in range(n):
        if dd[ref_string][i]['name'] == name:
            image_ref = dd[ref_string][i]["links"][0]["href"]
            return image_ref, dd[ref_string][i]['id']

    raise Exception("No such name: %s" % name)


def get_cloudlet_base_list(server_address, uname, password):
    from glance import client
    glance_client = client.get_client(server_address, username=uname, password=password)
    image_list = glance_client.get_images()
    for image in image_list:
        print "image list : %s" % image.get('name')


def main(argv=None):
    CMD_CREATE_BASE     = "create-base"
    CMD_CREATE_OVERLAY  = "create-overlay"
    CMD_DOWNLOAD        = "download"
    CMD_SYNTHESIS       = "synthesis"
    CMD_BOOT            = "boot"
    CMD_EXT_LIST        = "ext-list"
    CMD_IMAGE_LIST      = "image-list"
    CMD_EXPORT_BASE     = "export-base"
    CMD_IMPORT_BASE     = "import-base"
    commands = {
            CMD_CREATE_BASE: "create base vm from the running instance",
            CMD_CREATE_OVERLAY: "create VM overlay from the customizaed VM",
            CMD_DOWNLOAD: "Download VM overlay",
            CMD_SYNTHESIS: "VM Synthesis (Need downloadable URLs for VM overlay",
            CMD_BOOT : "Boot VM disk using predefined configuration (testing purpose",
            CMD_EXT_LIST: "List available extensions",
            CMD_IMAGE_LIST: "List images",
            CMD_EXPORT_BASE: "Export Base VM",
            CMD_IMPORT_BASE: "Import Base VM",
            }

    settings, args = process_command_line(sys.argv[1:], commands)
    print "Connecting to %s for tenant %s" % \
            (settings.server_address, settings.tenant_name)
    token, endpoint, glance_endpoint = \
            get_token(settings.server_address, settings.user_name, 
                    settings.password, settings.tenant_name)

    if len(args) < 1:
        print "need command"
        sys.exit(1)
    if args[0] == CMD_CREATE_BASE:
        instance_name = raw_input("Name of a running instance that you like to make as a base VM : ")
        snapshot_name = raw_input("Set name of Base VM : ")
        request_cloudlet_base(settings.server_address, token, \
                urlparse(endpoint), instance_name, snapshot_name) 
    elif args[0] == CMD_CREATE_OVERLAY:
        instance_uuid = raw_input("UUID of a running instance that you like to create VM overlay : ")
        snapshot_name = raw_input("Set name of VM overlay : ")
        request_cloudlet_overlay_stop(settings.server_address, token, urlparse(endpoint), \
                instance_uuid, snapshot_name)
    elif args[0] == CMD_DOWNLOAD:
        VM_overlay_meta = raw_input("Name of VM overlay file: ")
        overlay_download(settings.server_address, token, urlparse(glance_endpoint),\
                VM_overlay_meta, VM_overlay_meta)
    elif args[0] == CMD_EXPORT_BASE:
        basedisk_uuid = raw_input("UUID of a base disk : ")
        output_path = os.path.join(os.curdir, "base-%s.zip" % basedisk_uuid)
        if os.path.exists(output_path) == True:
            is_overwrite = raw_input("%s exists. Overwirte it? (y/N) " % output_path)
            if is_overwrite != 'y':
                sys.exit(1)
        basevm_download(settings.server_address, token, \
                urlparse(endpoint), basedisk_uuid, output_path)
    elif args[0] == CMD_IMPORT_BASE:
        import_filepath = args[1]
        if os.access(import_filepath, os.R_OK) == False:
            sys.stderr("Cannot access the file at %s" % import_filepath)
            sys.exit(1)
        basevm_name = raw_input("Input the name of base VM : ")
        basevm_import(settings.server_address, settings.user_name, 
                settings.password, settings.tenant_name, 
                import_filepath, basevm_name)
    elif args[0] == CMD_SYNTHESIS:
        overlay_url = raw_input("URL for VM overlay metafile : ")
        new_instance_name = raw_input("Set VM's name : ")
        request_synthesis(settings.server_address, token, urlparse(endpoint), \
                key_name=None, server_name=new_instance_name, \
                overlay_url=overlay_url)
    elif args[0] == CMD_EXT_LIST:
        filter_name = None
        if len(args)==2:
            filter_name = args[1]
        ext_info = get_extension(settings.server_address, token, urlparse(endpoint), filter_name)
        print json.dumps(ext_info, indent=2)
    elif args[0] == CMD_IMAGE_LIST:
        images = get_list(settings.server_address, token, \
                urlparse(endpoint), "images")
        print json.dumps(images, indent=2)
    elif args[0] == CMD_BOOT:
        image_name = raw_input("Specify disk image by name : ")
        new_instance_name = raw_input("Set VM's name : ")
        images = request_new_server(settings.server_address, \
                token, urlparse(endpoint), key_name=None, \
                image_name=image_name, server_name=new_instance_name)
    elif args[0] == 'ip-address':
        server_uuid = args[1]
        ret = request_cloudlet_ipaddress(settings.server_address, token, urlparse(endpoint), \
                server_uuid=server_uuid)
        print str(ret)
    else:
        print "No such command"
        sys.exit(1)
    '''
    elif args[0] == 'flavor-list':
        images = get_list(settings.server_address, token, urlparse(endpoint), "flavors")
        print json.dumps(images, indent=2)
    elif args[0] == 'server-list':
        images = get_list(settings.server_address, token, urlparse(endpoint), "servers")
        print json.dumps(images, indent=2)
    elif args[0] == 'overlay_start':
        request_cloudlet_overlay_start(settings.server_address, token, urlparse(endpoint), image_name=test_base_name, key_name="test")
    elif args[0] == 'cloudlet_list':
        print get_cloudlet_base_list(settings.server_address, "admin", "admin")
    '''


if __name__ == "__main__":
    status = main()
    sys.exit(status)


