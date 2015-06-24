# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2012 Nebula, Inc.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import logging

from django import shortcuts
from django import template
from django.core import urlresolvers
from django.template.defaultfilters import title
from django.utils.http import urlencode
from django.utils.translation import string_concat, ugettext_lazy as _

from horizon.conf import HORIZON_CONFIG
from horizon import exceptions
from horizon import messages
from horizon import tables
from horizon.templatetags import sizeformat
from horizon.utils.filters import replace_underscores

from openstack_dashboard import api
from openstack_dashboard.dashboards.project.access_and_security \
        .floating_ips.workflows import IPAssociationWorkflow
from .tabs import InstanceDetailTabs, LogTab, ConsoleTab
from openstack_dashboard import policy
from openstack_dashboard.dashboards.project.instances.workflows \
    import update_instance

from ..util import get_cloudlet_type
from ..util import CLOUDLET_TYPE
from .. import cloudlet_api


LOG = logging.getLogger(__name__)

ACTIVE_STATES = ("ACTIVE",)

POWER_STATES = {
    0: "NO STATE",
    1: "RUNNING",
    2: "BLOCKED",
    3: "PAUSED",
    4: "SHUTDOWN",
    5: "SHUTOFF",
    6: "CRASHED",
    7: "SUSPENDED",
    8: "FAILED",
    9: "BUILDING",
}

PAUSE = 0
UNPAUSE = 1
SUSPEND = 0
RESUME = 1


def is_deleting(instance):
    task_state = getattr(instance, "OS-EXT-STS:task_state", None)
    if not task_state:
        return False
    return task_state.lower() == "deleting"


class TerminateInstance(tables.BatchAction):
    name = "terminate"
    action_present = _("Terminate")
    action_past = _("Scheduled termination of")
    data_type_singular = _("Instance")
    data_type_plural = _("Instances")
    classes = ('btn-danger', 'btn-terminate')

    def allowed(self, request, instance=None):
        #is_resumed_base = False
        #cloudlet_type = get_cloudlet_type(instance)
        #if cloudlet_type == CLOUDLET_TYPE.IMAGE_TYPE_BASE_DISK:
        #    is_resumed_base = True
        #return (not is_resumed_base)
        return True


    def action(self, request, obj_id):
        api.nova.server_delete(request, obj_id)


class CreateOverlayAction(tables.BatchAction):
    name = "overlay"
    action_present = _("Create")
    action_past = _("Scheduled VM overlay creation of")
    data_type_singular = _("VM overlay")
    data_type_plural = _("VM overlays")
    classes = ('btn-danger', 'btn-terminate')

    def allowed(self, request, instance=None):
        is_active = instance.status in ACTIVE_STATES
        is_resumed_base = False
        cloudlet_type = get_cloudlet_type(instance)
        if cloudlet_type == CLOUDLET_TYPE.IMAGE_TYPE_BASE_DISK:
            is_resumed_base = True

        return is_active and is_resumed_base

    def action(self, request, obj_id):
        ret_dict = cloudlet_api.request_create_overlay(request, obj_id)


class VMSynthesisLink(tables.LinkAction):
    name = "synthesis"
    verbose_name = _("Start VM Synthesis")
    url = "horizon:project:cloudlet:synthesis"
    classes = ("btn-launch", "ajax-modal")

    def allowed(self, request, datum):
        try:
            limits = api.nova.tenant_absolute_limits(request, reserved=True)

            instances_available = limits['maxTotalInstances'] \
                - limits['totalInstancesUsed']
            cores_available = limits['maxTotalCores'] \
                - limits['totalCoresUsed']
            ram_available = limits['maxTotalRAMSize'] - limits['totalRAMUsed']

            if instances_available <= 0 or cores_available <= 0 \
                    or ram_available <= 0:
                if "disabled" not in self.classes:
                    self.classes = [c for c in self.classes] + ['disabled']
                    self.verbose_name = string_concat(self.verbose_name, ' ',
                                                      _("(Quota exceeded)"))
            else:
                self.verbose_name = _("Start VM Synthesis")
                classes = [c for c in self.classes if c != "disabled"]
                self.classes = classes
        except:
            LOG.exception("Failed to retrieve quota information")
            # If we can't get the quota information, leave it to the
            # API to check when launching

        return True  # The action should always be displayed


