from __future__ import absolute_import, division, print_function

import unittest

from context import caas
from caas.cluster import libvirtCluster


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
        _ = controller.create(name=domain_name, cpu=4, memory=8, image_format='qcow2',
                              image_path='/home/junjuew/passthrough-test/ubuntu-16.04-nvidia-docker-openrtist-tensorflow-benchmark.qcow2',
                              network_interfaces=[libvirtCluster.BridgeNetworkInterface('vmbr0')])
        current_domain_names = self._get_current_domain_names(controller)
        self.assertIn(domain_name, current_domain_names)
        controller.delete(name=domain_name)
        current_domain_names = self._get_current_domain_names(controller)
        self.assertNotIn(domain_name, current_domain_names)

    def test_libvirt_create_list_and_delete_gpu_vm(self):
        controller = libvirtCluster.LibvirtController()
        # TODO(junjuew): image_path should be made relative
        test_domain = controller.create(name='test_libvirt_gpu', cpu=4, memory=8, image_format='qcow2',
                                        image_path='/home/junjuew/passthrough-test/ubuntu-16.04-nvidia-docker-openrtist-tensorflow-benchmark.qcow2', 
                                        network_interfaces=[libvirtCluster.BridgeNetworkInterface('vmbr0')],
                                        detect_gpus=True)
        current_domain_names = self._get_current_domain_names(controller)
        self.assertIn(test_domain.name(), current_domain_names)
        controller.delete(test_domain)
        current_domain_names = self._get_current_domain_names(controller)
        self.assertNotIn(test_domain.name(), current_domain_names)


if __name__ == '__main__':
    unittest.main()
