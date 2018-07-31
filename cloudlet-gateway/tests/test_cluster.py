from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
import unittest

from context import caas
from caas.cluster import libvirt

class TestLibvirt(unittest.TestCase):

    def setUp(self):
        pass 
    
    def test_libvirt_create_cpu(self):
        controller = libvirt.LibvirtController()
        # TODO(junjuew): image_path should be made relative
        controller.create(name='test_libvirt', cpu=4, memory=8, image_format='qcow2', image_path='/home/junjuew/passthrough-test/ubuntu-16.04-nvidia-docker-openrtist-tensorflow-benchmark.qcow2')

    def test_libvirt_create_gpu(self):
        controller = libvirt.LibvirtController()
        # TODO(junjuew): image_path should be made relative
        controller.create(name='test_libvirt_gpu', cpu=4, memory=8, image_format='qcow2', image_path='/home/junjuew/passthrough-test/ubuntu-16.04-nvidia-docker-openrtist-tensorflow-benchmark.qcow2', detect_gpus=True)

if __name__ == '__main__':
    unittest.main()