
from django.conf.urls.defaults import patterns, url

from .views import IndexView, SynthesisInstanceView, ResumeInstanceView

INSTANCES = r'^(?P<instance_id>[^/]+)/%s$'
VIEW_MOD = 'openstack_dashboard.dashboards.project.instances.views'

urlpatterns = patterns('',
    url(r'^$', IndexView.as_view(), name='index'),
    url(r'^resume$', ResumeInstanceView.as_view(), name='resume'),
    url(r'^synthesis$', SynthesisInstanceView.as_view(), name='synthesis'),
    #url(r'^(?P<instance_id>[^/]+)/overlay', OverlayCreationView.as_view(), name='overlay'),
    #url(r'^(?P<instance_id>[^/]+)/$', DetailView.as_view(), name='detail'),
    #url(INSTANCES % 'update', UpdateView.as_view(), name='update'),
    #url(INSTANCES % 'console', 'console', name='console'),
    #url(INSTANCES % 'vnc', 'vnc', name='vnc'),
    #url(INSTANCES % 'spice', 'spice', name='spice'),
)
