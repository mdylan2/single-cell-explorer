import unittest

from server.common.utils.data_locator import DataLocator
from server.dataset.cxg_dataset import CxgDataset
from server.tests.unit import app_config
from server.tests import FIXTURES_ROOT
from server.tests.fixtures.fixtures import pbmc3k_colors


class TestCxgDataset(unittest.TestCase):
    def test_get_colors(self):
        data = self.get_data("pbmc3k.cxg")
        self.assertDictEqual(data.get_colors(), pbmc3k_colors)
        data = self.get_data("pbmc3k_v0.cxg")
        self.assertDictEqual(data.get_colors(), dict())

    def get_data(self, fixture):
        data_locator = f"{FIXTURES_ROOT}/{fixture}"
        config = app_config(data_locator)
        return CxgDataset(DataLocator(data_locator), config)
