# Operations

Two managed system nodes host platform controllers; a separate Karpenter pool hosts application pods. HPA scales game pods from two to four, and Karpenter adds workload capacity as needed. It consolidates eligible underused nodes after five minutes, respecting the configured single-node voluntary disruption budget, PDB and two-AZ spread. Check pending pods, NodeClaims and controller logs before increasing the pool's CPU cap. Karpenter does not autoscale the managed system group. See the [deployment checklist](../DEPLOYMENT_README.md#production-deployment-checklist) for scaling tests, AMI rotation and recovery boundaries.

Application startup fails closed if Cognito, DynamoDB or the session secret is missing. `/healthz` checks the process; `/readyz` also reads DynamoDB. Inspect restarts, readiness, ALB target health and Argo CD sync status after each rollout. CPU-intensive solo moves are bounded by the small board and per-user write limits.

Fluent Bit ships logs to encrypted S3 within roughly one minute. Its temporary upload buffer may be lost on node failure; this is basic operational logging, not a lossless audit pipeline. EKS control-plane/audit logs and VPC flow logs go to CloudWatch. WAF and DynamoDB expose native CloudWatch metrics. There is no installed Prometheus dashboard or paging destination; configure alarms/notifications for your actual service objectives before relying on this for production.

DynamoDB uses on-demand capacity, point-in-time recovery, deletion protection and TTL. TTL deletion is asynchronous; the app immediately rejects expired rooms. Test point-in-time restore into a new table before any real launch. S3 state versioning supports recovery; never force-unlock until the lock holder is confirmed dead.

Rotate the Secrets Manager session key and restart all game pods together; this invalidates active sessions. Terraform owns the initial secret version; coordinate external rotation with configuration/state to avoid conflicting ownership. Keep state access restricted because the initial key is also in encrypted Terraform state.

Security boundaries: the game namespace enforces restricted pods and default-deny networking with DNS, VPC ingress to port 8080, and HTTPS egress for AWS/Cognito. HTTPS egress is not domain-filtered. Nodes require IMDSv2 with hop limit one; game containers run non-root, drop capabilities and use read-only roots. Argo CD/platform controllers remain privileged administrative components; restrict their access. Cognito verifies email and enforces a strong password policy, but MFA is not configured by this test stack.

Keep dependencies, images, Kubernetes and Helm charts patched and scan changes. Production use additionally requires tested backups, alert routing, capacity/load tests, identity/MFA policy, access reviews and a region-specific availability/cost review. Dev's single NAT gateway is an explicit availability tradeoff.
