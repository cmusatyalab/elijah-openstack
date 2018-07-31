from __future__ import absolute_import, division, print_function

import shlex
import subprocess

import flask
import libvirt
from jinja2 import Environment, PackageLoader, select_autoescape

from caas.cluster import base


class LibvirtController(base.BaseCluster):
    """Controller for managing libvirt-based VMs"""

    def __init__(self, uri="qemu:///system"):
        """Connect to libvirt daemon."""
        self._conn = libvirt.open(uri)
        if self._conn is None:
            raise EnvironmentError("Failed to connect to libvirt. Do you have libvirt installed?")
        self._jinja_env = Environment(
            loader=PackageLoader('caas', 'templates'),
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
        print(vm_xml)
        domain = self._conn.createXML(vm_xml, 0)
        if domain is None:
            raise EnvironmentError("Libvirt failed to create {}.".format(name))

    def _get_nvidia_gpu_info(self):
        """Return NVIDIA GPU card info."""
        cmd = "lspci -nn | grep -o '.*NVIDIA.*' | cut -d ' ' -f 1"
        cmd_proc = subprocess.Popen(shlex.split(cmd), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        ret = cmd_proc.returncode
        if ret != 0:
            raise EnvironmentError("Failed to auto detect NVIDIA GPU cards information")
        out, _ = cmd_proc.communicate()
        gpus = []
        for line in out:
            gpu_info = {}
            gpu_info['bus'] = '0x{:2X}'.format(out.split(':')[0])
            gpu_info['slot'] = '0x{:2X}'.format(out.split(':')[1].split('.')[0])
            gpu_info['function'] = '0x{:2X}'.format(out.split(':')[1].split('.')[1])
        return gpus

    def create(self, name, cpu, memory, image_format, image_path, gpus=[], detect_gpus=False):
        """Create a libvirt VM"""
        # auto-detect GPU is limited to nvidia gpu only for now
        if detect_gpus:
            gpus = self._get_nvidia_gpu_info()
        self._create_vm_from_xml_template(name=name,
                                          cpu=cpu,
                                          memory=memory,
                                          image_format=image_format,
                                          image_path=image_path,
                                          gpus=gpus)

    def read(self):
        pass

    def delete(self):
        pass
    
    def update(self):
        pass
