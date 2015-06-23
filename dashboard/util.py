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
"""
Views for managing Images and Snapshots.
"""

import logging
from xml.etree import ElementTree

LOG = logging.getLogger(__name__)


class CloudletUtilError(Exception):
    pass


# original is defined at cloudlet_api.py
class CLOUDLET_TYPE(object):
    PROPERTY_KEY_CLOUDLET       = "is_cloudlet"
    PROPERTY_KEY_CLOUDLET_TYPE  = "cloudlet_type"
    PROPERTY_KEY_NETWORK_INFO   = "network"
    PROPERTY_KEY_BASE_UUID      = "base_sha256_uuid"
    PROPERTY_KEY_BASE_RESOURCE  = "base_resource_xml_str"

    IMAGE_TYPE_BASE_DISK        = "cloudlet_base_disk"
    IMAGE_TYPE_BASE_MEM         = "cloudlet_base_memory"
    IMAGE_TYPE_BASE_DISK_HASH   = "cloudlet_base_disk_hash"
    IMAGE_TYPE_BASE_MEM_HASH    = "cloudlet_base_memory_hash"
    IMAGE_TYPE_OVERLAY          = "cloudlet_overlay"


def get_cloudlet_type(instance):
    import glanceclient.exc as glance_exceptions
    from openstack_dashboard.api import glance
    request = instance.request
    image_id = instance.image['id']
    metadata = instance.metadata
    try:
        image = glance.image_get(request, image_id)
        if hasattr(image, 'properties') != True:
            return None
        properties = getattr(image, 'properties')
        if properties == None or \
                properties.get(CLOUDLET_TYPE.PROPERTY_KEY_CLOUDLET) == None:
            return None

        # now it's either resumed base instance or synthesized instance
        # synthesized instance has meta that for overlay URL
        if (metadata.get('overlay_url') is not None) or\
                (metadata.get('handoff_info') is not None):
            return CLOUDLET_TYPE.IMAGE_TYPE_OVERLAY
        else:
            return CLOUDLET_TYPE.IMAGE_TYPE_BASE_DISK
    except glance_exceptions.ClientException:
        return None


def find_basevm_by_sha256(request, sha256_value):
    from openstack_dashboard.api import glance

    public = {"is_public": True, "status": "active"}
    image_detail = glance.image_list_detailed(request, filters=public)
    if len(image_detail) == 2:  # icehouse
        public_images, _more_images = image_detail
    elif len(image_detail) == 3: # kilo
        public_images, _more_images, has_prev_data = image_detail
    for image in public_images:
        properties = getattr(image, "properties")
        if properties == None or len(properties) == 0:
            continue
        if properties.get(CLOUDLET_TYPE.PROPERTY_KEY_CLOUDLET_TYPE) != \
                CLOUDLET_TYPE.IMAGE_TYPE_BASE_DISK:
            continue
        base_sha256_uuid = properties.get(CLOUDLET_TYPE.PROPERTY_KEY_BASE_UUID)
        if base_sha256_uuid == sha256_value:
            return image
    return None


def find_matching_flavor(flavor_list, cpu_count, memory_mb, disk_gb):
    ret = set()
    for flavor in flavor_list:
        vcpu = int(flavor.vcpus)
        ram_mb = int(flavor.ram)
        block_gb = int(flavor.disk)
        flavor_name = flavor.name
        if vcpu == cpu_count and ram_mb == memory_mb and disk_gb == block_gb:
            flavor_ref = flavor.links[0]['href']
            flavor_id = flavor.id
            ret.add((flavor_id, "%s" % flavor_name))
    return ret


def get_resource_size(libvirt_xml_str):
    libvirt_xml = ElementTree.fromstring(libvirt_xml_str)
    memory_element = libvirt_xml.find("memory")
    cpu_element = libvirt_xml.find("vcpu")
    if memory_element == None or cpu_element == None:
        msg = "Cannot find memory size or CPU number of Base VM"
        raise CloudletUtilError(msg)
    memory_size = int(memory_element.text)
    memory_unit = memory_element.get("unit").lower()

    if memory_unit != 'mib' and memory_unit != 'mb' and memory_unit != "m":
        if memory_unit == 'kib' or memory_unit == 'kb' or memory_unit == 'k':
            memory_size = memory_size / 1024
        elif memory_unit == 'gib' or memory_unit == 'gg' or memory_unit == 'g':
            memory_size = memory_size * 1024
    cpu_count = cpu_element.text
    return int(cpu_count), int(memory_size)

