# rsp_tcp bridge — serves the RSPduo as rtl_tcp for OpenWebRX/nrsc5.
# Uses ON5HB/rsp_tcp_v2 (not SDRplay's official RSPTCPServer): it exposes real gain
# control — -l (LNA state), -g (IF gain reduction), -G (AGC setpoint) — which the
# official one lacks. That's what HD Radio needs to overcome the discone's FM-trap.
# Built on the rsp-soapy base (SDRplay API + SoapySDRUtil for the readiness probe).
FROM va3ymx/rsp-soapy:latest
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends build-essential cmake git libusb-1.0-0-dev pkg-config; \
    git clone --depth 1 https://github.com/ON5HB/rsp_tcp_v2.git /tmp/rsptcp; \
    cmake -S /tmp/rsptcp -B /tmp/rsptcp/build -DCMAKE_BUILD_TYPE=Release; \
    cmake --build /tmp/rsptcp/build -j"$(nproc)"; \
    install -m0755 /tmp/rsptcp/build/rsp_tcp /usr/local/bin/; \
    rm -rf /tmp/rsptcp /var/lib/apt/lists/*
COPY entrypoint.sh /usr/local/bin/rsptcp-entrypoint.sh
RUN chmod +x /usr/local/bin/rsptcp-entrypoint.sh
ENTRYPOINT ["/usr/local/bin/rsptcp-entrypoint.sh"]
