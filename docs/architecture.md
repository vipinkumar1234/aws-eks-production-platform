# Architecture

```mermaid
flowchart LR
  Player -->|HTTPS| ALB[ALB + ACM + WAF]
  ALB --> Game[Two game replicas on private EKS nodes]
  Player <-->|Code + PKCE login| Cognito
  Game -->|IRSA| DynamoDB[DynamoDB rooms + limits + TTL]
  Game -->|IRSA| Secrets[Secrets Manager session key]
  GitHub[GitHub Actions OIDC] --> ECR[Scanned immutable ECR images]
  Argo[Argo CD] --> Game
  Karpenter[Karpenter on managed system nodes] --> Workload[Private workload nodes with consolidation]
  Workload --> Game
  ECR --> Game
  Logs[Fluent Bit] --> S3Logs[Encrypted S3 logs]
  EKS[EKS audit logs + VPC flow logs] --> CloudWatch
  Bootstrap[AWS SDK bucket bootstrap] --> State[Private versioned S3 state]
  State --> Init[Terraform init with native lockfile]
```

Two AZs, public ALB subnets and private node subnets. Dev has one NAT gateway, prod one per AZ. S3 and DynamoDB gateway endpoints avoid NAT for those services; other AWS HTTPS APIs use NAT. EKS API access is private unless administrator CIDRs are explicitly provided.

Cognito login is implemented once, in the application. Signed, secure HttpOnly cookies carry the session; PKCE/state/nonce and issuer/audience/expiry checks protect login. DynamoDB conditional writes serialize room transitions across workers. The same Secrets Manager session key is loaded by all replicas at startup.
