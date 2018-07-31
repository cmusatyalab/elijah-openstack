"""Abstraction for a libvirt controller that can CRUD libvirt-based VMs.

This module is standalone except using the global jinja2 environment.
Only libvirt bridge networking is supported now. It assumes the host system
already has a bridge created.
"""
from __future__ import absolute_import, division, print_function

import subprocess

import libvirt
from jinja2 import Environment, PackageLoader, select_autoescape
from logzero import logger

from caas.cluster import base

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

class LibvirtController(base.BaseCluster):
    """Controller for managing libvirt-based VMs."""
    DOMAIN_INFO_NAME = 'name'
    DOMAIN_INFO_STATE = 'state'
    JINJA_PACKAGE_LOADER_PACKAGE = 'caas'
    JINJA_PACKAGE_LOADER_TEMPLATE_DIR = 'templates'

    def __init__(self, uri="qemu:///system"):
        """Connect to libvirt daemon."""
        super(LibvirtController, self).__init__()
        self._conn = libvirt.open(uri)
        if self._conn is None:
            raise EnvironmentError("Failed to connect to libvirt. Do you have libvirt installed?")
        self._jinja_env = Environment(
            loader=PackageLoader(self.__class__.JINJA_PACKAGE_LOADER_PACKAGE,
                                 self.__class__.JINJA_PACKAGE_LOADER_TEMPLATE_DIR),
            autoescape=select_autoescape(['html', 'xml'])
        )

    def _create_vm_from_xml_template(self, name, cpu, memory, image_format, image_path, network_interfaces, gpus):
        template = self._jinja_env.get_template("libvirt-vm-template.xml")
        vm_xml = template.render(name=name,
                                 cpu=cpu,
                                 memory=memory,
                                 image_format=image_format,
                                 image_path=image_path,
                                 network_interfaces = network_interfaces,
                                 gpus=gpus)
        domain = self._conn.createXML(vm_xml, 0)
        if domain is None:
            raise EnvironmentError("Libvirt failed to create {}.".format(name))
        return domain

    def _get_nvidia_gpu_info(self):
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

    def create(self, name, cpu, memory, image_format, image_path, network_interfaces, gpus=[], detect_gpus=False):
        """Create a libvirt VM.

        network_interfaces: a list of NetworkInterface-derived objects.
        gpus: a list of GPU objects
        """
        # auto-detect GPU is limited to nvidia gpu only for now
        if detect_gpus:
            gpus = self._get_nvidia_gpu_info()
        return self._create_vm_from_xml_template(name=name,
                                                 cpu=cpu,
                                                 memory=memory,
                                                 image_format=image_format,
                                                 image_path=image_path,
                                                 network_interfaces=network_interfaces,
                                                 gpus=gpus)

    def get(self):
        """Get information about all the domains created by libvirt."""
        domains = self._conn.listAllDomains(0)
        info = []
        for domain in domains:
            domain_info = {}
            domain_info[self.__class__.DOMAIN_INFO_NAME] = domain.name()
            state, _ = domain.state()
            domain_info[self.__class__.DOMAIN_INFO_STATE] = state
            info.append(domain_info)
        return info

    def _delete_domain(self, domain):
        try:
            domain.undefine()
        except libvirt.libvirtError as e:
            logger.warning("Unable to undefine the domain. Trying to destroy it instead. Libvirt Error: {}".format(e))
            domain.destroy()

    def delete(self, domain=None, name=None):
        if name is not None:
            domain = self._conn.lookupByName(name)
        if domain is not None:
            self._delete_domain(domain)
        else:
            raise ValueError("Failed to delete domain. Invalid name {} or domain object {}.".format(name, domain))

    def update(self):
        raise NotImplementedError("Libvirt cluster does not support update operation.")
