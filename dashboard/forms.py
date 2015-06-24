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
import os
import math
import zipfile
import logging
import shutil
import httplib
import json

from openstack_dashboard import api
from tempfile import mkdtemp
from lxml import etree
from .util import CLOUDLET_TYPE
from .util import find_basevm_by_sha256
from .util import find_matching_flavor
from .util import get_resource_size

from django.conf import settings
from django.forms import ValidationError
from django.forms.widgets import HiddenInput
from django.utils.translation import ugettext_lazy as _
from django.core.files.uploadedfile import TemporaryUploadedFile
from django.views.decorators.debug import sensitive_variables  # noqa
from horizon import exceptions
from horizon import forms
from horizon import messages
from . import cloudlet_api

from elijah.provisioning.package import PackagingUtil
from elijah.provisioning.package import BaseVMPackage
import elijah.provisioning.memory_util as elijah_memory_util

LOG = logging.getLogger(__name__)


class ImportImageForm(forms.SelfHandlingForm):
    name = forms.CharField(max_length="255", label=_("Name"), required=True)
    image_file = forms.FileField(label=_("Image File"),
                                 help_text=("A local image to upload."),
                                 required=False)
    is_public = forms.BooleanField(label=_("Public"), required=False,
                                   initial=True)

    def __init__(self, *args, **kwargs):
        super(ImportImageForm, self).__init__(*args, **kwargs)
        if not settings.HORIZON_IMAGES_ALLOW_UPLOAD:
            self.fields['image_file'].widget = HiddenInput()

    def clean(self):
        data = super(ImportImageForm, self).clean()
        # check validity of zip file
        zipbase = None
        try:
            zipbase = zipfile.ZipFile(data['image_file'])
            if BaseVMPackage.MANIFEST_FILENAME not in zipbase.namelist():
                msg = _('File is not valid (No manifest file)')
                raise ValidationError(msg)
            xml = zipbase.read(BaseVMPackage.MANIFEST_FILENAME)
            tree = etree.fromstring(xml, etree.XMLParser(schema=BaseVMPackage.schema))
        except Exception as e:
            msg = 'File is not valid (Not a zipped base VM)'
            raise ValidationError(_(msg))

        # Create attributes
        base_hashvalue = tree.get('hash_value')
        matching_base = find_basevm_by_sha256(self.request, base_hashvalue)
        if matching_base is not None:
            msg = "Base VM exists : UUID(%s)" % matching_base.id
            raise ValidationError(_(msg))

        disk_name = tree.find(BaseVMPackage.NSP + 'disk').get('path')
        memory_name = tree.find(BaseVMPackage.NSP + 'memory').get('path')
        diskhash_name = tree.find(BaseVMPackage.NSP + 'disk_hash').get('path')
        memoryhash_name = tree.find(BaseVMPackage.NSP + 'memory_hash').get('path')

        temp_dir = mkdtemp(prefix="cloudlet-base-")
        LOG.info("Decompressing zipfile to temp dir(%s)\n" % (temp_dir))
        zipbase.extractall(temp_dir)
        disk_path = os.path.join(temp_dir, disk_name)
        memory_path = os.path.join(temp_dir, memory_name)
        diskhash_path = os.path.join(temp_dir, diskhash_name)
        memoryhash_path = os.path.join(temp_dir, memoryhash_name)

        data['base_hashvalue'] = base_hashvalue
        data['base_disk_path'] = disk_path
        data['base_memory_path'] = memory_path
        data['base_diskhash_path'] = diskhash_path
        data['base_memoryhash_path'] = memoryhash_path
        return data

    def handle(self, request, data):
        basevm_name = data['name']
        base_hashvalue = data['base_hashvalue']
        disk_path = data['base_disk_path']
        memory_path = data['base_memory_path']
        diskhash_path = data['base_diskhash_path']
        memoryhash_path = data['base_memoryhash_path']

        # upload base disk
        def _create_param(filepath, image_name, image_type,
                          disk_size, mem_size):
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
                "min_disk": disk_size,
                "min_ram": mem_size,
                "properties": properties,
            }
            return param

        try:
            # create new flavor if nothing matches
            memory_header = elijah_memory_util._QemuMemoryHeader(
                open(memory_path))
            libvirt_xml_str = memory_header.xml
            cpu_count, memory_size_mb = get_resource_size(libvirt_xml_str)
            disk_gb = int(math.ceil(os.path.getsize(disk_path)/1024/1024/1024))
            flavors = api.nova.flavor_list(request)
            ref_flavors = find_matching_flavor(flavors,
                                               cpu_count,
                                               memory_size_mb,
                                               disk_gb)
            if len(ref_flavors) == 0:
                flavor_name = "cloudlet-flavor-%s" % basevm_name
                flavor_ref = api.nova.flavor_create(self.request, flavor_name,
                                                    memory_size_mb, cpu_count,
                                                    disk_gb, is_public=True)
                msg = "Create new flavor %s with (cpu:%d, memory:%d, disk:%d)" %\
                    (flavor_name, cpu_count, memory_size_mb, disk_gb)
                LOG.info(msg)
            # upload Base VM
            disk_param = _create_param(
                disk_path, basevm_name + "-disk",
                CLOUDLET_TYPE.IMAGE_TYPE_BASE_DISK,
                disk_gb, memory_size_mb)
            memory_param = _create_param(
                memory_path, basevm_name + "-memory",
                CLOUDLET_TYPE.IMAGE_TYPE_BASE_MEM,
                disk_gb, memory_size_mb)
            diskhash_param = _create_param(
                diskhash_path, basevm_name + "-diskhash",
                CLOUDLET_TYPE.IMAGE_TYPE_BASE_DISK_HASH,
                disk_gb, memory_size_mb)
            memoryhash_param = _create_param(
                memoryhash_path, basevm_name + "-memhash",
                CLOUDLET_TYPE.IMAGE_TYPE_BASE_MEM_HASH,
                disk_gb, memory_size_mb)

            LOG.info("upload base memory to glance")
            glance_memory = api.glance.image_create(request, **memory_param)
            LOG.info("upload base disk hash to glance")
            glance_diskhash = api.glance.image_create(request, **diskhash_param)
            LOG.info("upload base memory hash to glance")
            glance_memoryhash = api.glance.image_create(request, **memoryhash_param)

            glance_ref = {
                CLOUDLET_TYPE.IMAGE_TYPE_BASE_MEM: glance_memory.id,
                CLOUDLET_TYPE.IMAGE_TYPE_BASE_DISK_HASH: glance_diskhash.id,
                CLOUDLET_TYPE.IMAGE_TYPE_BASE_MEM_HASH: glance_memoryhash.id,
                CLOUDLET_TYPE.PROPERTY_KEY_BASE_RESOURCE:\
                libvirt_xml_str.replace("\n", "")  # API cannot send '\n'
            }
            disk_param['properties'].update(glance_ref)
            LOG.info("upload base disk to glance")
            glance_memory = api.glance.image_create(request, **disk_param)

            LOG.info("SUCCESS")
            msg = "Your image %s has been queued for creation." % basevm_name
            messages.success(request, _(msg))
        except:
            exceptions.handle(request, _('Unable to import image.'))

        dirpath = os.path.dirname(disk_path)
        if os.path.exists(dirpath) == True:
            shutil.rmtree(dirpath)
        return True


