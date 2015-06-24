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
from django.conf.urls import patterns, url

from .views import download_vm_overlay
from .views import IndexView
from .views import SynthesisInstanceView
from .views import ResumeInstanceView
from .views import ImportBaseView
from .views import HandoffInstanceView


INSTANCES = r'^(?P<instance_id>[^/]+)/%s$'
VIEW_MOD = 'openstack_dashboard.dashboards.project.instances.views'

urlpatterns = patterns(
    '',
    url(r'^$', IndexView.as_view(), name='index'),
    url(r'^resume/$', ResumeInstanceView.as_view(), name='resume'),
    url(r'^import/$', ImportBaseView.as_view(), name='import'),
    url(r'^synthesis/$', SynthesisInstanceView.as_view(), name='synthesis'),
    url(INSTANCES % 'handoff', HandoffInstanceView.as_view(), name='handoff'),
    url(r'^download/$', download_vm_overlay, name='download'),
)
