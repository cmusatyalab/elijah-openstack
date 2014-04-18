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
 2. Broadcasting Avahi message for a mobile client within broadcasting domain
"""


from oslo.config import cfg
from nova import manager
from nova.scheduler import manager as scheduler_manager
from nova.openstack.common import log as logging
from nova.compute.cloudlet_api import CloudletAPI as CloudletAPI

from elijah.discovery.ds_register import RegisterThread
from elijah.discovery.ds_register import RegisterError
from elijah.discovery.config import DiscoveryConst
from elijah.discovery.config import CLOUDLET_FEATURE
from elijah.discovery.avahi_server import AvahiServerThread
from elijah.discovery.avahi_server import AvahiDiscoverError


LOG = logging.getLogger(__name__)


cloudlet_discovery_opts = [
    cfg.StrOpt('register_server',
               default= "http://reg.findcloudlet.org",
               help='URL of central Cloud server to send heart beat'),
    cfg.IntOpt('register_ping_interval',
               default=60,
               help='Interval in seconds for send heart beat to register server'),
    cfg.BoolOpt('register_enable_avahi',
               default=True,
               help="Whether to turn on Avahi server for local discovery"),
    ]
CONF = cfg.CONF
CONF.register_opts(cloudlet_discovery_opts)


class CloudletSchedulerManager(scheduler_manager.SchedulerManager):
    def __init__(self, scheduler_driver=None, *args, **kwargs):
        self.resource_uri = None
        self.cloudlet_api = CloudletAPI()

        # Start Avahi Server
        avahi_server = None
        if CONF.register_enable_avahi is True:
            # Start Avahi Server
            try:
                avahi_server = AvahiServerThread(service_name=DiscoveryConst.SERVICE_NAME,
                        service_port=DiscoveryConst.SERVICE_PORT)
                avahi_server.start()
                LOG.info("[Avahi] Start Avahi Server")
            except AvahiDiscoverError as e:
                LOG.info(str(e))
                LOG.info("Cannot start Avahi Server. Start avahi-daemon")
                avahi_server.terminate()
                avahi_server = None

        super(CloudletSchedulerManager, self).__init__(*args, **kwargs)

    @manager.periodic_task(spacing=CONF.register_ping_interval)
    def _update_cloudlet_status(self, context):
        LOG.info(_("Send ping to registration server at %s" % (CONF.register_server)))
        
        try:
            resource_stats = self.cloudlet_api.cloudlet_get_static_status(context, None)
            register_server = CONF.register_server
            cloudlet_ip = CONF.my_ip
            cloudlet_rest_port = DiscoveryConst.REST_API_PORT
            feature_flag_list = {CLOUDLET_FEATURE.VM_SYNTHESIS_OPENSTACK}
            if self.resource_uri is None:
                # Start registration client
                self.resource_uri = RegisterThread.initial_register(
                        register_server, resource_stats, feature_flag_list,
                        cloudlet_ip, cloudlet_rest_port)
                LOG.info(_("Success to register to %s" % register_server))
            else:
                RegisterThread.update_status(register_server,\
                        self.resource_uri, feature_flag_list, resource_stats)
                LOG.info(_("Success to update to %s" % register_server))
        except RegisterError as e:
            LOG.debug("Failed to update to Cloud: %s" % str(e))
