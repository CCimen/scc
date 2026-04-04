#!/bin/sh
# scc-egress-proxy entrypoint: assemble squid.conf and run Squid in foreground.
set -e

CONF_TEMPLATE="/etc/squid/squid.conf.template"
CONF_TARGET="/etc/squid/squid.conf"
ACL_RULES="/etc/squid/acl-rules.conf"

# Start from the template
cp "$CONF_TEMPLATE" "$CONF_TARGET"

# If the topology manager volume-mounted ACL rules, inject them
# between the SCC_ACL_RULES_START and SCC_ACL_RULES_END markers.
if [ -f "$ACL_RULES" ]; then
    sed -i "/^# SCC_ACL_RULES_START$/,/^# SCC_ACL_RULES_END$/{
        /^# SCC_ACL_RULES_START$/r $ACL_RULES
        /^# SCC_ACL_RULES_END$/!d
    }" "$CONF_TARGET"
fi

exec squid -N -f "$CONF_TARGET"
