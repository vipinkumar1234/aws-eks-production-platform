# ArenaGrid Platform Components and Terminology

This reference explains every major component and production term used in the ArenaGrid AWS EKS platform. Each entry gives the practical purpose in one line.

## Product

| Component or term | Use case |
| --- | --- |
| **ArenaGrid** | Multiplayer tic-tac-toe arena where red and blue players claim board positions through an HTTP API. |
| **Game API** | Python service exposing `/healthz`, `/api/game/state`, and `POST /api/game/move`. |
| **DynamoDB game table** | Durable, encrypted storage for game boards so state survives pod restarts and scaling. |
| **Game ID** | Logical key that identifies a game board in DynamoDB; the default deployment uses `arena-default`. |
| **WebSocket extension** | Future real-time channel for matchmaking, presence, and live board updates. |

## Terraform and AWS Foundations

| Component or term | Use case |
| --- | --- |
| **Terraform** | Declaratively creates and updates AWS infrastructure from version-controlled code. |
| **Terraform module** | Reusable infrastructure unit such as VPC, EKS, WAF, ACM, Cognito, KMS, or DynamoDB. |
| **Terraform environment** | Isolated root configuration for one deployment environment, currently `dev` and `prod`. |
| **Remote state** | Shared durable Terraform state stored in an encrypted S3 backend. |
| **S3 state locking** | Terraform's native `use_lockfile=true` mechanism prevents concurrent state writes. |
| **State key** | Separate object path such as `eks/dev/terraform.tfstate` or `eks/prod/terraform.tfstate`. |
| **State bucket** | Pre-existing S3 bucket required before Terraform backend initialization. |
| **Ansible state bootstrap** | Idempotently creates and hardens the state bucket before Terraform runs. |
| **Plan** | Terraform's reviewed change preview before infrastructure is modified. |
| **Apply** | Terraform operation that creates or changes resources according to a plan. |
| **Destroy plan** | Explicit Terraform plan describing resource deletion after testing. |
| **AWS provider** | Terraform provider that communicates with AWS APIs. |
| **Default tags** | Provider-level tags applied automatically to supported AWS resources. |
| **InfraVersion** | Tag containing the deployed branch or deployment identifier, such as `feat_test` or `main`. |
| **Region alias** | Short naming token such as `apse1` for `ap-southeast-1` and `use1` for `us-east-1`. |

## Networking

| Component or term | Use case |
| --- | --- |
| **VPC** | Isolated AWS network containing the EKS cluster and supporting services. |
| **CIDR** | IP address range allocated to the VPC, such as `10.10.0.0/16`. |
| **Availability Zone** | Independent datacenter location used to spread infrastructure for fault tolerance. |
| **Multi-AZ** | Deployment across three Availability Zones to reduce single-zone failure impact. |
| **Public subnet** | Subnet with internet routing used primarily by the internet-facing ALB. |
| **Private subnet** | Subnet without direct public addressing used by EKS nodes, pods, and private services. |
| **Route table** | Network routing rules that direct subnet traffic to NAT gateways or VPC endpoints. |
| **NAT Gateway** | Multi-AZ egress service allowing private workloads to reach required external AWS or internet services. |
| **VPC endpoint** | Private network path from the VPC to AWS services without public internet traversal. |
| **Gateway endpoint** | Route-table-based private endpoint used here for S3 and DynamoDB. |
| **Interface endpoint** | ENI-based private endpoint used here for ECR, STS, SSM, EC2 messaging, and CloudWatch Logs. |
| **Endpoint security group** | Allows private VPC workloads to reach interface endpoints over HTTPS. |
| **DNS hostnames/support** | VPC settings required for private endpoint names and AWS service resolution. |

## EKS and Kubernetes

| Component or term | Use case |
| --- | --- |
| **Amazon EKS** | Managed Kubernetes control plane used to run ArenaGrid and platform add-ons. |
| **EKS control plane** | AWS-managed Kubernetes API, scheduler, and controllers. |
| **EKS API endpoint** | Kubernetes administration endpoint configured private-only by default. |
| **Managed node group** | AWS-managed EC2 worker group used for stable system capacity. |
| **Worker node** | EC2 instance that runs Kubernetes pods. |
| **Pod** | Smallest Kubernetes execution unit containing the ArenaGrid container. |
| **Deployment** | Maintains the desired ArenaGrid replica count and performs rolling updates. |
| **Service** | Stable Kubernetes virtual endpoint that selects ArenaGrid pods. |
| **ClusterIP** | Internal Kubernetes Service type used behind the ALB. |
| **Namespace** | Kubernetes boundary separating application, platform, observability, and Argo CD resources. |
| **ServiceAccount** | Kubernetes identity assigned to a pod. |
| **IRSA** | IAM Roles for Service Accounts; maps a Kubernetes ServiceAccount to a narrowly scoped AWS IAM role. |
| **NetworkPolicy** | Kubernetes traffic policy limiting pod ingress and egress. |
| **Resource requests** | Minimum CPU and memory reserved for reliable scheduling. |
| **Resource limits** | Maximum CPU and memory a container can consume. |
| **Read-only root filesystem** | Container hardening control that prevents writes to the image filesystem. |
| **Non-root container** | Security control that runs application code without UID 0 privileges. |
| **Topology spread constraint** | Distributes ArenaGrid replicas across Availability Zones for resilience. |
| **PDB** | PodDisruptionBudget that keeps a minimum number of replicas available during voluntary disruptions. |
| **HPA** | HorizontalPodAutoscaler that scales replicas based on CPU and memory utilization. |
| **Startup probe** | Prevents liveness failures while a new application pod is starting. |
| **Readiness probe** | Determines whether a pod may receive traffic. |
| **Liveness probe** | Detects a stuck process and allows Kubernetes to restart it. |
| **Termination grace period** | Time given to a pod to finish work before forced termination. |

