import json
import os
import time
from http import HTTPStatus
import hashlib
from unittest.mock import patch

import requests

from server.common.config.app_config import AppConfig
from server.tests import decode_fbs, FIXTURES_ROOT
from server.tests.fixtures.fixtures import pbmc3k_colors
from server.tests.unit import BaseTest as _BaseTest, skip_if

BAD_FILTER = {"filter": {"obs": {"annotation_value": [{"name": "xyz"}]}}}

from urllib.parse import quote


class BaseTest(_BaseTest):
    @classmethod
    def setUpClass(cls, app_config=None):
        cls.TEST_S3_URI = f"{FIXTURES_ROOT}/pbmc3k.cxg"
        cls.TEST_S3_URI_ENCODED = cls.encode_s3_uri(cls.TEST_S3_URI)
        cls.TEST_DATASET_URL_BASE = f"/s3_uri/{cls.TEST_S3_URI_ENCODED}"
        cls.TEST_URL_BASE = f"{cls.TEST_DATASET_URL_BASE}/api/v0.3/"
        cls.maxDiff = None
        cls.app = cls.create_app(app_config)

    @staticmethod
    def encode_s3_uri(s3_uri):
        return quote(quote(s3_uri, safe=""), safe="")


class EndPoints(BaseTest):
    @classmethod
    def setUpClass(cls, app_config=None):
        super().setUpClass(app_config)
        cls.app.testing = True
        cls.client = cls.app.test_client()
        os.environ["SKIP_STATIC"] = "True"
        for i in range(90):
            try:
                result = cls.client.get(f"{cls.TEST_URL_BASE}schema")
                cls.schema = json.loads(result.data)
                break
            except requests.exceptions.ConnectionError:
                time.sleep(1)

    def test_initialize(self):
        endpoint = "schema"
        url = f"{self.TEST_URL_BASE}{endpoint}"
        result = self.client.get(url)
        self.assertEqual(result.status_code, HTTPStatus.OK)
        self.assertEqual(result.headers["Content-Type"], "application/json")
        result_data = json.loads(result.data)
        self.assertEqual(result_data["schema"]["dataframe"]["nObs"], 2638)
        self.assertEqual(len(result_data["schema"]["annotations"]["obs"]), 2)
        self.assertEqual(len(result_data["schema"]["annotations"]["obs"]["columns"]), 5)

    def test_config(self):
        endpoint = "config"
        url = f"{self.TEST_URL_BASE}{endpoint}"
        result = self.client.get(url)
        self.assertEqual(result.status_code, HTTPStatus.OK)
        self.assertEqual(result.headers["Content-Type"], "application/json")
        result_data = json.loads(result.data)
        self.assertIn("library_versions", result_data["config"])
        self.assertEqual(result_data["config"]["displayNames"]["dataset"], "pbmc3k")

    def test_get_layout_fbs(self):
        endpoint = "layout/obs"
        url = f"{self.TEST_URL_BASE}{endpoint}"
        header = {"Accept": "application/octet-stream"}
        result = self.client.get(url, headers=header)
        self.assertEqual(result.status_code, HTTPStatus.OK)
        self.assertEqual(result.headers["Content-Type"], "application/octet-stream")
        df = decode_fbs.decode_matrix_FBS(result.data)
        self.assertEqual(df["n_rows"], 2638)
        self.assertEqual(df["n_cols"], 8)
        self.assertIsNotNone(df["columns"])
        self.assertSetEqual(
            set(df["col_idx"]),
            {"pca_0", "pca_1", "tsne_0", "tsne_1", "umap_0", "umap_1", "draw_graph_fr_0", "draw_graph_fr_1"},
        )
        self.assertIsNone(df["row_idx"])
        self.assertEqual(len(df["columns"]), df["n_cols"])

    def test_bad_filter(self):
        endpoint = "data/var"
        url = f"{self.TEST_URL_BASE}{endpoint}"
        header = {"Accept": "application/octet-stream"}
        result = self.client.put(url, headers=header, json=BAD_FILTER)
        self.assertEqual(result.status_code, HTTPStatus.BAD_REQUEST)

    def test_get_annotations_obs_fbs(self):
        endpoint = "annotations/obs"
        url = f"{self.TEST_URL_BASE}{endpoint}"
        header = {"Accept": "application/octet-stream"}
        result = self.client.get(url, headers=header)
        self.assertEqual(result.status_code, HTTPStatus.OK)
        self.assertEqual(result.headers["Content-Type"], "application/octet-stream")
        df = decode_fbs.decode_matrix_FBS(result.data)
        self.assertEqual(df["n_rows"], 2638)
        self.assertEqual(df["n_cols"], 5)
        self.assertIsNotNone(df["columns"])
        self.assertIsNone(df["row_idx"])
        self.assertEqual(len(df["columns"]), df["n_cols"])
        obs_index_col_name = self.schema["schema"]["annotations"]["obs"]["index"]
        self.assertCountEqual(
            df["col_idx"],
            [obs_index_col_name, "n_genes", "percent_mito", "n_counts", "louvain"],
        )

    def test_get_annotations_obs_keys_fbs(self):
        endpoint = "annotations/obs"
        query = "annotation-name=n_genes&annotation-name=percent_mito"
        url = f"{self.TEST_URL_BASE}{endpoint}?{query}"
        header = {"Accept": "application/octet-stream"}
        result = self.client.get(url, headers=header)
        self.assertEqual(result.status_code, HTTPStatus.OK)
        self.assertEqual(result.headers["Content-Type"], "application/octet-stream")
        df = decode_fbs.decode_matrix_FBS(result.data)
        self.assertEqual(df["n_rows"], 2638)
        self.assertEqual(df["n_cols"], 2)
        self.assertIsNotNone(df["columns"])
        self.assertIsNone(df["row_idx"])
        self.assertEqual(len(df["columns"]), df["n_cols"])
        self.assertCountEqual(df["col_idx"], ["n_genes", "percent_mito"])

    def test_get_annotations_obs_error(self):
        endpoint = "annotations/obs"
        query = "annotation-name=notakey"
        url = f"{self.TEST_URL_BASE}{endpoint}?{query}"
        header = {"Accept": "application/octet-stream"}
        result = self.client.get(url, headers=header)
        self.assertEqual(result.status_code, HTTPStatus.BAD_REQUEST)

    # TEMP: Testing count 15 to match hardcoded values for diffexp
    # TODO(#1281): Switch back to dynamic values
    def test_diff_exp(self):
        endpoint = "diffexp/obs"
        url = f"{self.TEST_URL_BASE}{endpoint}"
        params = {
            "mode": "topN",
            "set1": {"filter": {"obs": {"annotation_value": [{"name": "louvain", "values": ["NK cells"]}]}}},
            "set2": {"filter": {"obs": {"annotation_value": [{"name": "louvain", "values": ["CD8 T cells"]}]}}},
            "count": 15,
        }
        result = self.client.post(url, json=params)
        self.assertEqual(result.status_code, HTTPStatus.OK)
        self.assertEqual(result.headers["Content-Type"], "application/json")
        result_data = json.loads(result.data)
        self.assertEqual(len(result_data["positive"]), 15)
        self.assertEqual(len(result_data["negative"]), 15)

    def test_diff_exp_indices(self):
        endpoint = "diffexp/obs"
        url = f"{self.TEST_URL_BASE}{endpoint}"
        params = {
            "mode": "topN",
            "count": 15,
            "set1": {"filter": {"obs": {"index": [[0, 500]]}}},
            "set2": {"filter": {"obs": {"index": [[500, 1000]]}}},
        }
        result = self.client.post(url, json=params)
        self.assertEqual(result.status_code, HTTPStatus.OK)
        self.assertEqual(result.headers["Content-Type"], "application/json")
        result_data = json.loads(result.data)
        self.assertEqual(len(result_data["positive"]), 15)
        self.assertEqual(len(result_data["negative"]), 15)

    def test_get_annotations_var_fbs(self):
        endpoint = "annotations/var"
        url = f"{self.TEST_URL_BASE}{endpoint}"
        header = {"Accept": "application/octet-stream"}
        result = self.client.get(url, headers=header)
        self.assertEqual(result.status_code, HTTPStatus.OK)
        self.assertEqual(result.headers["Content-Type"], "application/octet-stream")
        df = decode_fbs.decode_matrix_FBS(result.data)
        self.assertEqual(df["n_rows"], 1838)
        self.assertEqual(df["n_cols"], 2)
        self.assertIsNotNone(df["columns"])
        self.assertIsNone(df["row_idx"])
        self.assertEqual(len(df["columns"]), df["n_cols"])
        var_index_col_name = self.schema["schema"]["annotations"]["var"]["index"]
        self.assertCountEqual(df["col_idx"], [var_index_col_name, "n_cells"])

    def test_get_annotations_var_keys_fbs(self):
        endpoint = "annotations/var"
        query = "annotation-name=n_cells"
        url = f"{self.TEST_URL_BASE}{endpoint}?{query}"
        header = {"Accept": "application/octet-stream"}
        result = self.client.get(url, headers=header)
        self.assertEqual(result.status_code, HTTPStatus.OK)
        self.assertEqual(result.headers["Content-Type"], "application/octet-stream")
        df = decode_fbs.decode_matrix_FBS(result.data)
        self.assertEqual(df["n_rows"], 1838)
        self.assertEqual(df["n_cols"], 1)
        self.assertIsNotNone(df["columns"])
        self.assertIsNone(df["row_idx"])
        self.assertEqual(len(df["columns"]), df["n_cols"])
        self.assertCountEqual(df["col_idx"], ["n_cells"])

    def test_get_annotations_var_error(self):
        endpoint = "annotations/var"
        query = "annotation-name=notakey"
        url = f"{self.TEST_URL_BASE}{endpoint}?{query}"
        header = {"Accept": "application/octet-stream"}
        result = self.client.get(url, headers=header)
        self.assertEqual(result.status_code, HTTPStatus.BAD_REQUEST)

    def test_data_mimetype_error(self):
        endpoint = "data/var"
        header = {"Accept": "xxx"}
        url = f"{self.TEST_URL_BASE}{endpoint}"
        result = self.client.put(url, headers=header)
        self.assertEqual(result.status_code, HTTPStatus.NOT_ACCEPTABLE)

    def test_fbs_default(self):
        endpoint = "data/var"
        url = f"{self.TEST_URL_BASE}{endpoint}"
        headers = {"Accept": "application/octet-stream"}
        result = self.client.put(url, headers=headers)
        self.assertEqual(result.status_code, HTTPStatus.BAD_REQUEST)

        filter = {"filter": {"var": {"index": [0, 1, 4]}}}
        result = self.client.put(url, headers=headers, json=filter)
        self.assertEqual(result.headers["Content-Type"], "application/octet-stream")

    def test_data_put_fbs(self):
        endpoint = "data/var"
        url = f"{self.TEST_URL_BASE}{endpoint}"
        header = {"Accept": "application/octet-stream"}
        result = self.client.put(url, headers=header)
        self.assertEqual(result.status_code, HTTPStatus.BAD_REQUEST)

    def test_data_get_fbs(self):
        endpoint = "data/var"
        url = f"{self.TEST_URL_BASE}{endpoint}"
        header = {"Accept": "application/octet-stream"}
        result = self.client.get(url, headers=header)
        self.assertEqual(result.status_code, HTTPStatus.BAD_REQUEST)

    def test_data_put_filter_fbs(self):
        endpoint = "data/var"
        url = f"{self.TEST_URL_BASE}{endpoint}"
        header = {"Accept": "application/octet-stream"}
        filter = {"filter": {"var": {"index": [0, 1, 4]}}}
        result = self.client.put(url, headers=header, json=filter)
        self.assertEqual(result.status_code, HTTPStatus.OK)
        self.assertEqual(result.headers["Content-Type"], "application/octet-stream")
        df = decode_fbs.decode_matrix_FBS(result.data)
        self.assertEqual(df["n_rows"], 2638)
        self.assertEqual(df["n_cols"], 3)
        self.assertIsNotNone(df["columns"])
        self.assertIsNone(df["row_idx"])
        self.assertEqual(len(df["columns"]), df["n_cols"])
        self.assertListEqual(df["col_idx"].tolist(), [0, 1, 4])

    def test_data_get_filter_fbs(self):
        index_col_name = self.schema["schema"]["annotations"]["var"]["index"]
        endpoint = "data/var"
        query = f"var:{index_col_name}=SIK1"
        url = f"{self.TEST_URL_BASE}{endpoint}?{query}"
        header = {"Accept": "application/octet-stream"}
        result = self.client.get(url, headers=header)
        self.assertEqual(result.status_code, HTTPStatus.OK)
        self.assertEqual(result.headers["Content-Type"], "application/octet-stream")
        df = decode_fbs.decode_matrix_FBS(result.data)
        self.assertEqual(df["n_rows"], 2638)
        self.assertEqual(df["n_cols"], 1)

    def test_data_get_unknown_filter_fbs(self):
        index_col_name = self.schema["schema"]["annotations"]["var"]["index"]
        endpoint = "data/var"
        query = f"var:{index_col_name}=UNKNOWN"
        url = f"{self.TEST_URL_BASE}{endpoint}?{query}"
        header = {"Accept": "application/octet-stream"}
        result = self.client.get(url, headers=header)
        self.assertEqual(result.status_code, HTTPStatus.OK)
        self.assertEqual(result.headers["Content-Type"], "application/octet-stream")
        df = decode_fbs.decode_matrix_FBS(result.data)
        self.assertEqual(df["n_rows"], 2638)
        self.assertEqual(df["n_cols"], 0)

    def test_data_put_single_var(self):
        endpoint = "data/var"
        url = f"{self.TEST_URL_BASE}{endpoint}"
        header = {"Accept": "application/octet-stream"}
        index_col_name = self.schema["schema"]["annotations"]["var"]["index"]
        var_filter = {"filter": {"var": {"annotation_value": [{"name": index_col_name, "values": ["RER1"]}]}}}
        result = self.client.put(url, headers=header, json=var_filter)
        self.assertEqual(result.status_code, HTTPStatus.OK)
        self.assertEqual(result.headers["Content-Type"], "application/octet-stream")
        df = decode_fbs.decode_matrix_FBS(result.data)
        self.assertEqual(df["n_rows"], 2638)
        self.assertEqual(df["n_cols"], 1)

    def test_colors(self):
        endpoint = "colors"
        url = f"{self.TEST_URL_BASE}{endpoint}"
        result = self.client.get(url)
        self.assertEqual(result.status_code, HTTPStatus.OK)
        self.assertEqual(result.headers["Content-Type"], "application/json")
        result_data = json.loads(result.data)
        self.assertEqual(result_data, pbmc3k_colors)

    @skip_if(lambda x: os.getenv("SKIP_STATIC"), "Skip static test when running locally")
    def test_static(self):
        endpoint = "static"
        file = "assets/favicon.ico"
        url = f"{endpoint}/{file}"
        result = self.client.get(url)
        self.assertEqual(result.status_code, HTTPStatus.OK)

    def test_genesets_config(self):
        result = self.client.get(f"{self.TEST_URL_BASE}config")
        config_data = json.loads(result.data)
        params = config_data["config"]["parameters"]
        annotations_genesets = params["annotations_genesets"]
        annotations_genesets_readonly = params["annotations_genesets_readonly"]
        annotations_genesets_summary_methods = params["annotations_genesets_summary_methods"]
        self.assertTrue(annotations_genesets)
        self.assertTrue(annotations_genesets_readonly)
        self.assertEqual(annotations_genesets_summary_methods, ["mean"])

    def test_get_genesets(self):
        endpoint = "genesets"
        url = f"{self.TEST_URL_BASE}{endpoint}"
        result = self.client.get(url, headers={"Accept": "application/json"})
        self.assertEqual(result.status_code, HTTPStatus.OK)
        self.assertEqual(result.headers["Content-Type"], "application/json")
        result_data = json.loads(result.data)
        self.assertIsNotNone(result_data["genesets"])

    def test_get_summaryvar(self):
        index_col_name = self.schema["schema"]["annotations"]["var"]["index"]
        endpoint = "summarize/var"

        # single column
        filter = f"var:{index_col_name}=F5"
        query = f"method=mean&{filter}"
        query_hash = hashlib.sha1(query.encode()).hexdigest()
        url = f"{self.TEST_URL_BASE}{endpoint}?{query}"
        header = {"Accept": "application/octet-stream"}
        result = self.client.get(url, headers=header)
        self.assertEqual(result.status_code, HTTPStatus.OK)
        self.assertEqual(result.headers["Content-Type"], "application/octet-stream")
        df = decode_fbs.decode_matrix_FBS(result.data)
        self.assertEqual(df["n_rows"], 2638)
        self.assertEqual(df["n_cols"], 1)
        self.assertEqual(df["col_idx"], [query_hash])
        self.assertAlmostEqual(df["columns"][0][0], -0.110451095)

        # multi-column
        col_names = ["F5", "BEB3", "SIK1"]
        filter = "&".join([f"var:{index_col_name}={name}" for name in col_names])
        query = f"method=mean&{filter}"
        query_hash = hashlib.sha1(query.encode()).hexdigest()
        url = f"{self.TEST_URL_BASE}{endpoint}?{query}"
        header = {"Accept": "application/octet-stream"}
        result = self.client.get(url, headers=header)
        self.assertEqual(result.status_code, HTTPStatus.OK)
        self.assertEqual(result.headers["Content-Type"], "application/octet-stream")
        df = decode_fbs.decode_matrix_FBS(result.data)
        self.assertEqual(df["n_rows"], 2638)
        self.assertEqual(df["n_cols"], 1)
        self.assertEqual(df["col_idx"], [query_hash])
        self.assertAlmostEqual(df["columns"][0][0], -0.16628358)

    def test_post_summaryvar(self):
        index_col_name = self.schema["schema"]["annotations"]["var"]["index"]
        endpoint = "summarize/var"
        headers = {"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/octet-stream"}

        # single column
        filter = f"var:{index_col_name}=F5"
        query = f"method=mean&{filter}"
        query_hash = hashlib.sha1(query.encode()).hexdigest()
        url = f"{self.TEST_URL_BASE}{endpoint}?key={query_hash}"
        result = self.client.post(url, headers=headers, data=query)

        self.assertEqual(result.status_code, HTTPStatus.OK)
        self.assertEqual(result.headers["Content-Type"], "application/octet-stream")
        df = decode_fbs.decode_matrix_FBS(result.data)
        self.assertEqual(df["n_rows"], 2638)
        self.assertEqual(df["n_cols"], 1)
        self.assertEqual(df["col_idx"], [query_hash])
        self.assertAlmostEqual(df["columns"][0][0], -0.110451095)

        # multi-column
        col_names = ["F5", "BEB3", "SIK1"]
        filter = "&".join([f"var:{index_col_name}={name}" for name in col_names])
        query = f"method=mean&{filter}"
        query_hash = hashlib.sha1(query.encode()).hexdigest()
        url = f"{self.TEST_URL_BASE}{endpoint}?key={query_hash}"
        result = self.client.post(url, headers=headers, data=query)
        self.assertEqual(result.status_code, HTTPStatus.OK)
        self.assertEqual(result.headers["Content-Type"], "application/octet-stream")
        df = decode_fbs.decode_matrix_FBS(result.data)
        self.assertEqual(df["n_rows"], 2638)
        self.assertEqual(df["n_cols"], 1)
        self.assertEqual(df["col_idx"], [query_hash])
        self.assertAlmostEqual(df["columns"][0][0], -0.16628358)