class EditInstance(policy.PolicyTargetMixin, tables.LinkAction):
    name = "edit"
    verbose_name = _("Edit Instance")
    url = "horizon:project:instances:update"
    classes = ("ajax-modal",)
    icon = "pencil"
    policy_rules = (("compute", "compute:update"),)

    def get_link_url(self, project):
        return self._get_link_url(project, 'instance_info')

    def _get_link_url(self, project, step_slug):
        base_url = urlresolvers.reverse(self.url, args=[project.id])
        next_url = self.table.get_full_url()
        params = {"step": step_slug,
                  update_instance.UpdateInstance.redirect_param_name: next_url}
        param = urlencode(params)
        return "?".join([base_url, param])

    def allowed(self, request, instance):
        return not is_deleting(instance)


class VMHandoffLink(tables.LinkAction):
    name = "handoff"
    verbose_name = _("VM Handoff")
    url = "horizon:project:cloudlet:handoff"
    classes = ("btn-handoff", "ajax-modal",)
    icon = "pencil"

    def get_link_url(self, datum):
        instance_id = self.table.get_object_id(datum)
        return urlresolvers.reverse(self.url, args=[instance_id])

    def allowed(self, request, instance):
        is_synthesized = False
        cloudlet_type = get_cloudlet_type(instance)
        if cloudlet_type == CLOUDLET_TYPE.IMAGE_TYPE_OVERLAY:
            is_synthesized = True
        return is_synthesized



class AssociateIP(tables.LinkAction):
    name = "associate"
    verbose_name = _("Associate Floating IP")
    url = "horizon:project:access_and_security:floating_ips:associate"
    classes = ("ajax-modal", "btn-associate")

    def allowed(self, request, instance):
        fip = api.network.NetworkClient(request).floating_ips
        if fip.is_simple_associate_supported():
            return False
        return not is_deleting(instance)

    def get_link_url(self, datum):
        base_url = urlresolvers.reverse(self.url)
        next = urlresolvers.reverse("horizon:project:instances:index")
        params = {"instance_id": self.table.get_object_id(datum),
                  IPAssociationWorkflow.redirect_param_name: next}
        params = urlencode(params)
        return "?".join([base_url, params])


class SimpleAssociateIP(tables.Action):
    name = "associate-simple"
    verbose_name = _("Associate Floating IP")
    classes = ("btn-associate-simple",)

    def allowed(self, request, instance):
        fip = api.network.NetworkClient(request).floating_ips
        if not fip.is_simple_associate_supported():
            return False
        return not is_deleting(instance)

    def single(self, table, request, instance):
        try:
            fip = api.network.tenant_floating_ip_allocate(request)
            api.network.floating_ip_associate(request, fip.id, instance)
            messages.success(request,
                             _("Successfully associated floating IP: %s")
                             % fip.ip)
        except:
            exceptions.handle(request,
                              _("Unable to associate floating IP."))
        return shortcuts.redirect("horizon:project:cloudlet:instances:index")


class SimpleDisassociateIP(tables.Action):
    name = "disassociate"
    verbose_name = _("Disassociate Floating IP")
    classes = ("btn-danger", "btn-disassociate",)

    def allowed(self, request, instance):
        if not HORIZON_CONFIG["simple_ip_management"]:
            return False
        return not is_deleting(instance)

    def single(self, table, request, instance_id):
        try:
            fips = [fip for fip in api.network.tenant_floating_ip_list(request)
                    if fip.port_id == instance_id]
            # Removing multiple floating IPs at once doesn't work, so this pops
            # off the first one.
            if fips:
                fip = fips.pop()
                api.network.floating_ip_disassociate(request,
                                                     fip.id, instance_id)
                api.network.tenant_floating_ip_release(request, fip.id)
                messages.success(request,
                                 _("Successfully disassociated "
                                   "floating IP: %s") % fip.ip)
            else:
                messages.info(request, _("No floating IPs to disassociate."))
        except:
            exceptions.handle(request,
                              _("Unable to disassociate floating IP."))
        return shortcuts.redirect("horizon:project:instances:index")


