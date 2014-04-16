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

from nova.compute import task_states
from nova.compute import vm_states
from nova.openstack.common import log as logging
from nova import utils
from nova.openstack.common import lockutils
from nova import exception
from nova import manager as manager
from nova.compute import manager as compute_manager
from nova.openstack.common.notifier import api as notifier
from nova.virt import driver
from oslo.config import cfg


LOG = logging.getLogger(__name__)


cloudlet_discovery_opts = [
    cfg.StrOpt('register_server',
               default= "http://reg.findcloudlet.org",
               help='URL of central Cloud server to send heart beat'),
    ]
CONF = cfg.CONF
CONF.register_opts(cloudlet_discovery_opts)


class CloudletComputeManager(compute_manager.ComputeManager):
    """Manages the running instances from creation to destruction."""
    RPC_API_VERSION = '2.28'

    def __init__(self, compute_driver=None, *args, **kwargs):
        super(CloudletComputeManager, self).__init__(*args, **kwargs)

        # make sure to load cloudlet Driver which inherit libvirt driver
        # change at /etc/nova/nova-compute.conf
        self.driver = driver.load_compute_driver(self.virtapi, compute_driver)

    @compute_manager.exception.wrap_exception(notifier=notifier, \
            publisher_id=compute_manager.publisher_id())
    @compute_manager.reverts_task_state
    @compute_manager.wrap_instance_fault
    def cloudlet_create_base(self, context, instance, vm_name, 
            disk_meta_id, memory_meta_id, 
            diskhash_meta_id, memoryhash_meta_id):
        """Cloudlet base creation
        and terminate the instance
        """
        context = context.elevated()
        current_power_state = self._get_power_state(context, instance)
        LOG.info(_("Generating cloudlet base"), instance=instance)

        self._notify_about_instance_usage(context, instance, "snapshot.start")

        def update_task_state(task_state, expected_state=task_states.IMAGE_SNAPSHOT):
            return self._instance_update(context, instance['uuid'],
                    task_state=task_state,
                    expected_task_state=expected_state)

        self.driver.cloudlet_base(context, instance, vm_name, 
                disk_meta_id, memory_meta_id, 
                diskhash_meta_id, memoryhash_meta_id, update_task_state)

        instance = self._instance_update(context, instance['uuid'],
                task_state=None,
                expected_task_state=task_states.IMAGE_UPLOADING)

        # notify will raise exception since instance is already deleted
        self._notify_about_instance_usage( context, instance, "snapshot.end")
        self.cloudlet_terminate_instance(context, instance)

    @compute_manager.exception.wrap_exception(notifier=notifier, \
            publisher_id=compute_manager.publisher_id())
    @compute_manager.reverts_task_state
    @compute_manager.wrap_instance_fault
    def cloudlet_overlay_finish(self, context, instance, overlay_name, overlay_id):
        """Generate VM overlay with given instance,
        and save it as a snapshot
        """
        context = context.elevated()
        LOG.info(_("Generating VM overlay"), instance=instance)

        def update_task_state(task_state, expected_state=task_states.IMAGE_SNAPSHOT):
            return self._instance_update(context, instance['uuid'],
                    task_state=task_state,
                    expected_task_state=expected_state)

        self.driver.create_overlay_vm(context, instance, overlay_name, 
                overlay_id, update_task_state)

        instance = self._instance_update(context, instance['uuid'],
                task_state=None,
                expected_task_state=task_states.IMAGE_UPLOADING)
        self.cloudlet_terminate_instance(context, instance)

    # almost identical to terminate_instance method
    def cloudlet_terminate_instance(self, context, instance):
        bdms = self._get_instance_volume_bdms(context, instance)

        @lockutils.synchronized(instance['uuid'], 'nova-')
        def do_terminate_instance(instance, bdms):
            try:
                self._delete_instance(context, instance, bdms,
                                      reservations=None)
            except exception.InstanceTerminationFailure as error:
                msg = _('%s. Setting instance vm_state to ERROR')
                LOG.error(msg % error, instance=instance)
                self._set_instance_error_state(context, instance['uuid'])
            except exception.InstanceNotFound as e:
                LOG.warn(e, instance=instance)

        do_terminate_instance(instance, bdms)

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