class TestDatasetMetadata(BaseTest):
    @classmethod
    def setUpClass(cls):
        cls.data_locator_api_base = "api.cellxgene.staging.single-cell.czi.technology/dp/v1"
        cls.app__web_base_url = "https://cellxgene.staging.single-cell.czi.technology/"
        cls.config = AppConfig()
        cls.config.update_server_config(
            data_locator__api_base=cls.data_locator_api_base,
            app__web_base_url=cls.app__web_base_url,
            multi_dataset__dataroot={"e": {"base_url": "e", "dataroot": FIXTURES_ROOT}},
            app__flask_secret_key="testing",
            app__debug=True,
            data_locator__s3__region_name="us-east-1",
        )
        cls.meta_response_body = {
            "collection_id": "4f098ff4-4a12-446b-a841-91ba3d8e3fa6",
            "collection_visibility": "PUBLIC",
            "dataset_id": "2fa37b10-ab4d-49c9-97a8-b4b3d80bf939",
            "s3_uri": f"{FIXTURES_ROOT}/pbmc3k.cxg",
            "tombstoned": False,
        }
        super().setUpClass(cls.config)

        cls.app.testing = True
        cls.client = cls.app.test_client()

    @patch("server.dataset.dataset_metadata.request_dataset_metadata_from_data_portal")
    @patch("server.dataset.dataset_metadata.requests.get")
    def test_dataset_metadata_api_called_for_public_collection(self, mock_get, mock_dp):
        self.TEST_DATASET_URL_BASE = "/e/pbmc3k_v0_public.cxg"
        self.TEST_URL_BASE = f"{self.TEST_DATASET_URL_BASE}/api/v0.3/"

        response_body = {
            "contact_email": "test_email",
            "contact_name": "test_user",
            "datasets": [
                {
                    "collection_visibility": "PUBLIC",
                    "id": "2fa37b10-ab4d-49c9-97a8-b4b3d80bf939",
                    "name": "Test Dataset",
                },
            ],
            "description": "test_description",
            "id": "4f098ff4-4a12-446b-a841-91ba3d8e3fa6",
            "links": [
                "http://test.link",
            ],
            "name": "Test Collection",
            "visibility": "PUBLIC",
        }

        mock_get.return_value = MockResponse(body=json.dumps(response_body), status_code=200)
        mock_dp.return_value = self.meta_response_body

        endpoint = "dataset-metadata"
        url = f"{self.TEST_URL_BASE}{endpoint}"
        result = self.client.get(url)

        self.assertEqual(result.status_code, HTTPStatus.OK)
        self.assertEqual(result.headers["Content-Type"], "application/json")

        self.assertEqual(mock_get.call_count, 1)

        response_obj = json.loads(result.data)["metadata"]

        self.assertEqual(response_obj["dataset_name"], "Test Dataset")

        expected_url = f"https://cellxgene.staging.single-cell.czi.technology/collections/{response_body['id']}"
        self.assertEqual(response_obj["dataset_id"], response_body["datasets"][0]["id"])
        self.assertEqual(response_obj["collection_url"], expected_url)
        self.assertEqual(response_obj["collection_name"], response_body["name"])
        self.assertEqual(response_obj["collection_contact_email"], response_body["contact_email"])
        self.assertEqual(response_obj["collection_contact_name"], response_body["contact_name"])
        self.assertEqual(response_obj["collection_description"], response_body["description"])
        self.assertEqual(response_obj["collection_links"], response_body["links"])
        self.assertEqual(response_obj["collection_datasets"], response_body["datasets"])

    @patch("server.dataset.dataset_metadata.request_dataset_metadata_from_data_portal")
    @patch("server.dataset.dataset_metadata.requests.get")
    def test_dataset_metadata_api_called_for_private_collection(self, mock_get, mock_dp):
        self.TEST_DATASET_URL_BASE = "/e/pbmc3k_v0_private.cxg"
        self.TEST_URL_BASE = f"{self.TEST_DATASET_URL_BASE}/api/v0.3/"

        response_body = {
            "contact_email": "test_email",
            "contact_name": "test_user",
            "datasets": [
                {
                    "collection_visibility": "PRIVATE",
                    "id": "2fa37b10-ab4d-49c9-97a8-b4b3d80bf939",
                    "name": "Test Dataset",
                },
            ],
            "description": "test_description",
            "id": "4f098ff4-4a12-446b-a841-91ba3d8e3fa6",
            "links": [
                "http://test.link",
            ],
            "name": "Test Collection",
            "visibility": "PRIVATE",
        }

        mock_get.return_value = MockResponse(body=json.dumps(response_body), status_code=200)
        meta_response_body_private = self.meta_response_body.copy()
        meta_response_body_private["collection_visibility"] = "PRIVATE"
        mock_dp.return_value = meta_response_body_private

        endpoint = "dataset-metadata"
        url = f"{self.TEST_URL_BASE}{endpoint}"
        result = self.client.get(url)

        self.assertEqual(result.status_code, HTTPStatus.OK)
        self.assertEqual(result.headers["Content-Type"], "application/json")

        self.assertEqual(mock_get.call_count, 1)

        response_obj = json.loads(result.data)["metadata"]

        self.assertEqual(response_obj["dataset_name"], "Test Dataset")

        expected_url = f"https://cellxgene.staging.single-cell.czi.technology/collections/{response_body['id']}/private"
        self.assertEqual(response_obj["dataset_id"], response_body["datasets"][0]["id"])
        self.assertEqual(response_obj["collection_url"], expected_url)
        self.assertEqual(response_obj["collection_name"], response_body["name"])
        self.assertEqual(response_obj["collection_contact_email"], response_body["contact_email"])
        self.assertEqual(response_obj["collection_contact_name"], response_body["contact_name"])
        self.assertEqual(response_obj["collection_description"], response_body["description"])
        self.assertEqual(response_obj["collection_links"], response_body["links"])
        self.assertEqual(response_obj["collection_datasets"], response_body["datasets"])

    @patch("server.dataset.dataset_metadata.request_dataset_metadata_from_data_portal")
    def test_dataset_metadata_api_fails_gracefully_on_dataset_not_found(self, mock_dp):
        # Force a new dataset name, otherwise a cache entry will be found and the mock will not be applied
        self.TEST_DATASET_URL_BASE = "/e/pbmc3k_v0_2.cxg"
        self.TEST_URL_BASE = f"{self.TEST_DATASET_URL_BASE}/api/v0.3/"

        # If request_dataset_metadata_from_data_portal, it always returns None
        mock_dp.return_value = None

        endpoint = "dataset-metadata"
        url = f"{self.TEST_URL_BASE}{endpoint}"
        result = self.client.get(url)

        self.assertEqual(result.status_code, HTTPStatus.NOT_FOUND)

    @patch("server.dataset.dataset_metadata.request_dataset_metadata_from_data_portal")
    @patch("server.dataset.dataset_metadata.requests.get")
    def test_dataset_metadata_api_fails_gracefully_on_connection_failure(self, mock_get, mock_dp):
        self.TEST_DATASET_URL_BASE = "/e/pbmc3k_v0.cxg"
        self.TEST_URL_BASE = f"{self.TEST_DATASET_URL_BASE}/api/v0.3/"

        mock_dp.return_value = self.meta_response_body
        mock_get.side_effect = Exception("Cannot connect to the data portal")

        endpoint = "dataset-metadata"
        url = f"{self.TEST_URL_BASE}{endpoint}"
        result = self.client.get(url)

        self.assertEqual(result.status_code, HTTPStatus.BAD_REQUEST)


