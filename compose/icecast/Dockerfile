# Minimal Icecast2 streaming server (the destination nrsc5/ffmpeg pushes to).
FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    icecast2 gettext-base ca-certificates && rm -rf /var/lib/apt/lists/*
COPY icecast.xml.tmpl /icecast.xml.tmpl
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
EXPOSE 8000
ENTRYPOINT ["/entrypoint.sh"]
