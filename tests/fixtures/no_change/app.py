import os
from aws_cdk import Stack, App, Environment, aws_ec2 as ec2


class DefaultVPC(Stack):
    def __init__(self, app: App, id: str, **kwargs) -> None:
        super().__init__(app, id, **kwargs)

        vpc = ec2.Vpc.from_lookup(self, "DefaultVPC", is_default=True)


account_id = os.getenv("ACCOUNT_ID", "")
region = os.getenv("AWS_REGION", "")

env = Environment(account=account_id, region=region)
app = App()
DefaultVPC(app, "DefaultVPCStacck", env=env)
app.synth()
