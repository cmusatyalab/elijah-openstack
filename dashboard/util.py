"""
Views for managing Images and Snapshots.
"""

import glanceclient.exc as glance_exceptions
from openstack_dashboard.api import glance
import logging

LOG = logging.getLogger(__name__)


# original is defined at cloudlet_api.py
class CLOUDLET_TYPE(object):
    IMAGE_TYPE_BASE_DISK        = "cloudlet_base_disk"
    IMAGE_TYPE_BASE_MEM         = "cloudlet_base_memory"
    IMAGE_TYPE_BASE_DISK_HASH   = "cloudlet_base_disk_hash"
    IMAGE_TYPE_BASE_MEM_HASH    = "cloudlet_base_memory_hash"
    IMAGE_TYPE_OVERLAY_META     = "cloudlet_overlay_meta"
    IMAGE_TYPE_OVERLAY_DATA     = "cloudlet_overlay_data"


def get_cloudlet_type(instance):
    request = instance.request
    image_id = instance.image['id']
    metadata = instance.metadata
    try:
        image = glance.image_get(request, image_id)
        if hasattr(image, 'properties') != True:
            return None
        properties = getattr(image, 'properties')
        if properties == None or properties.get('is_cloudlet') == None:
            return None

        # now it's either resumed base instance or synthesized instance
        # synthesized instance has meta that for overlay URL
        if metadata.get('overlay_meta_url') != None:
            return CLOUDLET_TYPE.IMAGE_TYPE_OVERLAY_META
        else:
            return CLOUDLET_TYPE.IMAGE_TYPE_BASE_DISK
    except glance_exceptions.ClientException:
        return None


