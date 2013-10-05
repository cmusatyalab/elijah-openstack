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