class UpdateRow(tables.Row):
    ajax = True

    def get_data(self, request, instance_id):
        instance = api.nova.server_get(request, instance_id)
        instance.full_flavor = api.nova.flavor_get(request,
                                                   instance.flavor["id"])
        return instance


def get_ips(instance):
    template_name = 'project/instances/_instance_ips.html'
    context = {"instance": instance}
    return template.loader.render_to_string(template_name, context)


def get_size(instance):
    if hasattr(instance, "full_flavor"):
        size_string = _("%(name)s | %(RAM)s RAM | %(VCPU)s VCPU "
                        "| %(disk)s Disk")
        vals = {'name': instance.full_flavor.name,
                'RAM': sizeformat.mbformat(instance.full_flavor.ram),
                'VCPU': instance.full_flavor.vcpus,
                'disk': sizeformat.diskgbformat(instance.full_flavor.disk)}
        return size_string % vals
    return _("Not available")


def get_keyname(instance):
    if hasattr(instance, "key_name"):
        keyname = instance.key_name
        return keyname
    return _("Not available")


def cloudlet_type(instance):
    if hasattr(instance, "cloudlet_type"):
        cloudlet_type = getattr(instance, "cloudlet_type")
        return cloudlet_type
    return _("Unknown type")


def get_power_state(instance):
    return POWER_STATES.get(getattr(instance, "OS-EXT-STS:power_state", 0), '')


STATUS_DISPLAY_CHOICES = (
    ("resize", "Resize/Migrate"),
    ("verify_resize", "Confirm or Revert Resize/Migrate"),
    ("revert_resize", "Revert Resize/Migrate"),
)


TASK_DISPLAY_CHOICES = (
    ("image_snapshot", "Snapshotting"),
    ("resize_prep", "Preparing Resize or Migrate"),
    ("resize_migrating", "Resizing or Migrating"),
    ("resize_migrated", "Resized or Migrated"),
    ("resize_finish", "Finishing Resize or Migrate"),
    ("resize_confirming", "Confirming Resize or Nigrate"),
    ("resize_reverting", "Reverting Resize or Migrate"),
    ("unpausing", "Resuming"),
)


class InstancesTable(tables.DataTable):
    TASK_STATUS_CHOICES = (
        (None, True),
        ("none", True)
    )
    STATUS_CHOICES = (
        ("active", True),
        ("shutoff", True),
        ("suspended", True),
        ("paused", True),
        ("error", False),
    )
    name = tables.Column("name",
                         link=("horizon:project:instances:detail"),
                         verbose_name=_("Instance Name"))
    cloudlet_type = tables.Column(cloudlet_type, verbose_name=_("Type"))
    ip = tables.Column(get_ips, verbose_name=_("IP Address"))
    size = tables.Column(get_size,
                         verbose_name=_("Size"),
                         attrs={'data-type': 'size'})
    #keypair = tables.Column(get_keyname, verbose_name=_("Keypair"))
    status = tables.Column("status",
                           filters=(title, replace_underscores),
                           verbose_name=_("Status"),
                           status=True,
                           status_choices=STATUS_CHOICES,
                           display_choices=STATUS_DISPLAY_CHOICES)
    task = tables.Column("OS-EXT-STS:task_state",
                         verbose_name=_("Task"),
                         filters=(title, replace_underscores),
                         status=True,
                         status_choices=TASK_STATUS_CHOICES,
                         display_choices=TASK_DISPLAY_CHOICES)
    state = tables.Column(get_power_state,
                          filters=(title, replace_underscores),
                          verbose_name=_("Power State"))

    class Meta:
        name = "instances"
        verbose_name = _("Instances")
        status_columns = ["status", "task"]
        row_class = UpdateRow
        table_actions = (VMSynthesisLink, )
        row_actions = (VMHandoffLink, CreateOverlayAction,
                       TerminateInstance, EditInstance)
                       #SimpleAssociateIP, AssociateIP,
                       #SimpleDisassociateIP, SimpleDisassociateIP)
