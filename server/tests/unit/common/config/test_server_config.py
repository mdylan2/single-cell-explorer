import json
import os
import unittest
from unittest.mock import patch


from server.common.config.base_config import BaseConfig
from server.common.utils.utils import find_available_port
from server.tests import PROJECT_ROOT, FIXTURES_ROOT

from server.common.config.app_config import AppConfig
from server.common.errors import ConfigurationError
from server.tests.unit.common.config import ConfigTests


class TestServerConfig(ConfigTests):
    def setUp(self):
        self.config_file_name = f"{unittest.TestCase.id(self).split('.')[-1]}.yml"
        self.config = AppConfig()
        self.config.update_server_config(app__flask_secret_key="secret")
        self.config.update_server_config(multi_dataset__dataroot=FIXTURES_ROOT)
        self.server_config = self.config.server_config
        self.config.complete_config()

        message_list = []

        def noop(message):
            message_list.append(message)

        messagefn = noop
        self.context = dict(messagefn=messagefn, messages=message_list)

    def get_config(self, **kwargs):
        file_name = self.custom_app_config(
            dataroot=f"{FIXTURES_ROOT}", config_file_name=self.config_file_name, **kwargs
        )
        config = AppConfig()
        config.update_from_config_file(file_name)
        return config

    def test_init_raises_error_if_default_config_is_invalid(self):
        invalid_config = self.get_config(port="not_valid")
        with self.assertRaises(ConfigurationError):
            invalid_config.complete_config()

    @patch("server.common.config.server_config.BaseConfig.validate_correct_type_of_configuration_attribute")
    def test_complete_config_checks_all_attr(self, mock_check_attrs):
        mock_check_attrs.side_effect = BaseConfig.validate_correct_type_of_configuration_attribute()
        self.server_config.complete_config(self.context)
        self.assertEqual(mock_check_attrs.call_count, 31)

    def test_handle_app__throws_error_if_port_doesnt_exist(self):
        config = self.get_config(port=99999999)
        with self.assertRaises(ConfigurationError):
            config.server_config.handle_app(self.context)

    @patch("server.common.config.server_config.discover_s3_region_name")
    def test_handle_data_locator_works_for_default_types(self, mock_discover_region_name):
        mock_discover_region_name.return_value = None
        # Default config
        self.assertEqual(self.config.server_config.data_locator__s3__region_name, None)
        # hard coded
        config = self.get_config()
        self.assertEqual(config.server_config.data_locator__s3__region_name, "us-east-1")
        # incorrectly formatted
        dataroot = {
            "d1": {"base_url": "set1", "dataroot": "/path/to/set1_datasets/"},
            "d2": {"base_url": "set2/subdir", "dataroot": "s3://shouldnt/work"},
        }
        file_name = self.custom_app_config(
            dataroot=dataroot, config_file_name=self.config_file_name, data_locator_region_name="true"
        )
        config = AppConfig()
        config.update_from_config_file(file_name)
        with self.assertRaises(ConfigurationError):
            config.server_config.handle_data_locator()

    @patch("server.common.config.server_config.discover_s3_region_name")
    def test_handle_data_locator_can_read_from_dataroot(self, mock_discover_region_name):
        mock_discover_region_name.return_value = "us-west-2"
        dataroot = {
            "d1": {"base_url": "set1", "dataroot": "/path/to/set1_datasets/"},
            "d2": {"base_url": "set2/subdir", "dataroot": "s3://hosted-cellxgene-dev"},
        }
        file_name = self.custom_app_config(
            dataroot=dataroot, config_file_name=self.config_file_name, data_locator_region_name="true"
        )
        config = AppConfig()
        config.update_from_config_file(file_name)
        config.server_config.handle_data_locator()
        self.assertEqual(config.server_config.data_locator__s3__region_name, "us-west-2")
        mock_discover_region_name.assert_called_once_with("s3://hosted-cellxgene-dev")

    def test_handle_app___can_use_envar_port(self):
        config = self.get_config(port=24)
        self.assertEqual(config.server_config.app__port, 24)

        # Note if the port is set in the config file it will NOT be overwritten by a different envvar
        os.environ["CXG_SERVER_PORT"] = "4008"
        self.config = AppConfig()
        self.config.update_server_config(app__flask_secret_key="secret")
        self.config.server_config.handle_app(self.context)
        self.assertEqual(self.config.server_config.app__port, 4008)
        del os.environ["CXG_SERVER_PORT"]

    def test_handle_app__can_get_secret_key_from_envvar_or_config_file_with_envvar_given_preference(self):
        config = self.get_config(flask_secret_key="KEY_FROM_FILE")
        self.assertEqual(config.server_config.app__flask_secret_key, "KEY_FROM_FILE")

        os.environ["CXG_SECRET_KEY"] = "KEY_FROM_ENV"
        config.external_config.handle_environment(self.context)
        self.assertEqual(config.server_config.app__flask_secret_key, "KEY_FROM_ENV")

    def test_handle_app__sets_web_base_url(self):
        config = self.get_config(web_base_url="anything.com")
        self.assertEqual(config.server_config.app__web_base_url, "anything.com")

    def test_handle_data_source__errors_when_passed_zero_or_two_dataroots(self):
        file_name = self.custom_app_config(
            dataroot=f"{FIXTURES_ROOT}",
            config_file_name="two_data_roots.yml",
                dataset_datapath=f"{FIXTURES_ROOT}/some_dataset.cxg",
        )
        config = AppConfig()
        config.update_from_config_file(file_name)
        with self.assertRaises(ConfigurationError):
            config.server_config.handle_data_source()

        file_name = self.custom_app_config(config_file_name="zero_roots.yml")
        config = AppConfig()
        config.update_from_config_file(file_name)
        with self.assertRaises(ConfigurationError):
            config.server_config.handle_data_source()

    @unittest.skip("skip when running in github action")
    def test_get_api_base_url_works(self):
        # test the api_base_url feature, and that it can contain a path
        config = AppConfig()
        backend_port = find_available_port("localhost", 10000)
        config.update_server_config(
            app__flask_secret_key="secret",
            app__api_base_url=f"http://localhost:{backend_port}/additional/path",
            multi_dataset__dataroot=f"{PROJECT_ROOT}/example-dataset",
            multi_dataset__allowed_matrix_types=["cxg"],
        )

        config.complete_config()
        server = self.create_app(config)
        server.testing = True
        session = server.test_client()
        response = session.get(f"/additional/path/d/pbmc3k.cxg/api/v0.2/config")

        self.assertEqual(response.status_code, 200)
        data_config = json.loads(response.data)
        self.assertEqual(data_config["config"]["displayNames"]["dataset"], "pbmc3k")

        # test the health check at the correct url
        response = session.get(f"/additional/path/health")
        assert json.loads(response.data)["status"] == "pass"

    def test_get_web_base_url_works(self):
        config = self.get_config(web_base_url="www.thisisawebsite.com")
        web_base_url = config.server_config.get_web_base_url()
        self.assertEqual(web_base_url, "www.thisisawebsite.com")

        config = self.get_config(web_base_url="local", port=12)
        web_base_url = config.server_config.get_web_base_url()
        self.assertEqual(web_base_url, "http://localhost:12")

        config = self.get_config(web_base_url="www.thisisawebsite.com/")
        web_base_url = config.server_config.get_web_base_url()
        self.assertEqual(web_base_url, "www.thisisawebsite.com")

        config = self.get_config(api_base_url="www.api_base.com/")
        web_base_url = config.server_config.get_web_base_url()
        self.assertEqual(web_base_url, "www.api_base.com")

    def test_config_for_single_dataset(self):
        file_name = self.custom_app_config(
            config_file_name="single_dataset.yml", dataset_datapath=f"{FIXTURES_ROOT}/pbmc3k.cxg"
        )
        config = AppConfig()
        config.update_from_config_file(file_name)
        config.server_config.handle_single_dataset(self.context)

        file_name = self.custom_app_config(
            config_file_name="single_dataset_with_about.yml",
            about="www.cziscience.com",
            dataset_datapath=f"{FIXTURES_ROOT}/pbmc3k.cxg",
        )
        config = AppConfig()
        config.update_from_config_file(file_name)
        with self.assertRaises(ConfigurationError):
            config.server_config.handle_single_dataset(self.context)

    def test_multi_dataset_raises_error_for_illegal_routes(self):
        # test for illegal url_dataroots
        for illegal in ("../b", "!$*", "\\n", "", "(bad)"):
            self.config.update_server_config(
                multi_dataset__dataroot={"tag": {"base_url": illegal, "dataroot": f"{PROJECT_ROOT}/example-dataset"}}
            )
            with self.assertRaises(ConfigurationError):
                self.config.complete_config()

    def test_multidataset_works_for_legal_routes(self):
        # test for legal url_dataroots
        for legal in ("d", "this.is-okay_", "a/b"):
            self.config.update_server_config(
                multi_dataset__dataroot={"tag": {"base_url": legal, "dataroot": f"{PROJECT_ROOT}/example-dataset"}}
            )
            self.config.complete_config()

    @patch("server.app.app.render_template")
    def test_mulitdatasets_work_e2e(self, mock_render_template):
        try:
            os.symlink(FIXTURES_ROOT, f"{FIXTURES_ROOT}/set2")
            os.symlink(FIXTURES_ROOT, f"{FIXTURES_ROOT}/set3")
        except FileExistsError:
            pass

        mock_render_template.return_value = "something"
        # test that multi dataroots work end to end
        self.config.update_server_config(
            multi_dataset__dataroot=dict(
                s1=dict(dataroot=f"{PROJECT_ROOT}/example-dataset", base_url="set1/1/2"),
                s2=dict(dataroot=f"{FIXTURES_ROOT}/set2", base_url="set2"),
                s3=dict(dataroot=f"{FIXTURES_ROOT}/set3", base_url="set3"),
            )
        )

        # Change this default to test if the dataroot overrides below work.
        self.config.update_default_dataset_config(app__about_legal_tos="tos_default.html")

        self.config.complete_config()

        server = self.create_app(self.config)
        server.testing = True
        session = server.test_client()

        response = session.get(f"/set1/1/2/pbmc3k.cxg/api/v0.2/config")

        data_config = json.loads(response.data)
        assert data_config["config"]["displayNames"]["dataset"] == "pbmc3k"

        response = session.get("/set2/pbmc3k.cxg/api/v0.2/config")

        data_config = json.loads(response.data)
        self.assertEqual(data_config["config"]["displayNames"]["dataset"], "pbmc3k")

        response = session.get("/set3/pbmc3k.cxg/api/v0.2/config")
        data_config = json.loads(response.data)
        self.assertEqual(data_config["config"]["displayNames"]["dataset"], "pbmc3k")

        response = session.get("/health")
        self.assertEqual(json.loads(response.data)["status"], "pass")

        # access a dataset (no slash)
        with self.subTest("access a dataset without a trailing a slash"):
            response = session.get("/set2/pbmc3k.cxg")
            self.assertEqual(response.status_code, 308)

        # access a dataset (with slash)
        with self.subTest("access a dataset with a slash"):
            response = session.get("/set2/pbmc3k.cxg/")
            self.assertEqual(response.status_code, 200)

        # cleanup
        os.unlink(f"{FIXTURES_ROOT}/set2")
        os.unlink(f"{FIXTURES_ROOT}/set3")

    @patch("server.common.config.server_config.diffexp_tiledb.set_config")
    def test_handle_diffexp(self, mock_tiledb_config):
        custom_config_file = self.custom_app_config(
            dataroot=f"{FIXTURES_ROOT}",
            cpu_multiplier=3,
            diffexp_max_workers=1,
            target_workunit=4,
            config_file_name=self.config_file_name,
        )
        config = AppConfig()
        config.update_from_config_file(custom_config_file)
        config.server_config.handle_diffexp()
        # called with the min of diffexp_max_workers and cpus*cpu_multiplier
        mock_tiledb_config.assert_called_once_with(1, 4)

    @patch("server.dataset.cxg_dataset.CxgDataset.set_tiledb_context")
    def test_handle_adaptor(self, mock_tiledb_context):
        custom_config = self.custom_app_config(
            dataroot=f"{FIXTURES_ROOT}", cxg_tile_cache_size=10, cxg_num_reader_threads=2
        )
        config = AppConfig()
        config.update_from_config_file(custom_config)
        config.server_config.handle_adaptor()
        mock_tiledb_context.assert_called_once_with(
            {"sm.tile_cache_size": 10, "sm.num_reader_threads": 2, "vfs.s3.region": "us-east-1"}
        )
