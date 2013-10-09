
from django.conf.urls.defaults import patterns, url

from .views import download_vm_overlay
from .views import IndexView, SynthesisInstanceView, ResumeInstanceView, ImportBaseView

INSTANCES = r'^(?P<instance_id>[^/]+)/%s$'
VIEW_MOD = 'openstack_dashboard.dashboards.project.instances.views'

urlpatterns = patterns('',
    url(r'^$', IndexView.as_view(), name='index'),
    url(r'^resume$', ResumeInstanceView.as_view(), name='resume'),
    url(r'^import$', ImportBaseView.as_view(), name='import'),
    url(r'^synthesis$', SynthesisInstanceView.as_view(), name='synthesis'),
    url(r'^download$', download_vm_overlay, name='download'),
)
