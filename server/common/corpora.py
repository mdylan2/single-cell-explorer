"""
Corpora schema conventions support.  Helper functions for reading.

https://github.com/chanzuckerberg/corpora-data-portal/blob/main/backend/schema/corpora_schema.md

https://github.com/chanzuckerberg/corpora-data-portal/blob/main/backend/schema/corpora_schema_h5ad_implementation.md
"""
import collections
import json
import re

from server.common.utils.corpora_constants import CorporaConstants


# Official SemVer regex: https://semver.org/
SEMVER_FORMAT = re.compile(
    r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)(?:-(?P<prerelease>(?:0|[1-9]\d*|\d*["
    r"a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?(?:\+(?P<buildmetadata>[0-9a-zA-Z-]+("
    r"?:\.[0-9a-zA-Z-]+)*))?$"
)


def validate_version_str(version_str, release_only=True):
    """
    Test if a string conforms to SemVer format (https://semver.org/)
    :param version_str: a string to be validated
    :param release_only: only declare releases (not prereleases) valid
    :return: True if the version string is of a valid SemVer format else False
    """
    match = SEMVER_FORMAT.match(version_str)
    has_match = match is not None
    if has_match and release_only:
        return not match.group("prerelease")
    return has_match


def corpora_get_versions_from_anndata(adata):
    """
    Given an AnnData object, return:
        * None - if not a Corpora object
        * [ corpora_schema_version, corpora_encoding_version ] - if a Corpora object

    Implements the identification protocol defined in the specification.
    """

    # per Corpora AnnData spec, this is a corpora file if the following is true
    if "version" not in adata.uns_keys():
        return None
    version = adata.uns["version"]
    if not isinstance(version, collections.abc.Mapping) or "corpora_schema_version" not in version:
        return None

    corpora_schema_version = version.get("corpora_schema_version")
    corpora_encoding_version = version.get("corpora_encoding_version")

    # TODO: spec says these must be SEMVER values, so check.
    if validate_version_str(corpora_schema_version) and validate_version_str(corpora_encoding_version):
        return [corpora_schema_version, corpora_encoding_version]


def corpora_is_version_supported(corpora_schema_version, corpora_encoding_version):
    return (
        corpora_schema_version
        and corpora_encoding_version
        and corpora_schema_version.startswith("1.")
        and corpora_encoding_version.startswith("0.1.")
    )


def corpora_get_props_from_anndata(adata):
    """
    Get Corpora dataset properties from an AnnData
    """
    versions = corpora_get_versions_from_anndata(adata)
    if versions is None:
        return None
    [corpora_schema_version, corpora_encoding_version] = versions
    version_is_supported = corpora_is_version_supported(corpora_schema_version, corpora_encoding_version)
    if not version_is_supported:
        raise ValueError("Unsupported Corpora schema version")

    corpora_props = {}
    for key in CorporaConstants.REQUIRED_SIMPLE_METADATA_FIELDS:
        if key not in adata.uns:
            raise KeyError(f"missing Corpora schema field {key}")
        corpora_props[key] = adata.uns[key]

    for key in CorporaConstants.OPTIONAL_JSON_ENCODED_METADATA_FIELD:
        if key not in adata.uns:
            continue
        try:
            corpora_props[key] = json.loads(adata.uns[key])
        except json.JSONDecodeError:
            raise json.JSONDecodeError(f"Corpora schema field {key} is expected to be a valid JSON string")

    for key in CorporaConstants.OPTIONAL_SIMPLE_METADATA_FIELDS:
        if key in adata.uns:
            corpora_props[key] = adata.uns[key]

    return corpora_props
