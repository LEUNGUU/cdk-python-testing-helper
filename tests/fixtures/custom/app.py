from aws_cdk import App
from fargate_profile import ServerlessEKS

app = App()

fargate_profile = ServerlessEKS(
    app,
    "FargateProfileEKS",
    cluster_name="FargateProfileEKS",
    k8s_version="1.24",
    fargate_profile_name="NodeGroupC",
)

app.synth()