class TestConfigEndpoint(BaseTest):
    @classmethod
    def setUpClass(cls):
        cls.data_locator_api_base = "api.cellxgene.staging.single-cell.czi.technology/dp/v1"
        cls.app__web_base_url = "https://cellxgene.staging.single-cell.czi.technology/"
        cls.config = AppConfig()
        cls.config.update_server_config(
            data_locator__api_base=cls.data_locator_api_base,
            app__web_base_url=cls.app__web_base_url,
            multi_dataset__dataroot={"e": {"base_url": "e", "dataroot": FIXTURES_ROOT}},
            app__flask_secret_key="testing",
            app__debug=True,
            data_locator__s3__region_name="us-east-1",
        )
        super().setUpClass(cls.config)

        cls.app.testing = True
        cls.client = cls.app.test_client()

    def test_config_has_collections_home_page(self):
        endpoint = "config"
        url = f"{self.TEST_URL_BASE}{endpoint}"
        result = self.client.get(url)
        self.assertEqual(result.status_code, HTTPStatus.OK)
        self.assertEqual(result.headers["Content-Type"], "application/json")
        result_data = json.loads(result.data)
        self.assertEqual(result_data["config"]["links"]["collections-home-page"], self.app__web_base_url[:-1])


class TestS3URI(BaseTest):
    @classmethod
    def setUpClass(cls):
        cls.data_locator_api_base = "api.cellxgene.staging.single-cell.czi.technology/dp/v1"
        cls.app__web_base_url = "https://cellxgene.staging.single-cell.czi.technology/"
        cls.config = AppConfig()
        cls.config.update_server_config(
            data_locator__api_base=cls.data_locator_api_base,
            app__web_base_url=cls.app__web_base_url,
            multi_dataset__dataroot={"e": {"base_url": "e", "dataroot": FIXTURES_ROOT}},
            app__flask_secret_key="testing",
            app__debug=True,
            data_locator__s3__region_name="us-east-1",
        )
        super().setUpClass(cls.config)

        cls.app.testing = True
        cls.client = cls.app.test_client()

        endpoint = "s3_uri"
        test_dataset_url_base = "/e/pbmc3k_v0.cxg"
        test_url_base = f"{test_dataset_url_base}/api/v0.3/"

        cls.url = f"{test_url_base}{endpoint}"

    @patch("server.dataset.dataset_metadata.requests.get")
    def test_get_S3_URI_in_data_portal(self, mock_get):
        test_s3_uris = [
            (f"{FIXTURES_ROOT}/pbmc3k.cxg", f"{FIXTURES_ROOT}/pbmc3k.cxg"),
            (f"{FIXTURES_ROOT}/pbmc3k.cxg/", f"{FIXTURES_ROOT}/pbmc3k.cxg"),
            (None, None),
        ]
        test_response_body = {
            "collection_id": "4f098ff4-4a12-446b-a841-91ba3d8e3fa6",
            "collection_visibility": "PUBLIC",
            "dataset_id": "2fa37b10-ab4d-49c9-97a8-b4b3d80bf939",
            "tombstoned": False,
        }
        for actual, expected in test_s3_uris:
            with self.subTest(actual):
                test_response_body["s3_uri"] = actual
                response_body = json.dumps(test_response_body)
                mock_get.return_value = MockResponse(body=response_body, status_code=200)

                result = self.client.get(self.url)
                self.assertEqual(result.status_code, HTTPStatus.OK)
                self.assertEqual(json.loads(result.data), expected)

    @patch("server.dataset.dataset_metadata.requests.get")
    def test_get_S3_URI_not_in_data_portal(self, mock_get):
        mock_get.return_value = MockResponse(body="", status_code=404)
        result = self.client.get(self.url)
        self.assertEqual(result.status_code, HTTPStatus.OK)
        self.assertIsNotNone(json.loads(result.data))

    @patch("server.dataset.dataset_metadata.requests.get")
    def test_tombstoned_datasets_redirect_to_data_portal(self, mock_get):
        response_body = json.dumps(
            {
                "collection_id": "4f098ff4-4a12-446b-a841-91ba3d8e3fa6",
                "collection_visibility": "PUBLIC",
                "dataset_id": "2fa37b10-ab4d-49c9-97a8-b4b3d80bf939",
                "s3_uri": None,
                "tombstoned": True,
            }
        )
        mock_get.return_value = MockResponse(body=response_body, status_code=200)
        endpoint = "s3_uri"
        self.TEST_DATASET_URL_BASE = "/e/pbmc3k_v2.cxg"
        url = f"{self.TEST_DATASET_URL_BASE}/api/v0.3/{endpoint}"
        result = self.client.get(url)
        self.assertEqual(result.status_code, 302)
        self.assertEqual(
            result.headers["Location"],
            "https://cellxgene.staging.single-cell.czi.technology/collections/4f098ff4-4a12-446b-a841-91ba3d8e3fa6?tombstoned_dataset_id=2fa37b10-ab4d-49c9-97a8-b4b3d80bf939",
        )  # noqa E501


class MockResponse:
    def __init__(self, body, status_code):
        self.content = body
        self.status_code = status_code

    def json(self):
        return json.loads(self.content)
