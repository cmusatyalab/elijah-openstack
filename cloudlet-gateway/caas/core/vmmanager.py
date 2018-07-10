"""Virtual Machine manager/provider"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
import six
import abc

@six.add_metaclass(abc.ABCMeta)
class VMManager():
    """VM Managers in charge of CRUD and monitoring VMs"""

    def __init__(self):
        self.builder = None

    @abc.abstractclassmethod
    def info(self):
        """VM infos"""
        pass

class LibVirtVMBuilder(object):
    """LibVirt VM builder"""

    def __init__(self, cpu_cnt = 0, mem_gb = 0, gpu_cnt = 0):
        self._cpu_cnt = cpu_cnt
        self._mem_gb = mem_gb
        self._gpu_cnt = gpu_cnt

    def set_cpu_cnt(self, cpu_cnt):
        self._cpu_cnt = cpu_cnt
        return self
    
    def set_mem_gb(self, mem_gb):
        self._mem_gb = mem_gb
        return self
    
    def add_gpu(self):
        self._gpu_cnt += 1
    
    def build(self):




class LibVirtVMManager(VMManager):

    def __init__(self):
        self.builder = self._