## Load Balancing, TLS, and Edge Security

| Component or term | Use case |
| --- | --- |
| **AWS Load Balancer Controller** | Kubernetes controller that creates and maintains AWS ALBs from Ingress resources. |
| **ALB** | Internet-facing Application Load Balancer that terminates TLS and routes requests to pod IPs. |
| **Ingress** | Kubernetes routing resource defining the ArenaGrid hostname, listener ports, certificate, WAF, and backend. |
| **IP target mode** | ALB mode that registers pod IPs directly instead of node ports. |
| **Target group** | ALB backend group containing healthy ArenaGrid pod IPs. |
| **Health check** | ALB request to `/healthz` used to remove unhealthy pods from rotation. |
| **ACM** | AWS Certificate Manager that issues and renews the public TLS certificate. |
| **DNS validation** | ACM validation method using a Route 53 record proving domain ownership. |
| **HTTPS** | Encrypted client-to-ALB transport on port 443. |
| **HTTP redirect** | ALB behavior that redirects port 80 requests to HTTPS port 443. |
| **Route 53** | AWS DNS service used for certificate validation and the application hostname. |
| **WAF** | AWS Web Application Firewall attached to the ALB to block malicious requests. |
| **Managed WAF rule group** | AWS-maintained rules for common exploits and known bad inputs. |
| **Rate-based WAF rule** | Blocks an IP after it exceeds the configured request threshold. |
| **Cognito** | Managed user directory and OAuth provider used for ALB authentication. |
| **ALB authentication** | Forces users to sign in with Cognito before reaching ArenaGrid. |
| **WAF Web ACL ARN** | Identifier used by the Ingress to attach the Terraform-created WAF policy to the ALB. |

## Storage and Encryption

| Component or term | Use case |
| --- | --- |
| **KMS** | Customer-managed encryption key used for EKS secrets, ECR, DynamoDB, and S3 logs. |
| **Key rotation** | Automatic periodic KMS key material rotation. |
| **Deletion window** | Delay before a scheduled KMS key deletion becomes permanent. |
| **ECR** | Private container registry for ArenaGrid images. |
| **Immutable image tag** | ECR setting that prevents an existing image tag from being overwritten. |
| **Image scan on push** | Automatic vulnerability scanning when an image is uploaded to ECR. |
| **DynamoDB** | Serverless NoSQL database used for durable game state. |
| **On-demand billing** | DynamoDB capacity mode suitable for variable game traffic without provisioned capacity planning. |
| **PITR** | Point-in-time recovery that allows DynamoDB restoration to a recent timestamp. |
| **Deletion protection** | Prevents accidental removal of the game table. |
| **S3 log bucket** | Private storage location for Fluent Bit Kubernetes logs. |
| **S3 versioning** | Retains prior log object versions for recovery and audit. |
| **S3 lifecycle** | Automatically expires current and noncurrent log objects according to retention policy. |
| **SSE-KMS** | Server-side S3 encryption using the customer-managed KMS key. |

## Karpenter and Capacity

| Component or term | Use case |
| --- | --- |
| **Karpenter** | Kubernetes node provisioning controller that launches capacity when pods cannot be scheduled. |
| **NodePool** | Scheduling policy defining acceptable capacity types, instance families, limits, and disruption behavior. |
| **EC2NodeClass** | AWS-specific Karpenter configuration defining AMI, subnets, security groups, and node role. |
| **Bin packing** | Packing pods efficiently onto existing nodes before launching another node to reduce cost and waste. |
| **Instance category** | Karpenter constraint allowing balanced general, compute, and burstable families such as `t`, `m`, and `c`. |
| **Instance generation** | Constraint that avoids old EC2 generations. |
| **Spot capacity** | Lower-cost interruptible EC2 capacity allowed for suitable workloads. |
| **On-Demand capacity** | More stable EC2 capacity used when interruption risk is unacceptable. |
| **Consolidation** | Karpenter process that replaces or removes underutilized nodes. |
| **ConsolidateAfter** | Delay before Karpenter evaluates an underutilized node for consolidation. |
| **NodePool limits** | Maximum CPU and memory that Karpenter can provision for the pool. |
| **Disruption budget** | Limits the percentage of nodes Karpenter may disrupt at once. |
| **SSM node access** | Systems Manager sessions to EC2 nodes without opening SSH access. |