class HandoffInstanceForm(forms.SelfHandlingForm):
    dest_addr = forms.CharField(max_length=255, required=True,
                                initial="mist.elijah.cs.cmu.edu:5000",
                                label=_("Keystone endpoint for destination OpenStack"))
    dest_account = forms.CharField(max_length=255, required=True,
                                   label=_("Destination Account"),
                                   initial="admin")
    dest_password = forms.CharField(widget=forms.PasswordInput(), required=True,
                                    initial="",
                                    label=_("Destination Password"))
    dest_tenant = forms.CharField(max_length=255, required=True,
                                  label=_("Destination Tenant"),
                                  initial="demo")
    dest_vmname = forms.CharField(max_length=255,
                           label=_("Instance Name at the destination"),
                           initial="handoff-vm")

    def __init__(self, request, *args, **kwargs):
        super(HandoffInstanceForm, self).__init__(request, *args, **kwargs)
        self.instance_id = kwargs.get('initial', {}).get('instance_id')

    @staticmethod
    def _get_token(dest_addr, user, password, tenant_name):
        if dest_addr.endswith("/"):
            dest_addr = dest_addr[-1:]
        params = {
            "auth": {
                "passwordCredentials": {
                    "username": user, "password": password
                },
                "tenantName": tenant_name
            }
        }
        headers = {"Content-Type": "application/json"}

        # HTTP connection
        conn = httplib.HTTPConnection(dest_addr)
        conn.request("POST", "/v2.0/tokens", json.dumps(params), headers)

        # HTTP response
        response = conn.getresponse()
        data = response.read()
        dd = json.loads(data)
        conn.close()
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
            raise
        return api_token, nova_endpoint, glance_endpoint

    def clean(self):
        cleaned_data = super(HandoffInstanceForm, self).clean()
        dest_addr = cleaned_data.get('dest_addr', None)
        dest_account = cleaned_data.get('dest_account', None)
        dest_password = cleaned_data.get('dest_password', None)
        dest_tenant = cleaned_data.get('dest_tenant', None)

        # check fields
        if cleaned_data.get('dest_vmname', None) is None:
            raise forms.ValidationError(_("Need name for VM at the destination"))
        if dest_addr is None:
            raise forms.ValidationError(_("Need URL to fetch VM overlay"))

        # get token of the destination
        try:
            dest_token, dest_nova_endpoint, dest_glance_endpoint = \
                self._get_token(dest_addr, dest_account,
                                dest_password, dest_tenant)
            cleaned_data['dest_token'] = dest_token
            cleaned_data['dest_nova_endpoint'] = dest_nova_endpoint
            cleaned_data['dest_glance_endpoint'] = dest_glance_endpoint
            cleaned_data['instance_id'] = self.instance_id
        except Exception as e:
            msg = "Cannot get Auth-token from %s" % (dest_addr)
            raise forms.ValidationError(_(msg))
        return cleaned_data

    def get_help_text(self):
        return super(HandoffInstanceForm, self).get_help_text()

    def handle(self, request, context):
        try:
            ret_json = cloudlet_api.request_handoff(
                request,
                context['instance_id'],
                context['dest_nova_endpoint'],
                context['dest_token'],
                context['dest_vmname']
            )
            import pdb;pdb.set_trace()
            error_msg = ret_json.get("badRequest", None)
            if error_msg is not None:
                msg = error_msg.get("message", "Failed to request VM synthesis")
                raise Exception(msg)
            return True
        except:
            exceptions.handle(request)
            return False


