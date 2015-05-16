# Copyright (C) 2011-2013 Carnegie Mellon University
# Author: Kiryong Ha (krha@cmu.edu)
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of version 2 of the GNU General Public License as published
# by the Free Software Foundation.  A copy of the GNU General Public License
# should have been distributed along with this program in the file
# LICENSE.GPL.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
# or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License
# for more details.
#

import webob

from nova.compute import API
from nova.compute import HostAPI
from nova.compute.cloudlet_api import CloudletAPI as CloudletAPI
from nova import exception
from nova.api.openstack import extensions
from nova.api.openstack import wsgi
from nova.openstack.common import log as logging
from nova.openstack.common.gettextutils import _



LOG = logging.getLogger(__name__)
authorize = extensions.extension_authorizer('compute', 'cloudlet')


class Cloudlet(extensions.ExtensionDescriptor):
    """Cloudlet compute API support"""

    name = "Cloudlet"
    alias = "os-cloudlet"
    namespace = "http://elijah.cs.cmu.edu/compute/ext/cloudlet/api/v1.1"
    updated = "2014-05-27T00:00:00+00:00"

    def get_controller_extensions(self):
        controller = CloudletController()
        extension = extensions.ControllerExtension(self, 'servers', controller)
        return [extension]

    def get_resources(self):
        resources = [extensions.ResourceExtension('os-cloudlet',
                CloudletDiscoveryController(),
                collection_actions={'status': 'GET'},
                member_actions={})]

        return resources


class CloudletDiscoveryController(object):
    """The Cloudlet Discovery API controller for the OpenStack API."""
    def __init__(self):
        self.host_api = HostAPI()
        self.cloudlet_api = CloudletAPI()
        super(CloudletDiscoveryController, self).__init__()

    def status(self, req):
        context = req.environ['nova.context']
        authorize(context)
        app_request=None
        stats = self.cloudlet_api.cloudlet_get_status(context, app_request)
        return {'cloudlet-status':stats}


class CloudletController(wsgi.Controller):
    def __init__(self, *args, **kwargs):
        super(CloudletController, self).__init__(*args, **kwargs)
        self.cloudlet_api = CloudletAPI()
        self.host_api = HostAPI()
        self.compute_api = API()

    def _get_instance(self, context, instance_id, want_objects=False):
        try:
            return self.compute_api.get(context, instance_id,
                                        want_objects=want_objects)
        except exception.InstanceNotFound:
            msg = _("Server not found")
            raise exc.HTTPNotFound(explanation=msg)

    @wsgi.action('cloudlet-base')
    def cloudlet_base_creation(self, req, id, body):
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
        instance = self._get_instance(context, id, want_objects=True)
        disk_meta, memory_meta = self.cloudlet_api.cloudlet_create_base(context,
                                                                        instance,
                                                                        baseVM_name)
        return {'base-disk': disk_meta, 'base-memory':memory_meta}

    @wsgi.action('cloudlet-overlay-start')
    def cloudlet_overlay_start(self, req, id, body):
        """Resume Base VM to start customization
        overlay_start will follow regular instance creationg process.
        If the image has memory reference, then it automatically resume the base VM
        """
        # currently we're using a openstack mechanism of starting new VM to
        # resume the Base VM. However, We might need this api for guarantee
        # matching VM configuration between base VM and requested instance
        pass

    @wsgi.action('cloudlet-overlay-finish')
    def cloudlet_overlay_finish(self, req, id, body):
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
        instance = self._get_instance(context, id, want_objects=True)
        overlay_id = self.cloudlet_api.cloudlet_create_overlay_finish(context,
                                                                      instance,
                                                                      overlay_name)
        return {'overlay-id': overlay_id}

    @wsgi.action('cloudlet-handoff')
    def cloudlet_handoff(self, req, id, body):
        """Perform VM migration acorss OpenStack
        """
        context = req.environ['nova.context']
        payload = body['cloudlet-handoff']
        handoff_type = payload.get("type", None)
        dest_vm_name = payload.get("handoff_vm_name", None)
        if handoff_type == None:
            msg = _("Specify Handoff type")
            raise webob.exc.HTTPBadRequest(explanation=msg)
        if dest_vm_name == None:
            msg = _("Need VM name at handoff dest")
            raise webob.exc.HTTPBadRequest(explanation=msg)
        LOG.debug(_("cloudlet handoff %r (type:%s, name:%s)"),
                  id, handoff_type, dest_vm_name)
        instance = self._get_instance(context, id, want_objects=True)
        residue_id = self.cloudlet_api.cloudlet_handoff(context, instance,
                                                        handoff_type,
                                                        dest_vm_name)
        return {'overlay': "success"}
