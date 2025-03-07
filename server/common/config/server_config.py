import os
import sys
import warnings
from os.path import basename
from urllib.parse import urlparse, quote_plus

from server.common.config import DEFAULT_SERVER_PORT, BIG_FILE_SIZE_THRESHOLD
from server.common.config.base_config import BaseConfig
from server.common.errors import ConfigurationError, DatasetAccessError
from server.common.utils.data_locator import discover_s3_region_name
from server.common.utils.utils import is_port_available, find_available_port, custom_format_warning
from server.compute import diffexp_cxg as diffexp_tiledb
from server.dataset.matrix_loader import MatrixDataLoader, MatrixDataType


class ServerConfig(BaseConfig):
    """Manages the config attribute associated with the server."""

    def __init__(self, app_config, default_config):
        dictval_cases = [
            ("app", "csp_directives"),
            ("adaptor", "cxg_adaptor", "tiledb_ctx"),
            ("multi_dataset", "dataroot"),
        ]
        super().__init__(app_config, default_config, dictval_cases)

        try:
            self.app__verbose = default_config["app"]["verbose"]
            self.app__debug = default_config["app"]["debug"]
            self.app__host = default_config["app"]["host"]
            self.app__port = default_config["app"]["port"]
            self.app__open_browser = default_config["app"]["open_browser"]
            self.app__force_https = default_config["app"]["force_https"]
            self.app__flask_secret_key = default_config["app"]["flask_secret_key"]
            self.app__generate_cache_control_headers = default_config["app"]["generate_cache_control_headers"]
            self.app__server_timing_headers = default_config["app"]["server_timing_headers"]
            self.app__csp_directives = default_config["app"]["csp_directives"]
            self.app__api_base_url = default_config["app"]["api_base_url"]
            self.app__web_base_url = default_config["app"]["web_base_url"]

            self.multi_dataset__dataroot = default_config["multi_dataset"]["dataroot"]
            self.multi_dataset__index = default_config["multi_dataset"]["index"]
            self.multi_dataset__allowed_matrix_types = default_config["multi_dataset"]["allowed_matrix_types"]

            self.single_dataset__datapath = default_config["single_dataset"]["datapath"]
            self.single_dataset__obs_names = default_config["single_dataset"]["obs_names"]
            self.single_dataset__var_names = default_config["single_dataset"]["var_names"]
            self.single_dataset__about = default_config["single_dataset"]["about"]
            self.single_dataset__title = default_config["single_dataset"]["title"]

            self.diffexp__alg_cxg__max_workers = default_config["diffexp"]["alg_cxg"]["max_workers"]
            self.diffexp__alg_cxg__cpu_multiplier = default_config["diffexp"]["alg_cxg"]["cpu_multiplier"]
            self.diffexp__alg_cxg__target_workunit = default_config["diffexp"]["alg_cxg"]["target_workunit"]

            self.data_locator__s3__region_name = default_config["data_locator"]["s3"]["region_name"]
            self.data_locator__api_base = default_config["data_locator"]["api_base"]
            self.adaptor__cxg_adaptor__tiledb_ctx = default_config["adaptor"]["cxg_adaptor"]["tiledb_ctx"]

            self.limits__diffexp_cellcount_max = default_config["limits"]["diffexp_cellcount_max"]
            self.limits__column_request_max = default_config["limits"]["column_request_max"]

        except KeyError as e:
            raise ConfigurationError(f"Unexpected config: {str(e)}")

    def complete_config(self, context):
        self.handle_app(context)
        self.handle_data_source()
        self.handle_data_locator()
        self.handle_adaptor()  # may depend on data_locator
        self.handle_single_dataset(context)  # may depend on adaptor
        self.handle_multi_dataset()  # may depend on adaptor
        self.handle_diffexp()
        self.handle_limits()

        self.check_config()

    def handle_app(self, context):
        self.validate_correct_type_of_configuration_attribute("app__verbose", bool)
        self.validate_correct_type_of_configuration_attribute("app__debug", bool)
        self.validate_correct_type_of_configuration_attribute("app__host", str)
        self.validate_correct_type_of_configuration_attribute("app__port", (type(None), int))
        self.validate_correct_type_of_configuration_attribute("app__open_browser", bool)
        self.validate_correct_type_of_configuration_attribute("app__force_https", bool)
        self.validate_correct_type_of_configuration_attribute("app__flask_secret_key", str)
        self.validate_correct_type_of_configuration_attribute("app__generate_cache_control_headers", bool)
        self.validate_correct_type_of_configuration_attribute("app__server_timing_headers", bool)
        self.validate_correct_type_of_configuration_attribute("app__csp_directives", (type(None), dict))
        self.validate_correct_type_of_configuration_attribute("app__api_base_url", (type(None), str))
        self.validate_correct_type_of_configuration_attribute("app__web_base_url", (type(None), str))

        if self.app__port:
            try:
                if not is_port_available(self.app__host, self.app__port):
                    raise ConfigurationError(
                        f"The port selected {self.app__port} is in use, please configure an open port."
                    )
            except OverflowError:
                raise ConfigurationError(f"Invalid port: {self.app__port}")
        else:
            try:
                default_server_port = int(os.environ.get("CXG_SERVER_PORT", DEFAULT_SERVER_PORT))
            except ValueError:
                raise ConfigurationError(
                    "Invalid port from environment variable CXG_SERVER_PORT: " + os.environ.get("CXG_SERVER_PORT")
                )
            try:
                self.app__port = find_available_port(self.app__host, default_server_port)
            except OverflowError:
                raise ConfigurationError(f"Invalid port: {default_server_port}")

        if self.app__debug:
            context["messagefn"]("in debug mode, setting verbose=True and open_browser=False")
            self.app__verbose = True
            self.app__open_browser = False
        else:
            warnings.formatwarning = custom_format_warning

        if not self.app__verbose:
            sys.tracebacklimit = 0

        # CSP Directives are a dict of string: list(string) or string: string
        if self.app__csp_directives is not None:
            for k, v in self.app__csp_directives.items():
                if not isinstance(k, str):
                    raise ConfigurationError("CSP directive names must be a string.")
                if isinstance(v, list):
                    for policy in v:
                        if not isinstance(policy, str):
                            raise ConfigurationError("CSP directive value must be a string or list of strings.")
                elif not isinstance(v, str):
                    raise ConfigurationError("CSP directive value must be a string or list of strings.")

        if self.app__web_base_url is None:
            self.app__web_base_url = self.app__api_base_url

    def handle_data_locator(self):
        self.validate_correct_type_of_configuration_attribute("data_locator__s3__region_name", (type(None), bool, str))
        self.validate_correct_type_of_configuration_attribute("data_locator__api_base", (type(None), str))
        if self.data_locator__s3__region_name is True:
            path = self.single_dataset__datapath or self.multi_dataset__dataroot

            if type(path) == dict:
                # if multi_dataset__dataroot is a dict, then use the first key
                # that is in s3.   NOTE:  it is not supported to have dataroots
                # in different regions.
                paths = [val.get("dataroot") for val in path.values()]
                for path in paths:
                    if path.startswith("s3://"):
                        break
            if path.startswith("s3://"):
                region_name = discover_s3_region_name(path)
                if region_name is None:
                    raise ConfigurationError(f"Unable to discover s3 region name from {path}")
            else:
                region_name = None
            self.data_locator__s3__region_name = region_name

    def handle_data_source(self):
        self.validate_correct_type_of_configuration_attribute("single_dataset__datapath", (str, type(None)))
        self.validate_correct_type_of_configuration_attribute("multi_dataset__dataroot", (type(None), dict, str))

        if self.single_dataset__datapath and self.multi_dataset__dataroot:
            raise ConfigurationError(
                "You must supply either a datapath (for single datasets) or a dataroot (for multidatasets). Not both"
            )
        if self.single_dataset__datapath is None and self.multi_dataset__dataroot is None:
            raise ConfigurationError("You must specify a datapath for a single dataset or a dataroot for multidatasets")

    def handle_single_dataset(self, context):
        self.validate_correct_type_of_configuration_attribute("single_dataset__datapath", (str, type(None)))
        self.validate_correct_type_of_configuration_attribute("single_dataset__title", (str, type(None)))
        self.validate_correct_type_of_configuration_attribute("single_dataset__about", (str, type(None)))
        self.validate_correct_type_of_configuration_attribute("single_dataset__obs_names", (str, type(None)))
        self.validate_correct_type_of_configuration_attribute("single_dataset__var_names", (str, type(None)))

        if self.single_dataset__datapath is None:
            return

        # preload this data set
        matrix_data_loader = MatrixDataLoader(location=self.single_dataset__datapath, app_config=self.app_config)

        try:
            matrix_data_loader.pre_load_validation()
        except DatasetAccessError as e:
            raise ConfigurationError(str(e))

        file_size = matrix_data_loader.file_size()
        file_basename = basename(self.single_dataset__datapath)
        if file_size > BIG_FILE_SIZE_THRESHOLD:
            context["messagefn"](f"Loading data from {file_basename}, this may take a while...")
        else:
            context["messagefn"](f"Loading data from {file_basename}.")

        if self.single_dataset__about:

            def url_check(url):
                try:
                    result = urlparse(url)
                    if all([result.scheme, result.netloc]):
                        return True
                    else:
                        return False
                except ValueError:
                    return False

            if not url_check(self.single_dataset__about):
                raise ConfigurationError(
                    "Must provide an absolute URL for --about. (Example format: http://example.com)"
                )

    def handle_multi_dataset(self):
        self.validate_correct_type_of_configuration_attribute("multi_dataset__dataroot", (type(None), dict, str))
        self.validate_correct_type_of_configuration_attribute("multi_dataset__index", (type(None), bool, str))
        self.validate_correct_type_of_configuration_attribute("multi_dataset__allowed_matrix_types", list)

        if self.multi_dataset__dataroot is None:
            return

        if type(self.multi_dataset__dataroot) == str:
            default_dict = dict(base_url="d", dataroot=self.multi_dataset__dataroot)
            self.multi_dataset__dataroot = dict(d=default_dict)

        for tag, dataroot_dict in self.multi_dataset__dataroot.items():
            if "base_url" not in dataroot_dict:
                raise ConfigurationError(f"error in multi_dataset__dataroot: missing base_url for tag {tag}")
            if "dataroot" not in dataroot_dict:
                raise ConfigurationError(f"error in multi_dataset__dataroot: missing dataroot, for tag {tag}")

            base_url = dataroot_dict["base_url"]

            # sanity check for well formed base urls
            bad = False
            if type(base_url) != str:
                bad = True
            elif os.path.normpath(base_url) != base_url:
                bad = True
            else:
                base_url_parts = base_url.split("/")
                if [quote_plus(part) for part in base_url_parts] != base_url_parts:
                    bad = True
                if ".." in base_url_parts:
                    bad = True
            if bad:
                raise ConfigurationError(f"error in multi_dataset__dataroot base_url {base_url} for tag {tag}")

        # verify all the base_urls are unique
        base_urls = [d["base_url"] for d in self.multi_dataset__dataroot.values()]
        if len(base_urls) > len(set(base_urls)):
            raise ConfigurationError("error in multi_dataset__dataroot:  base_urls must be unique")

        # error checking
        for mtype in self.multi_dataset__allowed_matrix_types:
            try:
                MatrixDataType(mtype)
            except ValueError:
                raise ConfigurationError(f'Invalid matrix type in "allowed_matrix_types": {mtype}')

    def handle_diffexp(self):
        self.validate_correct_type_of_configuration_attribute("diffexp__alg_cxg__max_workers", (str, int))
        self.validate_correct_type_of_configuration_attribute("diffexp__alg_cxg__cpu_multiplier", int)
        self.validate_correct_type_of_configuration_attribute("diffexp__alg_cxg__target_workunit", int)

        max_workers = self.diffexp__alg_cxg__max_workers
        cpu_multiplier = self.diffexp__alg_cxg__cpu_multiplier
        cpu_count = os.cpu_count()
        max_workers = min(max_workers, cpu_multiplier * cpu_count)
        diffexp_tiledb.set_config(max_workers, self.diffexp__alg_cxg__target_workunit)

    def handle_adaptor(self):
        # cxg
        self.validate_correct_type_of_configuration_attribute("adaptor__cxg_adaptor__tiledb_ctx", dict)
        regionkey = "vfs.s3.region"
        if regionkey not in self.adaptor__cxg_adaptor__tiledb_ctx:
            if type(self.data_locator__s3__region_name) == str:
                self.adaptor__cxg_adaptor__tiledb_ctx[regionkey] = self.data_locator__s3__region_name

        from server.dataset.cxg_dataset import CxgDataset

        CxgDataset.set_tiledb_context(self.adaptor__cxg_adaptor__tiledb_ctx)

    def handle_limits(self):
        self.validate_correct_type_of_configuration_attribute("limits__diffexp_cellcount_max", (type(None), int))
        self.validate_correct_type_of_configuration_attribute("limits__column_request_max", (type(None), int))

    def exceeds_limit(self, limit_name, value):
        limit_value = getattr(self, "limits__" + limit_name, None)
        if limit_value is None:  # disabled
            return False
        return value > limit_value

    def get_api_base_url(self):
        if self.app__api_base_url == "local":
            return f"http://{self.app__host}:{self.app__port}"
        if self.app__api_base_url and self.app__api_base_url.endswith("/"):
            return self.app__api_base_url[:-1]
        return self.app__api_base_url

    def get_web_base_url(self):
        if self.app__web_base_url == "local":
            return f"http://{self.app__host}:{self.app__port}"
        if self.app__web_base_url is None:
            return self.get_api_base_url()
        if self.app__web_base_url.endswith("/"):
            return self.app__web_base_url[:-1]
        return self.app__web_base_url

    def get_data_locator_api_base_url(self):
        return self.data_locator__api_base
