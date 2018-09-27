"""Controller Manager Class for creating cluster controllers.

Factory pattern for creating cluster controllers. 
Libvirt Cluster Controllers should be singletons if the parameters to create them are the same.
"""
from __future__ import absolute_import, division, print_function

from caas.cluster import libvirtCluster

_controller_class = {
    'libvirt': libvirtCluster.LibvirtController
}

_libvirt_controllers = {}

def get_controller(cluster_type, *args, **kwargs):
    if cluster_type not in _controller_class:
        raise NotImplementedError("Unsupported cluster {}. Supported cluster types are {}".format(
            cluster_type, _controller_class.keys()))
    elif cluster_type == 'libvirt':
        uri = args[0]
        if uri not in _libvirt_controllers:
            controller = _controller_class[cluster_type](*args, **kwargs)
            _libvirt_controllers[uri] = controller
        return _libvirt_controllers[uri]
