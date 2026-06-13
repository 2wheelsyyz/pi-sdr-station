# OpenWebRX+ with a current SoapySDRPlay3 that can drive the RSPduo.
#
# The stock slechev/openwebrxplus bundles SoapySDRPlay3 0.8.11-146ce1c, whose
# soapy_connector fails sdrplay_api_Init on the RSPduo at every sample rate — while
# acarsdec works through a master build of the same module. So we rebuild the module
# from master *inside this image* (right libstdc++) and drop the bundled one.
FROM slechev/openwebrxplus:latest

ARG SDRPLAY_VER=3.15.2
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
      build-essential cmake git pkg-config libsoapysdr-dev curl ca-certificates; \
    # SDRplay API headers (the runtime lib is already in the image)
    curl -fsSL "https://www.sdrplay.com/software/SDRplay_RSP_API-Linux-${SDRPLAY_VER}.run" -o /tmp/api.run; \
    chmod +x /tmp/api.run; sh /tmp/api.run --noexec --keep --target /tmp/sp; \
    cp /tmp/sp/inc/*.h /usr/local/include/; \
    [ -e /usr/local/lib/libsdrplay_api.so ] || ln -sf /usr/local/lib/libsdrplay_api.so.3 /usr/local/lib/libsdrplay_api.so; \
    ldconfig; \
    # build SoapySDRPlay3 master, then remove the stale bundled module
    git clone --depth 1 https://github.com/pothosware/SoapySDRPlay3.git /tmp/sp3; \
    cmake -S /tmp/sp3 -B /tmp/sp3/build -DCMAKE_BUILD_TYPE=Release; \
    cmake --build /tmp/sp3/build -j"$(nproc)"; \
    cmake --install /tmp/sp3/build; \
    rm -f /usr/lib/aarch64-linux-gnu/SoapySDR/modules0.8/libsdrPlaySupport.so; \
    ldconfig; \
    rm -rf /tmp/api.run /tmp/sp /tmp/sp3 /var/lib/apt/lists/*
