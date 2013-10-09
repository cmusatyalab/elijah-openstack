
import logging
from django.conf import settings
from django.forms import ValidationError
from django.forms.widgets import HiddenInput
from django.utils.translation import ugettext_lazy as _
from horizon import exceptions
from horizon import forms
from horizon import messages

from .workflows import cloudlet_api

LOG = logging.getLogger(__name__)


class ImportImageForm(forms.SelfHandlingForm):
    name = forms.CharField(max_length="255", label=_("Name"), required=True)
    copy_from = forms.CharField(max_length="1024",
                                label=_("Image Location"),
                                help_text=_("An external (HTTP) URL to load "
                                            "the image from."),
                                widget=forms.TextInput(attrs={
                                    'placeholder': 
                                    'http://example.com/download/ubuntu.img'
                                    }),
                                required=False)
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
        if not data['copy_from'] and not data['image_file']:
            raise ValidationError(
                _("A image or external image location must be specified."))
        elif data['copy_from'] and data['image_file']:
            raise ValidationError(
                _("Can not specify both image and external image location."))
        else:
            return data

    def handle(self, request, data):
        meta = {'is_public': data['is_public'],
                'disk_format': 'raw',
                'container_format': 'bare',
                'min_disk': (0),
                'min_ram': (0),
                'name': data['name']}

        if settings.HORIZON_IMAGES_ALLOW_UPLOAD and data['image_file']:
            meta['data'] = self.files['image_file']
        else:
            meta['copy_from'] = data['copy_from']

        try:
            image = cloudlet_api.request_import_basevm(request, **meta)
            messages.success(request,
                _('Your image %s has been queued for creation.' %
                    data['name']))
            return image
        except:
            exceptions.handle(request, _('Unable to create new image.'))
