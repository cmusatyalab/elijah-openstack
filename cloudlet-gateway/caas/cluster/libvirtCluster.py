"""Abstraction for a libvirt controller that can CRUD libvirt-based VMs.

This module is standalone except using the global jinja2 environment.
Only libvirt bridge networking is supported now. It assumes the host system
already has a bridge created.
"""
from __future__ import absolute_import, division, print_function

import libvirt
from jinja2 import Environment, PackageLoader, select_autoescape
from logzero import logger

from caas.cluster import base

class Singleton(type):
    _instances = {}
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]

class LibvirtController(base.BaseCluster):
    __metaclass__ = Singleton
    """Controller for managing libvirt-based VMs."""
    DOMAIN_INFO_NAME = 'name'
    DOMAIN_INFO_STATE = 'state'
    JINJA_PACKAGE_LOADER_PACKAGE = 'caas'
    JINJA_PACKAGE_LOADER_TEMPLATE_DIR = 'templates'
    _instances = {}

    @staticmethod
    def get_controller_instance(uri="qemu:///system"):
        if uri not in _intances:
            _instances[uri] = _create_instance(uri)
        else:
            return _instances[uri]

    def __init__(self, uri="qemu:///system"):
        # TODO: implement singleton
        # if LibvirtController.__instance[uri] != None:
        #     raise ValueError("This class is a singleton!")
        # else:
        #     Singleton.__instance = self

        """Connect to libvirt daemon."""
        super(LibvirtController, self).__init__()
        self._conn = libvirt.open(uri)
        if self._conn is None:
            raise EnvironmentError("Failed to connect to libvirt. Do you have libvirt installed?")
        self._jinja_env = Environment(
            loader=PackageLoader(self.__class__.JINJA_PACKAGE_LOADER_PACKAGE, self.__class__.JINJA_PACKAGE_LOADER_TEMPLATE_DIR),
            autoescape=select_autoescape(['html', 'xml'])
        )
    
    def _create_vm_from_xml_template(self, res_config):
        template = self._jinja_env.get_template("libvirt-vm-template.xml")
        vm_xml = template.render(res_config=res_config)
        domain = self._conn.createXML(vm_xml, 0)
        if domain is None:
            raise EnvironmentError("Libvirt failed to create {}.".format(res_config.name))
        return domain

    def create(self, res_config):
        """Create a libvirt VM.

        network_interfaces: a list of NetworkInterface-derived objects.
        gpus: a list of GPU objects
        """
        return self._create_vm_from_xml_template(res_config)

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
