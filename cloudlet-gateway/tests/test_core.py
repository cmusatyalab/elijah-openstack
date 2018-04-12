import unittest
import os
import logging

from context import caas
from context import cluster

class TestCluster(unittest.TestCase):

    def setUp(self):
        config = caas.core.config
        logging.config.dictConfig(config.LOG_CONFIG_DICT)

    def test_upper(self):
        sc = cluster.Swarm('test-swarm', env = os.environ.copy())
        sc.start()

if __name__ == '__main__':
    unittest.main()