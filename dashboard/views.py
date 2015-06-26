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

from django.core.urlresolvers import reverse, reverse_lazy
from django.http import HttpResponse
from django import shortcuts
from horizon import messages
from django.utils.translation import ugettext_lazy as _

from horizon import exceptions
from horizon import tables
from horizon import tabs

from openstack_dashboard import api
from openstack_dashboard.api.base import is_service_enabled
from django.utils.datastructures import SortedDict
from .images.tables import BaseVMsTable
from .images.tables import VMOverlaysTable
from .instances.tables import InstancesTable
from .volume_snapshots.tables import VolumeSnapshotsTable
from .volume_snapshots.tabs import SnapshotDetailTabs

from horizon import workflows
from .workflows import SynthesisInstance
from .workflows import ResumeInstance

from util import CLOUDLET_TYPE
from util import get_cloudlet_type

from horizon import forms
from .forms import ImportImageForm
from .forms import HandoffInstanceForm


LOG = logging.getLogger(__name__)


class IndexView(tables.MultiTableView):
    table_classes = (BaseVMsTable, VMOverlaysTable, InstancesTable, VolumeSnapshotsTable)
    template_name = 'project/cloudlet/index.html'

    def has_prev_data(self, table):
        return getattr(self, "_prev_%s" % table.name, False)

    def has_more_data(self, table):
        return getattr(self, "_more_%s" % table.name, False)

    def get_images_data(self):
        marker = self.request.GET.get(BaseVMsTable._meta.pagination_param, None)
        try:
            image_detail = api.glance.image_list_detailed(self.request)
            if len(image_detail) == 2:  # icehouse
                all_images, _more_images = image_detail
            elif len(image_detail) == 3: # kilo
                all_images, _more_images, has_prev_data = image_detail
            images = [im for im in all_images
                      if im.properties.get("cloudlet_type", None) == \
                              CLOUDLET_TYPE.IMAGE_TYPE_BASE_DISK]
        except:
            images = []
            exceptions.handle(self.request, _("Unable to retrieve images."))
        return images

    def get_overlays_data(self):
        req = self.request
        marker = req.GET.get(VMOverlaysTable._meta.pagination_param, None)
        try:
            image_detail = api.glance.image_list_detailed(self.request)
            if len(image_detail) == 2:  # icehouse
                all_snaps, _more_images = image_detail
            elif len(image_detail) == 3: # kilo
                all_snaps, _more_images, has_prev_data = image_detail
            snaps = [im for im in all_snaps\
                      if (im.properties.get("cloudlet_type", None) == CLOUDLET_TYPE.IMAGE_TYPE_OVERLAY)
                              and (im.owner == req.user.tenant_id)]
        except:
            snaps = []
            exceptions.handle(req, _("Unable to retrieve snapshots."))
        return snaps

    def get_instances_data(self):

        # Gather synthesized instances
        try:
            (instances, self._more_instances) = api.nova.server_list(self.request)
        except:
            instances = []
            exceptions.handle(self.request,
                              _('Unable to retrieve instances.'))

        # Gather our flavors and correlate our instances to them
        filtered_instances = list()
        if instances:
            try:
                flavors = api.nova.flavor_list(self.request)
            except:
                flavors = []
                exceptions.handle(self.request, ignore=True)

            full_flavors = SortedDict([(str(flavor.id), flavor)
                                        for flavor in flavors])
            # Loop through instances to get flavor info.
            for instance in instances:
                try:
                    flavor_id = instance.flavor["id"]
                    if flavor_id in full_flavors:
                        instance.full_flavor = full_flavors[flavor_id]
                    else:
                        # If the flavor_id is not in full_flavors list,
                        # get it via nova api.
                        instance.full_flavor = api.nova.flavor_get(
                            self.request, flavor_id)
                except:
                    msg = _('Unable to retrieve instance size information.')
                    exceptions.handle(self.request, msg)

            for instance in instances:
                instance_type = get_cloudlet_type(instance)
                if instance_type == CLOUDLET_TYPE.IMAGE_TYPE_BASE_DISK:
                    filtered_instances.append(instance)
                    setattr(instance, 'cloudlet_type', "Resumed Base VM")
                if instance_type == CLOUDLET_TYPE.IMAGE_TYPE_OVERLAY:
                    filtered_instances.append(instance)
                    setattr(instance, 'cloudlet_type', "Provisioned VM")

        return filtered_instances

    def get_volume_snapshots_data(self):
        if is_service_enabled(self.request, 'volume'):
            try:
                snapshots = api.cinder.volume_snapshot_list(self.request)
            except:
                snapshots = []
                exceptions.handle(self.request, _("Unable to retrieve "
                                                  "volume snapshots."))
        else:
            snapshots = []
        return snapshots


class ImportBaseView(forms.ModalFormView):
    form_class = ImportImageForm
    template_name = 'project/cloudlet/images/import.html'
    context_object_name = 'image'
    success_url = reverse_lazy("horizon:project:cloudlet:index")


class ResumeInstanceView(workflows.WorkflowView):
    workflow_class = ResumeInstance
    template_name = "project/cloudlet/instance/resume.html"

    def get_initial(self):
        initial = super(ResumeInstanceView, self).get_initial()
        initial['project_id'] = self.request.user.tenant_id
        initial['user_id'] = self.request.user.id
        return initial


class SynthesisInstanceView(workflows.WorkflowView):
    workflow_class = SynthesisInstance
    template_name = "project/cloudlet/instance/launch.html"

    def get_initial(self):
        initial = super(SynthesisInstanceView, self).get_initial()
        initial['project_id'] = self.request.user.tenant_id
        initial['user_id'] = self.request.user.id
        return initial


class HandoffInstanceView(forms.ModalFormView):
    form_class = HandoffInstanceForm
    template_name = 'project/cloudlet/instance/handoff.html'
    success_url = reverse_lazy("horizon:project:cloudlet:index")
    page_title = _("Handoff Instance")

    def get_context_data(self, **kwargs):
        context = super(HandoffInstanceView, self).get_context_data(**kwargs)
        context['instance_id'] = self.kwargs['instance_id']
        context['can_set_server_password'] = api.nova.can_set_server_password()
        return context

    def get_initial(self):
        return {'instance_id': self.kwargs['instance_id']}


def download_vm_overlay(request):
    try:
        image_id = request.GET.get("image_id", None)
        image_name = request.GET.get("image_name", None)
        if image_id is None:
            raise
        client = api.glance.glanceclient(request)

        body = client.images.data(image_id)
        response = HttpResponse(body, content_type="application/octet-stream")
        #response["Content-Length"] = "%d" % item.size_total
        response['Content-Disposition'] = 'attachment; filename="%s"' % image_name
        return response
    except Exception, e:
        LOG.exception("Exception in Downloading.")
        messages.error(request, _('Error Downloading VM overlay: %s') % e)
        return shortcuts.redirect(request.build_absolute_uri())
