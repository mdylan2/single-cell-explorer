import os
import shutil
import unittest

from server import import_plugins
from tests import PROJECT_ROOT, random_string


class TestPlugins(unittest.TestCase):
    """ Test plugin import functionality """

    plugins_dir = f"{PROJECT_ROOT}/server/tests/test_server/unit/plugins"
    test_plugin_path = f"{plugins_dir}/foo.py"
    secret = random_string(8)

    @classmethod
    def setUpClass(cls) -> None:
        if not os.path.isdir(cls.plugins_dir):
            os.mkdir(cls.plugins_dir)
        with open(cls.test_plugin_path, "w") as fh:
            fh.write(f'SECRET = "{cls.secret}"\n')

    @classmethod
    def tearDownClass(cls) -> None:
        if os.path.isdir(cls.plugins_dir):
            shutil.rmtree(cls.plugins_dir)

    def test_import_plugins(self):
        self.assertTrue(os.path.isfile(self.test_plugin_path))
        loaded_modules = import_plugins("server.tests.test_server.unit.plugins")
        # tests that import plugins found the file
        self.assertEqual(["server.tests.test_server.unit.plugins.foo"], [ele.__name__ for ele in loaded_modules])
        # tests that the module was properly executed
        self.assertEqual(self.secret, loaded_modules[0].SECRET)
