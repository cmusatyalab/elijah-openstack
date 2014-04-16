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

import webob

from nova.compute import API
from nova.compute.cloudlet_api import CloudletAPI as CloudletAPI
from nova import exception
from nova.api.openstack import extensions
from nova.api.openstack import wsgi
from nova.openstack.common import log as logging


LOG = logging.getLogger(__name__)


class Cloudlet(extensions.ExtensionDescriptor):
    """Cloudlet compute API support"""

    name = "Cloudlet"
    alias = "os-cloudlet-control"
    namespace = "http://elijah.cs.cmu.edu/compute/ext/cloudlet/api/v1.1"
    updated = "2013-05-27T00:00:00+00:00"

    def get_controller_extensions(self):
        controller = CloudletController()
        extension = extensions.ControllerExtension(self, 'servers', controller)
        return [extension]


class CloudletController(wsgi.Controller):
    def __init__(self, *args, **kwargs):
        super(CloudletController, self).__init__(*args, **kwargs)
        self.cloudlet_api = CloudletAPI()
        self.nova_api = API()

    def _get_instance(self, context, instance_uuid):
        try:
            return self.nova_api.get(context, instance_uuid)
        except exception.NotFound:
            msg = _("Instance not found")
            raise webob.exc.HTTPNotFound(explanation=msg)

    @wsgi.action('cloudlet-base')
    def _cloudlet_base_creation(self, req, id, body):
        """Generate cloudlet base VM
        """
        context = req.environ['nova.context']

        baseVM_name = ''
        if body['cloudlet-base'] and ('name' in body['cloudlet-base']):
            baseVM_name = body['cloudlet-base']['name']
        else:
            msg = _("Need to set base VM name")
            raise webob.exc.HTTPBadRequest(explanation=msg)

        LOG.debug(_("cloudlet Generate Base VM %r"), id)
        instance = self._get_instance(context, id)
        disk_meta, memory_meta = self.cloudlet_api.cloudlet_create_base(context, instance, baseVM_name)
        return {'base-disk': disk_meta, 'base-memory':memory_meta}

    @wsgi.action('cloudlet-overlay-start')
    def _cloudlet_overlay_start(self, req, id, body):
        """Resume Base VM to start customization
        overlay_start will follow regular instance creationg process.
        If the image has memory reference, then it automatically resume the base VM
        """
        # TODO:
        # We might need this api for gurantee matching VM configuration
        # between base VM and requested instance
        pass

    @wsgi.action('cloudlet-overlay-finish')
    def _cloudlet_overlay_finish(self, req, id, body):
        """Generate overlay VM from the requested instance
        """
        context = req.environ['nova.context']

        overlay_name = ''
        if 'overlay-name' in body['cloudlet-overlay-finish']:
            overlay_name= body['cloudlet-overlay-finish']['overlay-name']
        else:
            msg = _("Need overlay Name")
            raise webob.exc.HTTPNotFound(explanation=msg)

        LOG.debug(_("cloudlet Generate overlay VM finish %r"), id)
        instance = self._get_instance(context, id)
        overlay_id = self.cloudlet_api.cloudlet_create_overlay_finish(context, instance, overlay_name)
        return {'overlay-id': overlay_id}