## GitOps and Delivery

| Component or term | Use case |
| --- | --- |
| **GitHub Actions** | CI/CD automation for validation, image publishing, Terraform, and deployment workflows. |
| **GitHub OIDC** | Short-lived AWS authentication from GitHub without stored AWS access keys. |
| **Branch protection** | Policy allowing `feat*` branches to deploy dev and only `main` to deploy prod. |
| **GitHub Environment** | Approval and secret boundary for dev and production deployments. |
| **Manual approval gate** | Required reviewer approval before protected environment jobs execute. |
| **Argo CD** | GitOps controller that continuously reconciles Kubernetes state from Git. |
| **AppProject** | Argo CD policy boundary controlling allowed repositories, clusters, namespaces, and resource types. |
| **Root Application** | Argo CD Application that points to a repository directory containing platform resources. |
| **Reconciliation** | Argo CD process that makes the cluster match the Git revision. |
| **Immutable image** | Image identified by a commit tag or, preferably, a digest that cannot be silently replaced. |
| **Image digest** | Cryptographic identity used to promote exactly the same image between environments. |
| **Promotion** | Moving a tested image and GitOps revision from dev toward production. |
| **Terraform plan artifact** | Saved production plan reviewed before the protected apply job. |
| **GitOps renderer** | `scripts/render-gitops.sh`, which fills AWS output values into GitOps templates after apply. |
| **Drift** | Difference between declared Git/Terraform configuration and deployed infrastructure. |

## Observability and Operations

| Component or term | Use case |
| --- | --- |
| **Prometheus** | Metrics collection and rule evaluation for Kubernetes and ArenaGrid health. |
| **Grafana** | Dashboards for platform and application metrics. |
| **Alertmanager** | Groups and routes Prometheus alerts to operational notification channels. |
| **PrometheusRule** | Declarative alert rule for unavailable replicas, restarts, or missing endpoints. |
| **Fluent Bit** | Lightweight log collector running as a DaemonSet on nodes. |
| **DaemonSet** | Runs one logging pod on each eligible Kubernetes node. |
| **S3 log output** | Fluent Bit destination for encrypted, retained Kubernetes logs. |
| **Control-plane logs** | EKS API, audit, authenticator, controller-manager, and scheduler logs. |
| **SLO** | Service-level objective such as availability or latency target. |
| **RPO** | Maximum acceptable amount of data loss after an incident. |
| **RTO** | Maximum acceptable time to restore service after an incident. |
| **Backup drill** | Tested restore procedure proving backups are usable, not merely present. |
| **Runbook** | Documented operational procedure for deployment, incident response, rollback, or recovery. |
| **Rollback** | Reverting to a previously approved image, GitOps revision, or Terraform change. |
| **Least privilege** | Giving each identity only the AWS/Kubernetes permissions it needs. |
| **Defense in depth** | Combining TLS, WAF, Cognito, network policy, IAM, encryption, and observability controls. |

## Important Repository Files

| File or directory | Use case |
| --- | --- |
| `terraform/environments/dev` | Dev AWS root configuration. |
| `terraform/environments/prod` | Production AWS root configuration. |
| `terraform/modules` | Reusable infrastructure modules. |
| `gitops/argocd` | Argo CD project and root application bootstrap. |
| `gitops/platform` | AWS Load Balancer Controller, Karpenter, cert-manager, and metrics-server. |
| `gitops/apps/sample-app` | ArenaGrid Deployment, Service, Ingress, policies, HPA, and PDB. |
| `gitops/observability` | Prometheus, Grafana, Alertmanager, Fluent Bit, and alert rules. |
| `application/sample-app` | ArenaGrid source code, Dockerfile, dependencies, and tests. |
| `.github/workflows` | Validation, Terraform approval, image, GitOps, and security automation. |
| `scripts/bootstrap.sh` | Initializes remote state, applies an environment plan, and configures kubectl. |
| `scripts/render-gitops.sh` | Renders AWS Terraform outputs into GitOps manifests. |
| `DEPLOYMENT_README.md` | End-to-end deployment and operations guide. |
| `docs/architecture.md` | Detailed text and Mermaid architecture design. |
| `docs/architecture.drawio` | Editable diagrams.net low-level architecture diagram. |
