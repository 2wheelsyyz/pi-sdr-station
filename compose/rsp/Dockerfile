# SoapySDR + SoapySDRPlay3 (v3) + the proprietary SDRplay API — the stable way to
# drive the SDRplay RSPduo (acarsdec's native sdrplay backend crashes on antenna/gain
# selection, so we go through SoapySDR, which is also what OpenWebRX uses).
#
# Bundles the API *service*; the entrypoint starts it, then runs the given command.
# Default command probes the device (SoapySDRUtil) — handy for validating reception.
FROM debian:bookworm-slim

ARG SDRPLAY_VER=3.15.2
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
      curl ca-certificates build-essential cmake git pkg-config \
      libusb-1.0-0-dev libsoapysdr-dev soapysdr-tools; \
    # --- SDRplay API v3 (aarch64) ---
    curl -fsSL "https://www.sdrplay.com/software/SDRplay_RSP_API-Linux-${SDRPLAY_VER}.run" -o /tmp/api.run; \
    chmod +x /tmp/api.run; sh /tmp/api.run --noexec --keep --target /tmp/sp; \
    install -m0755 /tmp/sp/arm64/libsdrplay_api.so.3.15 /usr/local/lib/; \
    install -m0755 /tmp/sp/arm64/sdrplay_apiService /usr/local/bin/; \
    cp /tmp/sp/inc/*.h /usr/local/include/; \
    cd /usr/local/lib; ln -sf libsdrplay_api.so.3.15 libsdrplay_api.so.3; ln -sf libsdrplay_api.so.3 libsdrplay_api.so; \
    ldconfig; \
    # --- SoapySDRPlay3 module (builds against the API above) ---
    git clone --depth 1 https://github.com/pothosware/SoapySDRPlay3.git /tmp/SoapySDRPlay3; \
    cmake -S /tmp/SoapySDRPlay3 -B /tmp/SoapySDRPlay3/build -DCMAKE_BUILD_TYPE=Release; \
    cmake --build /tmp/SoapySDRPlay3/build -j"$(nproc)"; \
    cmake --install /tmp/SoapySDRPlay3/build; ldconfig; \
    rm -rf /tmp/* /var/lib/apt/lists/*

COPY entrypoint.sh /usr/local/bin/rsp-entrypoint.sh
RUN chmod +x /usr/local/bin/rsp-entrypoint.sh
ENTRYPOINT ["/usr/local/bin/rsp-entrypoint.sh"]
CMD ["SoapySDRUtil", "--probe=driver=sdrplay"]
