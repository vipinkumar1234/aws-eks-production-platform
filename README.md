# Small EKS gaming application

ArenaGrid is a small tic-tac-toe game: play against the computer or invite a friend. One Flask/Gunicorn service serves the UI and API. Cognito handles email sign-in; DynamoDB holds rooms and enforces concurrent moves across replicas.

The platform keeps practical production controls without a large in-cluster tool stack:

- EKS with two managed system nodes and Karpenter workload provisioning/consolidation across two availability zones; 2?4 application replicas, probes, HPA and a disruption budget.
- CloudFront HTTPS address (no purchased domain), private ALB, edge WAF rules and application-level Cognito authorization-code login with PKCE.
- Scoped IAM roles for service accounts, Secrets Manager session key, KMS encryption, private EKS API by default, restricted pods and NetworkPolicies.
- ECR immutable images and scans, GitHub OIDC, Argo CD deployment, Fluent Bit logs in S3, EKS audit logs and VPC flow logs in CloudWatch.
- Versioned, private S3 Terraform state with native `.tflock` locking. The bootstrap creates and secures the bucket **before** `terraform init`.

Removed: cert-manager (CloudFront supplies its default HTTPS certificate), unused external-secrets configuration, Prometheus/Grafana/Alertmanager and eight interface endpoints per AZ. Dev uses one NAT gateway; prod uses one per AZ. DynamoDB is game storage, never Terraform locking.

Start with **[deployment instructions](DEPLOYMENT_README.md)**. Dev and prod are separate optional environments; deploy only dev for a small test.

Local demo, using Python 3.12:

```bash
cd application/sample-app
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
LOCAL_DEMO=1 ENVIRONMENT=local python -m src.server
```

Open http://127.0.0.1:8080. On PowerShell, activate `.venv/Scripts/Activate.ps1` and set `$env:LOCAL_DEMO="1"; $env:ENVIRONMENT="local"` before starting Python. Demo identities and in-memory data are local-only; EKS refuses demo mode.

Tests: `python -m unittest discover -s tests -v` from the application directory. Bootstrap/renderer tests: `python -m unittest discover -s scripts -p 'test_*.py' -v` from the repository root (requires boto3). YAML validation requires PyYAML.

This is a compact production-style test platform, not a claim of complete production readiness. Paging integrations, multi-region recovery and a full metrics backend are deliberately absent. See [operations](docs/operations.md) for these boundaries.

Karpenter uses a bounded On-Demand workload pool, tested AMI pins, Pod Identity and interruption handling. See [deployment prerequisites](DEPLOYMENT_README.md#1-prepare-aws-and-github) and [AWS naming](docs/aws-naming.md).

Deployment is configured for AWS account `001495086648` and existing role `AutomationAdminAll`. See [one-time OIDC setup and workflow defaults](DEPLOYMENT_README.md#1-one-time-aws-trust-setup-for-your-existing-role). The default test URL needs no purchased domain; optional Route 53 zone creation is documented there.
