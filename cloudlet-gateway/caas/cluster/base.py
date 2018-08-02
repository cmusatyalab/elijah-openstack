"""Abstract base class for cluster abstraction.

A cluster is an entity that has capbilities to CRUD compute resources.
"""
from __future__ import absolute_import, division, print_function

import abc
import subprocess

from future.utils import with_metaclass


class NetworkInterface(object):
    def __init__(self):
        super(NetworkInterface, self).__init__()
        self.type, source, model = None, None, None


class BridgeNetworkInterface(object):
    def __init__(self, source):
        super(BridgeNetworkInterface, self).__init__()
        self.type = 'bridge'
        self.source = source
        self.model = 'e1000'


class GPU(object):
    def __init__(self, bus, slot, function):
        """Create a GPU object.
        bus, slot, function: integers corresponding to PCI device bus, slot, function
        """
        super(GPU, self).__init__()
        self.bus = '0x{:02X}'.format(bus)
        self.slot = '0x{:02X}'.format(slot)
        self.function = '0x{:02X}'.format(function)


class ResourceConfig(object):

    @staticmethod
    def _get_nvidia_gpu_info():
        """Return NVIDIA GPU card info."""
        cmd = 'lspci -nn | grep NVIDIA | cut -d " " -f 1 | tr : " " | tr . " "'
        # the output of the above command is "bus_id slot_id function" in hex
        cmd_proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        out, _ = cmd_proc.communicate()
        ret = cmd_proc.returncode
        if ret != 0:
            raise EnvironmentError("Failed to auto detect NVIDIA GPU cards information")
        gpus = []
        for line in out.splitlines():
            [bus, slot, function] = map(lambda x: int(x, 16), line.split())
            gpu = GPU(bus, slot, function)
            gpus.append(gpu)
        return gpus

    def __init__(self, name, cpu=0, memory=0, image_format=None, image_path=None, network_interfaces=[], gpus=[], detect_gpus=False):
        super(ResourceConfig, self).__init__()
        self.name = name
        self.cpu = cpu
        self.memory = memory
        self.image_format = image_format
        self.image_path = image_path
        self.network_interfaces = network_interfaces
        self.gpus = gpus

        # auto-detect GPU is limited to nvidia gpu only for now
        if detect_gpus:
            self.gpus = self._get_nvidia_gpu_info()


class BaseCluster(with_metaclass(abc.ABCMeta)):

    def __init__(self):
        pass

    @abc.abstractmethod
    def create(self, parameter_list):
        """Create a VM/Contianer."""
        raise NotImplementedError

    @abc.abstractmethod
    def get(self, parameter_list):
        """Get information about the cluster."""
        raise NotImplementedError

    @abc.abstractmethod
    def update(self, parameter_list):
        """Update a VM/Container"""
        raise NotImplementedError

    @abc.abstractmethod
    def delete(self, parameter_list):
        """Delete a VM/Container."""
        raise NotImplementedError
