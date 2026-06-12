# Dockerfile — package the Form-emitted db-api binary into a minimal Linux image.
# The build stage emits C from the Form recipe (Go kernel), compiles with clang,
# and seeds a real SQLite file. The runtime stage carries ONLY the binary + the
# .db: no Python, no Node, no libsqlite3 — just libc. The binary parses SQLite
# itself (sqlite-read.fk) and is the only process.
#
# Build:  docker build -f deploy/db-api/Dockerfile -t form-db-api .
# Run:    docker run -p 8080:8080 form-db-api
# Then:   curl localhost:8080/ · /api/idea · /api/_surface · /api/_binary
#
# NOTE (2026-06-12): authored + portable (the emitted C carries the Linux/BSD
# sockaddr #ifdef), but NOT built in the session that wrote it (no docker daemon
# present). The native macOS binary IS witnessed live (scripts/db_api_server_demo.sh
# — Mach-O arm64, links only libSystem, runs on a fresh Mac with zero installed
# deps). Docker images are Linux, so this is the Linux sibling of that artifact.

# ── build: emit from Form, compile, seed ──
FROM golang:1.23-bookworm AS build
RUN apt-get update && apt-get install -y --no-install-recommends clang sqlite3 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /src
COPY form/ form/
RUN cd form/form-kernel-go && go build -o bin-go .
RUN cd form \
 && { printf '(do\n'; cat form-stdlib/db-api-server.fk; \
      printf '\n(print "==C==")\n(print (das-emit))\n(print "==END==")\n0)\n'; } > /tmp/driver.fk \
 && ./form-kernel-go/bin-go /tmp/driver.fk \
      | sed -n '/^==C==$/,/^==END==$/p' | sed -e '1d' -e '$d' > /tmp/srv.c \
 && clang -O2 -o /tmp/db-api /tmp/srv.c
RUN sqlite3 /data.db "CREATE TABLE idea(id INTEGER, slug TEXT, title TEXT); \
    INSERT INTO idea VALUES (1,'agent-pipeline','Agent Pipeline'), \
    (2,'form-os','Form OS'),(3,'living-equation','The Living Equation');"

# ── runtime: the binary + the .db, nothing else ──
FROM debian:bookworm-slim
COPY --from=build /tmp/db-api /usr/local/bin/db-api
COPY --from=build /data.db /data/seed.db
EXPOSE 8080
ENTRYPOINT ["/usr/local/bin/db-api"]
CMD ["8080", "/data/seed.db"]
