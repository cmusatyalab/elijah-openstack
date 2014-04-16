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
Scheduler Service
"""

import sys

from oslo.config import cfg

from nova.compute import rpcapi as compute_rpcapi
from nova.compute import task_states
from nova.compute import utils as compute_utils
from nova.compute import vm_states
from nova.conductor import api as conductor_api
import nova.context
from nova import exception
from nova import manager
from nova import notifications
from nova.openstack.common import excutils
from nova.openstack.common import importutils
from nova.openstack.common import jsonutils
from nova.openstack.common import log as logging
from nova.openstack.common.notifier import api as notifier
from nova.openstack.common.rpc import common as rpc_common

from nova.scheduler import manager as scheduler_manager


LOG = logging.getLogger(__name__)


cloudlet_discovery_opts = [
    cfg.StrOpt('register_server',
               default= "http://reg.findcloudlet.org",
               help='URL of central Cloud server to send heart beat'),
    ]
CONF = cfg.CONF
CONF.register_opts(cloudlet_discovery_opts)


class CloudletSchedulerManager(scheduler_manager.SchedulerManager):
    """Chooses a host to run instances on."""

    RPC_API_VERSION = '2.6'

    def __init__(self, scheduler_driver=None, *args, **kwargs):
        import pdb;pdb.set_trace()
        super(CloudletSchedulerManager, self).__init__(*args, **kwargs)

    @manager.periodic_task
    def _update_cloudlet_status(self, context):
        from elijah.discovery.ds_register import RegisterThread
        from elijah.discovery.ds_register import get_local_ipaddress
        from elijah.discovery.ds_register import RegisterError
        from elijah.discovery.Const import DiscoveryConst
        from elijah.discovery.Const import CLOUDLET_FEATURE
        from elijah.discovery.monitor import resource

        self.resource_uri = None
        LOG.info(_("ping to Cloud"))

        try:
            resource_monitor = resource.get_instance()
            
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
                self.register_client.update_status(register_server,\
                        self.resource_uri, feature_flag_list, resource_monitor)
                LOG.info(_("Success to update to %s" % register_server))
        except RegisterError as e:
            LOG.debug("Failed to update to Cloud: %s" % str(e))
