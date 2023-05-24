# Python Test Helper for AWS CDK

This simple helper facilitates testing CDK constructs from Python unit tests, by wrapping the CDK executable and exposing convenience methods to set up fixtures, execute CDK commands, and parse their output.

It allows for different types of tests: lightweight tests that only use CDK `synthesize` to ensure code is syntactically correct and the right number and type of resources should be created, or full-fledged tests that run the full `deploy`/`destroy` cycle, and can then be used to test the actual created resources.

This tool is heavily inspired by this project: [terraform-python-testing-helper](https://github.com/GoogleCloudPlatform/terraform-python-testing-helper).

## Example Usage

The [`tests`](https://github.com/LEUNGUU/cdk-python-testing-helper/tree/main/tests) folder contains simple examples on how to write tests for both `synth` and `deploy`.

This is a test that uses synth output on an actual module:

```python
import pytest
import cdktest
import json


@pytest.fixture
def output(fixtures_dir):
    cdk = cdktest.CDKTest("custom", fixtures_dir, binary="npx cdk")
    return cdk.synthesize()


def test_apply(output):
    print(output)
```

## Testing

Tests use the `pytest` framework and have no other dependency except on the Python cdk library.
