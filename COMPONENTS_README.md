# Components

| Component | Purpose |
|---|---|
| Flask + Gunicorn | One UI/API service; solo and friend tic-tac-toe |
| Cognito | Verified email, OAuth code/PKCE login and signed ID tokens |
| DynamoDB | On-demand room storage, conditional writes, abuse limits, TTL, backups |
| EKS managed nodes | Two system nodes, private subnets, IMDSv2, encrypted storage |
| Karpenter | Workload node provisioning, bin packing/consolidation, bounded CPU capacity and interruption handling |
| ALB + ACM + WAF | HTTPS ingress, certificate renewal, common attack and rate rules |
| IAM + KMS + Secrets Manager | Workload permissions, encryption and shared session secret |
| ECR + GitHub Actions | Scanned, immutable images and OIDC authentication |
| Argo CD | Git-driven reconciliation of reviewed manifests |
| Metrics Server | CPU/memory HPA, capped at four game replicas |
| Fluent Bit + S3 | Centralized application/node logs |
| CloudWatch | EKS audit/control-plane logs and VPC flow logs |
| S3 backend | Versioned state with native lockfiles; no DynamoDB locking table |

[Deploy](DEPLOYMENT_README.md) ? [Architecture](docs/architecture.md)
