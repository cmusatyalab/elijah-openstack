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
from nova.compute import manager as compute_manager
from nova.openstack.common.notifier import api as notifier
from nova.virt import driver


LOG = logging.getLogger(__name__)


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

