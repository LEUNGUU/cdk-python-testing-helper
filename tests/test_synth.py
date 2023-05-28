"Test synth using an actual example."

import pytest
import cdktest

pytestmark = pytest.mark.test_synth


@pytest.fixture
def output(fixtures_dir):
    cdk = cdktest.CDKTest("custom", fixtures_dir, binary="npx cdk", enable_cache=False)
    yield cdk.synthesize()


def test_vpc_properties(output):
    print(output.resources.keys())
    print(output.resources["AWS::EC2::VPC"])
    assert len(output.resources["AWS::EC2::VPC"]) == 1
    assert output.resources["AWS::EC2::VPC"][0]["CidrBlock"] == "10.0.0.0/16"


def test_subnet_properties(output):
    print(output.resources["AWS::EC2::Subnet"])
    assert len(output.resources["AWS::EC2::Subnet"]) == 4
