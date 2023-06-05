"Test deploy using an actual example."

import pytest
import cdktest
import json
import boto3

pytestmark = pytest.mark.test_deploy


iam_client = boto3.client("iam")


@pytest.fixture(scope="session")
def output(fixtures_dir):
    cdk = cdktest.CDKTest("iam", fixtures_dir, binary="npx cdk")
    cdk.deploy()
    yield cdk.synthesize()
    cdk.destroy()


@pytest.fixture(scope="session")
def iam_role(output):
    try:
        role = iam_client.get_role(
            RoleName=output.resources["AWS::IAM::Role"][0]["RoleName"]
        )
    except Exception as e:
        pytest.fail(
            f'Unable to find iam role with name {output.resources["AWS::IAM::Role"][0]["RoleName"]}, due to {e}'
        )
    return role["Role"]


@pytest.fixture(scope="session")
def output_role(output):
    return output.resources["AWS::IAM::Role"][0]


def test_role_name(iam_role, output_role):
    assert (
        output_role["RoleName"] == iam_role["RoleName"]
    ), f'Expected role name to be {output_role["RoleName"]}, got {iam_role["RoleName"]}'
