# Helm chart for however-microservices-lab

If you'd like to deploy however-microservices-lab via its Helm chart, you can use the following commands.

**Warning:** This Helm chart is experimental and intended as a cloud-native lab deployment path.

Deploy the default setup:
```sh
helm upgrade however-microservices-lab ./helm-chart \
    --install
```

Deploy an advanced scenario:
```sh
helm upgrade however-microservices-lab ./helm-chart \
    --install \
    --create-namespace \
    --set images.repository=us-docker.pkg.dev/my-project/however-microservices-lab \
    --set frontend.externalService=false \
    --set cartDatabase.inClusterRedis.create=false \
    --set cartDatabase.type=spanner \
    --set cartDatabase.connectionString=projects/my-project/instances/however-microservices-lab/databases/carts \
    --set serviceAccounts.create=true \
    --set authorizationPolicies.create=true \
    --set networkPolicies.create=true \
    --set sidecars.create=true \
    --set frontend.virtualService.create=true \
    --set 'serviceAccounts.annotations.iam\.gke\.io/gcp-service-account=spanner-db-user@my-project.iam.gserviceaccount.com' \
    --set serviceAccounts.annotationsOnlyForCartservice=true \
    -n however-microservices-lab
```

For the full list of configurations, see [values.yaml](./values.yaml).

Upstream references that are still useful for advanced scenarios:
- [Online Boutique sample’s Helm chart, to simplify the setup of advanced and secured scenarios with Service Mesh and GitOps](https://medium.com/google-cloud/246119e46d53)
- [gRPC health probes with Kubernetes 1.24+](https://medium.com/google-cloud/b5bd26253a4c)
- [Use Google Cloud Spanner with the Online Boutique sample](https://medium.com/google-cloud/f7248e077339)
