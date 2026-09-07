# Operations

Use `scripts/bootstrap.sh` only from a workstation or trusted runner with the intended AWS role. Inspect Terraform plans before applying. Rotate the GitHub repository subject allow-list whenever repository or branch ownership changes.

For incidents, inspect Argo CD sync status, EKS control-plane logs, CloudWatch metrics, Prometheus alerts, and Fluent Bit delivery. Roll back application images by reverting the Git commit that changed the immutable image tag.
