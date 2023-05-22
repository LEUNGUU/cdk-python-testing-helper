"Test setup and apply using an actual example."

import pytest
import cdktest


@pytest.fixture
def output(fixtures_dir):
    cdk = cdktest.CDKTest("custom", fixtures_dir, binary="npx cdk")
    yield cdk.synthesize()


def test_apply(output):
    print("test")
