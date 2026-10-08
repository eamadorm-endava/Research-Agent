#!/bin/sh
# Import only discovered test services absent from the selected UI state.
set -eu
imports_file="$1"
project_id="$2"
region="$3"
terraform state list > /tmp/ui-state-addresses
while read -r address resource_id; do
  if ! grep -Fxq "$address" /tmp/ui-state-addresses; then
    terraform import -lock-timeout=5m \
      -var="project_id=$project_id" -var="main_region=$region" "$address" "$resource_id"
  fi
done < "$imports_file"
