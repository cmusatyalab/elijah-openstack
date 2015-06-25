# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2012 United States Government as represented by the
# Administrator of the National Aeronautics and Space Administration.
# All Rights Reserved.
#
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

"""
Views for managing images.
"""

import logging

from django.conf import settings
from django.forms import ValidationError
from django.forms.widgets import HiddenInput
from django.utils.translation import ugettext_lazy as _

from horizon import exceptions
from horizon import forms
from horizon import messages

from openstack_dashboard import api


LOG = logging.getLogger(__name__)


class CreateImageForm(forms.SelfHandlingForm):
    name = forms.CharField(max_length="255", label=_("Name"), required=True)
    image_url = forms.CharField(max_length=255, required=True,
                                label=_("URL for Base VM"),
                                help_text=("Import Base VM from the URL"),
                                initial="https://storage.cmusatyalab.org/cloudlet-vm/precise-baseVM.zip")
    disk_format = forms.ChoiceField(label=_('Format'),
                                    required=True,
                                    choices=[('', ''),
                                             ('aki',
                                                _('AKI - Amazon Kernel '
                                                        'Image')),
                                             ('ami',
                                                _('AMI - Amazon Machine '
                                                        'Image')),
                                             ('ari',
                                                _('ARI - Amazon Ramdisk '
                                                        'Image')),
                                             ('iso',
                                                _('ISO - Optical Disk Image')),
                                             ('qcow2',
                                                _('QCOW2 - QEMU Emulator')),
                                             ('raw', 'Raw'),
                                             ('vdi', 'VDI'),
                                             ('vhd', 'VHD'),
                                             ('vmdk', 'VMDK')],
                                    widget=forms.Select(attrs={'class':
                                                               'switchable'}))
    minimum_disk = forms.IntegerField(label=_("Minimum Disk (GB)"),
                                    help_text=_('The minimum disk size'
                                            ' required to boot the'
                                            ' image. If unspecified, this'
                                            ' value defaults to 0'
                                            ' (no minimum).'),
                                    required=False)
    minimum_ram = forms.IntegerField(label=_("Minimum Ram (MB)"),
                                    help_text=_('The minimum disk size'
                                            ' required to boot the'
                                            ' image. If unspecified, this'
                                            ' value defaults to 0 (no'
                                            ' minimum).'),
                                    required=False)
    is_public = forms.BooleanField(label=_("Public"), required=False)

    def __init__(self, *args, **kwargs):
        super(CreateImageForm, self).__init__(*args, **kwargs)

    def clean(self):
        data = super(CreateImageForm, self).clean()
        if not data['image_url']:
            raise ValidationError(
                _("A image or external image location must be specified."))
        else:
            return data

    def handle(self, request, data):
        # Glance does not really do anything with container_format at the
        # moment. It requires it is set to the same disk_format for the three
        # Amazon image types, otherwise it just treats them as 'bare.' As such
        # we will just set that to be that here instead of bothering the user
        # with asking them for information we can already determine.
        if data['disk_format'] in ('ami', 'aki', 'ari',):
            container_format = data['disk_format']
        else:
            container_format = 'bare'

        meta = {'is_public': data['is_public'],
                'disk_format': data['disk_format'],
                'container_format': container_format,
                'min_disk': (data['minimum_disk'] or 0),
                'min_ram': (data['minimum_ram'] or 0),
                'name': data['name']}

        meta['location'] = data['image_url']

        try:
            image = api.glance.image_create(request, **meta)
            messages.success(request,
                _('Your image %s has been queued for creation.' %
                    data['name']))
            return image
        except:
            exceptions.handle(request, _('Unable to create new image.'))


