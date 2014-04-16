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

LOG = logging.getLogger(__name__)


# original is defined at cloudlet_api.py
class CLOUDLET_TYPE(object):
    PROPERTY_KEY_CLOUDLET       = "is_cloudlet"
    PROPERTY_KEY_CLOUDLET_TYPE  = "cloudlet_type"
    PROPERTY_KEY_NETWORK_INFO   = "network"
    PROPERTY_KEY_BASE_UUID      = "base_sha256_uuid"

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
        if metadata.get('overlay_url') != None:
            return CLOUDLET_TYPE.IMAGE_TYPE_OVERLAY
        else:
            return CLOUDLET_TYPE.IMAGE_TYPE_BASE_DISK
    except glance_exceptions.ClientException:
        return None


def find_basevm_by_sha256(request, sha256_value):
    from openstack_dashboard.api import glance

    public = {"is_public": True, "status": "active"}
    public_images, _more = glance.image_list_detailed(request, filters=public)
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
