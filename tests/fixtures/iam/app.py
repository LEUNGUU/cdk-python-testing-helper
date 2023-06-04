from aws_cdk import (
    aws_iam as iam,
    App,
    Stack,
)


class IAMStack(Stack):
    def __init__(self, app: App, id: str, **kwargs) -> None:
        super().__init__(app, id, **kwargs)

        role_inline_policy = iam.Policy(
            self,
            "cdk-python-testing-helper-policy",
            policy_name="cdk-python-testing-helper-policy",
            statements=[
                iam.PolicyStatement(
                    actions=[
                        "sts:AssumeRole",
                    ],
                    resources=["arn:aws:iam::*:role/cdk-hnb659fds-lookup-role-*"],
                ),
            ],
        )
        role = iam.Role(
            self,
            "cdk-python-testing-helper",
            role_name="cdk-python-testing-helper",
            inline_policies={
                "cdk-python-testing-helper-inline": role_inline_policy.document
            },
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
        )


app = App()
IAMStack(app, "IAMStack")
app.synth()
