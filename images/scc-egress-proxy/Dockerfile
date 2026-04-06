# scc-egress-proxy: Squid forward-proxy sidecar for enforced web-egress.
# The topology manager volume-mounts compiled ACL rules at runtime.
FROM alpine:3.19

RUN apk add --no-cache squid

COPY squid.conf.template /etc/squid/squid.conf.template
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 3128

HEALTHCHECK --interval=5s --timeout=3s --start-period=5s --retries=3 \
    CMD wget -q --spider http://localhost:3128 || exit 1

ENTRYPOINT ["/entrypoint.sh"]
