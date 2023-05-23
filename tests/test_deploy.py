"Test setup and apply using an actual example."

import pytest
import cdktest
import json


@pytest.fixture
def output(fixtures_dir):
    cdk = cdktest.CDKTest("custom", fixtures_dir, binary="npx cdk")
    return cdk.synthesize()


def test_apply(output):
    res = json.loads(output)
    print(res.keys())
