# syntax=docker/dockerfile:1.6
# Build from the repository root. The pinned kernel is unchanged.
FROM docker.io/library/gcc:12.5.0-bookworm@sha256:4adc71d718fb96aeda49f1da3a936e1ea07af2b192493414a8bca1c73b9f2adb AS kernel-builder
WORKDIR /build
COPY form/runtime /build/runtime
RUN cc -O2 -o /build/fkwu runtime/fkwu-uni.c

FROM debian:bookworm-slim@sha256:7c7b2c966bc9ee8cedfeef67e0e279108992c77681fa595db4a9d65c06ccc587
# Form owns persistence. TLS is called directly by fkwu through
# libssl; no Python, curl, web server, scheduler or shell owns application logic.
RUN apt-get update && apt-get install -y --no-install-recommends libssl3 ca-certificates \
 && rm -rf /var/lib/apt/lists/* && mkdir -p /data
COPY --from=kernel-builder /build/fkwu /app/form/fkwu
COPY form/form/form-stdlib /app/form/form/form-stdlib
COPY form/form/native /app/form/form/native
COPY form/observe /app/form/observe
COPY form/runtime /app/form/runtime
COPY pulse/*.bml pulse/config.json pulse/organs.json /app/pulse/
COPY pulse/fkwu.conf /app/form/fkwu.conf
WORKDIR /app/form
# Assemble application entry images once on the builder's native tmpfs.
# Running requests load their native images rather than recompiling the same
# BML in eleven parallel workers. Authored BML remains the source authority.
RUN --mount=type=tmpfs,target=/dev/shm ./fkwu --check ../pulse/main.bml \
 && ./fkwu --check ../pulse/http.bml \
 && ./fkwu --check ../pulse/fetch.bml \
 && ./fkwu --check ../pulse/migrate.bml \
 && ./fkwu --check ../pulse/round.bml \
 && ./fkwu --check ../pulse/read.bml \
 && ./fkwu --check ../pulse/index.bml \
 && ./fkwu --check ../pulse/health.bml
ARG COHERENCE_SOURCE_SHA
ARG COHERENCE_FORM_SHA
LABEL org.opencontainers.image.title="pulse"
LABEL org.opencontainers.image.description="Independent Form-native pulse witness"
LABEL org.opencontainers.image.source="https://github.com/seeker71/Coherence-Network"
LABEL org.opencontainers.image.revision="${COHERENCE_SOURCE_SHA}"
LABEL org.opencontainers.image.coherence-form-revision="${COHERENCE_FORM_SHA}"
VOLUME ["/data"]
EXPOSE 8100
HEALTHCHECK --interval=60s --timeout=5s --start-period=120s --retries=3 \
 CMD ["./fkwu", "../pulse/health.bml"]
CMD ["./fkwu", "../pulse/main.bml"]
