
import logging
import shutil
from django.conf import settings
from django.forms import ValidationError
from django.forms.widgets import HiddenInput
from django.utils.translation import ugettext_lazy as _
from horizon import exceptions
from horizon import forms
from horizon import messages

from .workflows import cloudlet_api

from cloudlet.package import PackagingUtil 
from cloudlet.package import BaseVMPackage
import zipfile
from openstack_dashboard import api
from tempfile import mkdtemp
from lxml import etree
import os
from util import CLOUDLET_TYPE
from util import find_basevm_by_sha256


LOG = logging.getLogger(__name__)


class ImportImageForm(forms.SelfHandlingForm):
    name = forms.CharField(max_length="255", label=_("Name"), required=True)
    '''
    copy_from = forms.CharField(max_length="1024",
                                label=_("Image Location"),
                                help_text=_("An external (HTTP) URL to load "
                                            "the image from."),
                                widget=forms.TextInput(attrs={
                                    'placeholder': 
                                    'http://example.com/download/ubuntu.img'
                                    }),
                                required=False)
    '''
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

        try:
            disk_param = _create_param(disk_path, basevm_name + "-disk", 
                    CLOUDLET_TYPE.IMAGE_TYPE_BASE_DISK) 
            memory_param = _create_param(memory_path, basevm_name + "-memory", 
                    CLOUDLET_TYPE.IMAGE_TYPE_BASE_MEM) 
            diskhash_param = _create_param(diskhash_path, basevm_name + "-diskhash", 
                    CLOUDLET_TYPE.IMAGE_TYPE_BASE_DISK_HASH) 
            memoryhash_param = _create_param(memoryhash_path, basevm_name + "-memhash", 
                    CLOUDLET_TYPE.IMAGE_TYPE_BASE_MEM_HASH) 

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

