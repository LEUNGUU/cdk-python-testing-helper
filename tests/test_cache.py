"Test cache using an actual example."


import pytest
import cdktest
import logging
import shutil
import os
import uuid
from unittest.mock import patch


pytestmark = pytest.mark.test_cache


_LOGGER = logging.getLogger("cdktest")

cache_methods = ["synthesize", "deploy"]
no_cache_method = "destroy"


@pytest.fixture(scope="module")
def cdk(request, fixtures_dir):
    cdk = cdktest.CDKTest(
        appdir="no_change",
        basedir=fixtures_dir,
        binary="npx cdk",
        enable_cache=request.param,
    )
    yield cdk

    _LOGGER.debug("Removing cache dir")
    try:
        cdk.destroy()
        shutil.rmtree(cdk.cache_dir)
    except FileNotFoundError:
        _LOGGER.debug("%s does not exists", cdk.cache_dir)


@pytest.mark.parametrize("cdk", [True], indirect=True)
def test_use_cache(cdk):
    """
    Ensures cache is used and runs the execute_command() for first call of the
    method only
    """
    for method in cache_methods:
        with patch.object(
            cdk, "execute_command", wraps=cdk.execute_command
        ) as mock_execute_command:
            for _ in range(2):
                getattr(cdk, method)(use_cache=True)
            assert mock_execute_command.call_count == 1


@pytest.mark.parametrize("cdk", [False], indirect=True)
def test_not_use_cache(cdk):
    """
    Disable cache and runs the execute_command()
    """
    for method in cache_methods:
        with patch.object(
            cdk, "execute_command", wraps=cdk.execute_command
        ) as mock_execute_command:
            for _ in range(2):
                getattr(cdk, method)(use_cache=False)
            assert mock_execute_command.call_count == 2


@pytest.mark.parametrize("cdk", [True], indirect=True)
def test_use_cache_with_new_env(cdk):
    """
    Ensures cache is not used if the env attribute is updated
    before subsequent method calls
    """
    expected_call_count = 2
    for method in cache_methods:
        with patch.object(
            cdk, "execute_command", wraps=cdk.execute_command
        ) as mock_execute_command:
            for _ in range(expected_call_count):
                getattr(cdk, method)(use_cache=True)
                cdk.env["foo"] = "bar"

            assert mock_execute_command.call_count == expected_call_count

            del cdk.env["foo"]


@pytest.fixture
def dummy_cdk_filepath(cdk):
    filepath = os.path.join(cdk.appdir, "bar.txt")
    with open(filepath, "w") as f:
        f.write("old")

    yield filepath

    os.remove(filepath)


@pytest.mark.parametrize("cdk", [True], indirect=True)
def test_use_cache_with_new_cdk_content(cdk, dummy_cdk_filepath):
    """
    Ensures cache is not used if the appdir directory is updated
    before subsequent method calls
    """
    expected_call_count = 2
    for method in cache_methods:
        with patch.object(
            cdk, "execute_command", wraps=cdk.execute_command
        ) as mock_execute_command:
            for _ in range(expected_call_count):
                getattr(cdk, method)(use_cache=True)
                with open(dummy_cdk_filepath, "w") as f:
                    f.write(str(uuid.uuid4()))

            assert mock_execute_command.call_count == expected_call_count
