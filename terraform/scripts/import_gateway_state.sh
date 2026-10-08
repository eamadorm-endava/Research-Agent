#!/bin/sh
# Run after terraform init. Only adopt validated objects absent from this state.
set -eu
imports_file="$1"
project_id="$2"
region="$3"
network_name="$4"
app_cidr="$5"
proxy_cidr="$6"
terraform state list > /tmp/gateway-state-addresses
while read -r address resource_id; do
  if ! grep -Fxq "$address" /tmp/gateway-state-addresses; then
    terraform import -lock-timeout=5m \
      -var="project_id=$project_id" -var="main_region=$region" \
      -var="network_name=$network_name" -var="app_subnet_cidr=$app_cidr" \
      -var="proxy_only_subnet_cidr=$proxy_cidr" "$address" "$resource_id"
  fi
done < "$imports_file"
