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
Scheduler Service for Cloudlet.
This is inherited from default nova scheduler manager.
It added below feature
 1. periodic pinging to cloud (configured using register_server option at nova.conf
 2. Broadcasting UPnP message to be found by a mobile device
"""


from oslo.config import cfg
from nova import manager
from nova.scheduler import manager as scheduler_manager
from nova.openstack.common import log as logging

from elijah.discovery.ds_register import RegisterThread
from elijah.discovery.ds_register import RegisterError
from elijah.discovery.Const import DiscoveryConst
from elijah.discovery.Const import CLOUDLET_FEATURE
from elijah.discovery.monitor.resource import ResourceMonitor


LOG = logging.getLogger(__name__)


cloudlet_discovery_opts = [
    cfg.StrOpt('register_server',
               default= "http://reg.findcloudlet.org",
               help='URL of central Cloud server to send heart beat'),
    cfg.IntOpt('register_ping_interval',
               default=60,
               help='Interval in seconds for send heart beat to register server'),
    ]
CONF = cfg.CONF
CONF.register_opts(cloudlet_discovery_opts)


class CloudletSchedulerManager(scheduler_manager.SchedulerManager):
    def __init__(self, scheduler_driver=None, *args, **kwargs):
        self.resource_uri = None
        super(CloudletSchedulerManager, self).__init__(*args, **kwargs)

    @manager.periodic_task(spacing=CONF.register_ping_interval)
    def _update_cloudlet_status(self, context):
        LOG.info(_("Send ping to registration server at %s" % (CONF.register_server)))
        

        try:
            hosts = self.driver.host_manager.get_all_host_states(context)
            resource_monitor = ResourceMonitor(openstack_hosts=hosts)
            register_server = CONF.register_server
            cloudlet_ip = CONF.my_ip
            cloudlet_rest_port = DiscoveryConst.REST_API_PORT
            feature_flag_list = {CLOUDLET_FEATURE.VM_SYNTHESIS_OPENSTACK}
            if self.resource_uri is None:
                # Start registration client
                self.resource_uri = RegisterThread.initial_register(
                        register_server, resource_monitor, feature_flag_list,
                        cloudlet_ip, cloudlet_rest_port)
                LOG.info(_("Success to register to %s" % register_server))
            else:
                RegisterThread.update_status(register_server,\
                        self.resource_uri, feature_flag_list, resource_monitor)
                LOG.info(_("Success to update to %s" % register_server))
        except RegisterError as e:
            LOG.debug("Failed to update to Cloud: %s" % str(e))
