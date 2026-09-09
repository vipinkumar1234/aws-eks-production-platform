> Historical review: Karpenter was restored in the subsequent production-capacity revision. See DEPLOYMENT_README.md and docs/aws-naming.md for the current deployment.

# Simplification review

The starting worktree already contained application changes and broad uncommitted infrastructure edits. The current game was retained; deployment wiring was aligned to it.

Fixed deployment blockers: missing Flask/JWT/Gunicorn dependencies; Docker starting a localhost development server; obsolete HTTP-server tests; duplicate ALB versus application authentication; missing Cognito PKCE callback/client configuration; missing session-secret resource/IAM/environment; missing DynamoDB TTL; readiness probing only the process; initializing a nonexistent state bucket.

Removed Karpenter and its IAM/SQS/EventBridge resources, cert-manager, unused external-secrets configuration, the Prometheus/Grafana/Alertmanager stack and costly interface endpoints. Reduced node/pod counts and AZs while retaining separate dev/prod state roots. CI now deploys infrastructure only on explicit dispatch.

Validated locally:

- Terraform 1.14.0: backend-free initialization and provider-level validation passed for dev and prod; formatting passed.
- 12 application/authentication tests and 10 state-bootstrap/GitOps-render tests passed.
- All 19 YAML files parsed without duplicate keys or missing manifest envelopes.
- pip-audit 2.10.0 found no known vulnerabilities in the 20 locked runtime packages.
- Bash bootstrap syntax and Git whitespace checks passed.

Not executed: AWS plan/apply, container build/image scan, full Kubernetes schema/security scans, live Cognito login, DNS cutover and log-delivery checks. Account/profile, domain/zone, admin role and repository inputs are still required. CI retains Trivy, tfsec, Checkov and secret-scanning gates. Unit tests exercise game access, CSRF, turn/version checks, local-only demo mode, bootstrap failure ordering and native locking. A cloud plan/apply and browser sign-in require account-specific inputs and are not implied by local validation.
