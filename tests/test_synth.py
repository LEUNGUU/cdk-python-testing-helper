"Test synth using an actual example."

import pytest
import cdktest
from collections import Counter

pytestmark = pytest.mark.test_synth


@pytest.fixture(scope="module")
def output(fixtures_dir):
    cdk = cdktest.CDKTest("lb", fixtures_dir, binary="npx cdk")
    yield cdk.synthesize()


@pytest.fixture(scope="module")
def vpc_output(output):
    return output.resources["AWS::EC2::VPC"]


@pytest.fixture(scope="module")
def subnet_output(output):
    return output.resources["AWS::EC2::Subnet"]


@pytest.fixture(scope="module")
def asg_output(output):
    return output.resources["AWS::AutoScaling::AutoScalingGroup"]


@pytest.fixture(scope="module")
def lb_output(output):
    return output.resources["AWS::ElasticLoadBalancing::LoadBalancer"]


@pytest.fixture(scope="module")
def lc_output(output):
    return output.resources["AWS::AutoScaling::LaunchConfiguration"]


def test_vpc_count(vpc_output):
    assert (
        len(vpc_output) == 1
    ), f"Expected number of vpc to be 1, got {len(vpc_output)}"


def test_vpc_cidr(vpc_output):
    assert (
        vpc_output[0]["CidrBlock"] == "10.0.0.0/16"
    ), f'Expected cidr to be 10.0.0.0/16, got {vpc_output[0]["CidrBlock"]}'


def test_subnet_count(subnet_output):
    assert (
        len(subnet_output) == 4
    ), f"Expected number of subnet to be 4, got {len(subnet_output)}"


def test_subnet_type(subnet_output):
    tag_list = map(lambda x: x["Tags"], subnet_output)
    type_count = Counter(
        [
            item["Value"]
            for sublist in tag_list
            for item in sublist
            if item["Key"] == "aws-cdk:subnet-type"
        ]
    )
    assert (
        type_count["Private"] == 2
    ), f'Expected number of Private subnet is 2, got {type_count["Private"]}'
    assert (
        type_count["Public"] == 2
    ), f'Expected number of Public subnet is 2, got {type_count["Public"]}'


def test_asg_maxsize(asg_output):
    assert asg_output[0]["MaxSize"] == str(
        1
    ), f'Expected asg maxsize is 1, got {asg_output[0]["MaxSize"]}'


def test_asg_minsize(asg_output):
    assert asg_output[0]["MinSize"] == str(
        1
    ), f'Expected asg minsize is 1, got {asg_output[0]["MinSize"]}'


def test_asg_instance_type(lc_output):
    assert (
        lc_output[0]["InstanceType"] == "t2.micro"
    ), f'Expected instance type is t2.micro, got {lc_output[0]["InstanceType"]}'


def test_lb_count(lb_output):
    assert (
        len(lb_output) == 1
    ), f"Expected number of load balancer is 1, got {len(lb_output)}"


def test_lb_scheme(lb_output):
    assert (
        lb_output[0]["Scheme"] == "internet-facing"
    ), f'Expected scheme of load balancer is internet-facing, got {lb_output[0]["scheme"]}'


def test_lb_healthcheck(lb_output):
    assert (
        lb_output[0]["HealthCheck"]["Target"] == "HTTP:80/"
    ), f'Expected health check target of load balancer is http:80, got {lb_output[0]["HealthCheck"]["Target"]}'
