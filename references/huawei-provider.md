# Huawei Cloud provider guardrails

- Use provider source `huaweicloud/huaweicloud` with a literal version constraint.
- Use `huaweicloud_vpc_subnet_v1`; set required `gateway_ip`, deriving it with `cidrhost(cidr, 1)` only when documented as an assumption.
- Use `huaweicloud_networking_secgroup` and `huaweicloud_networking_secgroup_rule`.
- Do not use `huaweicloud_vpc_security_group_v1` or `huaweicloud_vpc_subnet_security_group_associate_v1`.
- Attach security groups to ECS instances or ports with stable references; do not attach them to VPCs or subnets.
- Preserve resource block type and label for existing state addresses unless an intentional replacement is approved.
- Keep AK/SK and passwords outside Terraform source. Use environment variables or sensitive input variables.
- Default to private access and least privilege. Never expose administrative or database ports to `0.0.0.0/0` or `::/0`.
