# nrsc5 (HD Radio / NRSC-5 decoder) with the RTL-SDR Blog v4 driver + ffmpeg,
# for decoding HD Radio and streaming the audio to Icecast (see scripts/hdradio.sh).
FROM debian:bookworm-slim AS build
RUN apt-get update && apt-get install -y --no-install-recommends \
    git cmake build-essential pkg-config autoconf automake libtool \
    libusb-1.0-0-dev libfftw3-dev libao-dev libfaad-dev ca-certificates \
 && rm -rf /var/lib/apt/lists/*
RUN git clone --depth 1 https://github.com/rtlsdrblog/rtl-sdr-blog /rtl \
 && cmake -S /rtl -B /rtl/build -DINSTALL_UDEV_RULES=ON \
 && cmake --build /rtl/build -j"$(nproc)" && cmake --install /rtl/build && ldconfig
RUN git clone --depth 1 https://github.com/theori-io/nrsc5 /src \
 && PKG_CONFIG_PATH=/usr/local/lib/pkgconfig cmake -S /src -B /src/build \
 && cmake --build /src/build -j"$(nproc)" && cmake --install /src/build && ldconfig

FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    libusb-1.0-0 libfftw3-double3 libfftw3-single3 libao4 libfaad2 ffmpeg ca-certificates \
 && rm -rf /var/lib/apt/lists/*
COPY --from=build /usr/local/ /usr/local/
COPY hdstream /usr/local/bin/hdstream
RUN ldconfig && chmod +x /usr/local/bin/hdstream
# default: raw nrsc5 CLI (e.g. `docker run … 98.1 0`); use --entrypoint hdstream to stream
ENTRYPOINT ["nrsc5"]
