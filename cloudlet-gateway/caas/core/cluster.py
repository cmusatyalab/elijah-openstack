#!/usr/bin/env python
import collections

import logging
from enum import Enum

from caas.core import machine
from caas.core import config
import docker

import settings
from exc import CreationError

logger = logging.getLogger(__name__)

Status = Enum("Status", "not_created running stopped unknown")
Role = Enum("Role", "leader manager worker")
SwarmDiscoveryInfo = collections.namedtuple('SwarmDiscoveryInfo', ['url', 'token'])

class SwarmNode(object):
    # TODO: need to check if name is unique?
    def __init__(self, name, os_env, role=Role.worker):
        '''
        :param name: name of the swarm node  
        :param os_env: 
        environment variables for launching a swarmnode. For openstack, it should contain configurations from openrc.sh.
        necessary env:
        OS_FLAVOR_NAME
        OS_IMAGE_NAME
        OS_NETWORK_NAME
        OS_SSH_USER
        OS_SECURITY_GROUPS
        
        optional env:
        OS_FLOATINGIP_POOL
        
        danger env:
        OS_KEYPAIR_NAME: existing keypair will be DELETED from OpenStack by docker openstack driver when using 
        docker-machine rm 
        '''
        # provider is a docker-machine
        self._provider = machine.Machine(path=config.DOCKER_MACHINE_PATH)
        self.name = name
        self.os_env = os_env
        self.role = role
        self.dc = None  # docker client
        self._setup_funcs = {
            Role.leader: self._swarm_setup_leader,
            Role.manager: self._swarm_setup_manager_and_worker,
            Role.worker: self._swarm_setup_manager_and_worker}

    def start(self, discovery_info=None):
        '''
        start a swarm node
        :return: 
        '''
        if self.status == Status.not_created:
            # launch machine
            # TODO does it need to be streaming?
            stdout, stderr, errorcode = self._provider.create(self.name, driver='openstack',
                                                              env=self.os_env)
            if not errorcode:
                # TODO: dc needs to be re-initialized when a node is restarted, since the ip address might change
                self.dc = docker.DockerClient(**self.env)
                created_swarm_discovery_info = self._swarm_setup(discovery_info)
        else:
            raise CreationError(self, "Failed to create. Node {} has been already created".format(self))
        return created_swarm_discovery_info

    @property
    def status(self):
        if self._provider.exists(self.name):
            if self._provider.status(self.name):
                # even if there could be errors, docker-machine ls shows the created machine as running
                status = Status.running
            else:
                status = Status.stopped
        else:
            status = Status.not_created
        return status

    @property
    def env(self):
        # TODO: need to check the format of env
        # right now assuing a dictionary with the same keys used by docker.DockerClient()
        return self._provider.env(machine=self.name)

    def promote(self, sn):
        # if node is not running or in swarm, raise NotInSwarm error
        # if node is not a swarm manager, raise PermissionError
        # call docker node to promote
        pass

    def demote(self, sn):
        pass

    def __repr__(self):
        return '{}({})'.format(self.name, self.status)

    def _swarm_setup(self, discovery_info):
        try:
            self._setup_funcs[self.role](discovery_info)
        except docker.errors.APIError as e:
            raise CreationError(self, e)

    def _swarm_setup_leader(self, discovery_info):
        self.dc.swarm.init()
        dtokens = self.dc.swarm.attrs[config.SWARM_TOKEN_ATTR]
        tokens = {Role.manager:dtokens[config.SWARM_TOKEN_MANAGER_ROLE],
                  Role.worker:dtokens[config.SWARM_TOKEN_WORKER_ROLE]}
        return tokens

    def _swarm_setup_manager_and_worker(self, discovery_info):
        self.dc.swarm.join([discovery_info.url], discovery_info.token[self.role])

class Swarm(object):
    '''
    represents a swarm cluster
    '''
    def _new_node_name(self):
        name = '{}-{}'.format(self.name, self._node_id)
        self._node_id+=1
        return name

    def __init__(self, name, env, size=(1, 0)):
        self.env = env
        self._node_id = 0
        self.name = name
        self.nodes = {Role.leader: SwarmNode(self._new_node_name(), env, role=Role.leader)}
        self.nodes.update({Role.manager: [SwarmNode(self._new_node_name(), env, role=Role.manager) for _ in range(size[0] - 1)]})
        self.nodes.update({Role.worker: [SwarmNode(self._new_node_name(), env) for _ in range(size[0] - 1)]})

    def start(self):
        # start leader node
        discovery_info = self.nodes[Role.leader].start(None)
        # start manager node
        map(lambda node: node.start(discovery_info), self.nodes[Role.manager])
        # start regular node
        map(lambda node: node.start(discovery_info), self.nodes[Role.worker])

def create_machine(osenv, path="/usr/local/bin/docker-machine"):
    pass


def create_swarm_cluster():
    # create a master machine
    # create needed worker machine
    pass


def delete_swarm_cluster():
    pass
