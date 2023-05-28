"Test deploy using an actual example."

import pytest
import cdktest
import json

pytestmark = pytest.mark.test_deploy


@pytest.fixture
def output(fixtures_dir):
    cdk = cdktest.CDKTest("custom", fixtures_dir, binary="npx cdk")
    return cdk.deploy()


def test_apply(output):
    print(output)
