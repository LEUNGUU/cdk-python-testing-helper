from aws_cdk import Stack, App, Environment, aws_ec2 as ec2


class DefaultVPC(Stack):
    def __init__(self, app: App, id: str, **kwargs) -> None:
        super().__init__(app, id, **kwargs)

        vpc = ec2.Vpc.from_lookup(self, "DefaultVPC", is_default=True)


env = Environment(account="435854615015", region="us-east-1")
app = App()
DefaultVPC(app, "DefaultVPCStacck", env=env)
app.synth()
