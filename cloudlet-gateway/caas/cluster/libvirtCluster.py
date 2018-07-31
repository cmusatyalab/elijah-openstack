"""Abstraction for a libvirt controller that can CRUD libvirt-based VMs.

This module is standalone except using the global jinja2 environment.
"""
from __future__ import absolute_import, division, print_function
import subprocess

import libvirt
from jinja2 import Environment, PackageLoader, select_autoescape
from logzero import logger

from caas.cluster import base


class LibvirtController(base.BaseCluster):
    """Controller for managing libvirt-based VMs."""
    DOMAIN_INFO_NAME = 'name'
    DOMAIN_INFO_STATE = 'state'
    HOST_GPU_INFO_BUS = 'bus'
    HOST_GPU_INFO_SLOT = 'slot'
    HOST_GPU_INFO_FUNCTION = 'function'
    JINJA_PACKAGE_LOADER_PACKAGE = 'caas'
    JINJA_PACKAGE_LOADER_TEMPLATE_DIR = 'templates'

    def __init__(self, uri="qemu:///system"):
        """Connect to libvirt daemon."""
        self._conn = libvirt.open(uri)
        if self._conn is None:
            raise EnvironmentError("Failed to connect to libvirt. Do you have libvirt installed?")
        self._jinja_env = Environment(
            loader=PackageLoader(self.__class__.JINJA_PACKAGE_LOADER_PACKAGE,
                                 self.__class__.JINJA_PACKAGE_LOADER_TEMPLATE_DIR),
            autoescape=select_autoescape(['html', 'xml'])
        )

    def _create_vm_from_xml_template(self, name, cpu, memory, image_format, image_path, gpus):
        template = self._jinja_env.get_template("libvirt-vm-template.xml")
        vm_xml = template.render(name=name,
                                 cpu=cpu,
                                 memory=memory,
                                 image_format=image_format,
                                 image_path=image_path,
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
            gpu_info = {}
            [bus, slot, function] = map(lambda x: int(x, 16), line.split())
            gpu_info[self.__class__.HOST_GPU_INFO_BUS] = '0x{:02X}'.format(bus)
            gpu_info[self.__class__.HOST_GPU_INFO_SLOT] = '0x{:02X}'.format(slot)
            gpu_info[self.__class__.HOST_GPU_INFO_FUNCTION] = '0x{:02X}'.format(function)
            gpus.append(gpu_info)
        return gpus

    def create(self, name, cpu, memory, image_format, image_path, gpus=[], detect_gpus=False):
        """Create a libvirt VM"""
        # auto-detect GPU is limited to nvidia gpu only for now
        if detect_gpus:
            gpus = self._get_nvidia_gpu_info()
        return self._create_vm_from_xml_template(name=name,
                                                 cpu=cpu,
                                                 memory=memory,
                                                 image_format=image_format,
                                                 image_path=image_path,
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
