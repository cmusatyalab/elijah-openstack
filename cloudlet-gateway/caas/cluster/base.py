"""Abstract base class for cluster abstraction.

A cluster is an entity that has capbilities to CRUD compute resources.
"""
from __future__ import absolute_import, division, print_function

import abc

from future.utils import with_metaclass


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
