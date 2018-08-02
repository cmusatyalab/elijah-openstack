from __future__ import absolute_import, division, print_function

import unittest

from context import caas
from caas.cluster import libvirtCluster
from caas.cluster import base


class TestLibvirt(unittest.TestCase):

    def setUp(self):
        pass

    def _get_current_domain_names(self, controller):
        current_domains = controller.get()
        current_domain_names = [domain['name'] for domain in current_domains]
        return current_domain_names

    def test_libvirt_create_list_and_delete_cpu_vm(self):
        controller = libvirtCluster.LibvirtController()
        # TODO(junjuew): image_path should be made relative
        domain_name = 'test_libvirt'
        vm_res_config = base.ResourceConfig(name=domain_name, cpu=4, memory=8, image_format='qcow2',
                              image_path='/home/junjuew/passthrough-test/ubuntu-16.04-nvidia-docker-openrtist-tensorflow-benchmark.qcow2',
                              network_interfaces=[base.BridgeNetworkInterface('vmbr0')])
        _ = controller.create(vm_res_config)
        current_domain_names = self._get_current_domain_names(controller)
        self.assertIn(domain_name, current_domain_names)
        controller.delete(name=domain_name)
        current_domain_names = self._get_current_domain_names(controller)
        self.assertNotIn(domain_name, current_domain_names)

    def test_libvirt_create_list_and_delete_gpu_vm(self):
        controller = libvirtCluster.LibvirtController()
        # TODO(junjuew): image_path should be made relative
        domain_name = 'test_libvirt_gpu'
        vm_res_config = base.ResourceConfig(name=domain_name, cpu=4, memory=8, image_format='qcow2',
                              image_path='/home/junjuew/passthrough-test/ubuntu-16.04-nvidia-docker-openrtist-tensorflow-benchmark.qcow2',
                              network_interfaces=[base.BridgeNetworkInterface('vmbr0')], detect_gpus=True)
        test_domain = controller.create(vm_res_config)
        current_domain_names = self._get_current_domain_names(controller)
        self.assertIn(test_domain.name(), current_domain_names)
        controller.delete(test_domain)
        current_domain_names = self._get_current_domain_names(controller)
        self.assertNotIn(test_domain.name(), current_domain_names)


if __name__ == '__main__':
    unittest.main()
