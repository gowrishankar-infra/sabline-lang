# Sabline, ready to run.
#
#   docker build -t sabline .
#   docker run --rm -v "$PWD:/work" sabline check /work/main.vel
#   docker run --rm -v "$PWD:/work" sabline /work/main.vel
#   docker run --rm -v "$PWD:/work" sabline /work/main.vel --allow io,fs:read:/work
#
# A run with no --allow gets io - the console - and every other effect
# is refused (5.0). Name what the program needs, narrowest first.
#
# The image carries the prover and the native backend, so promises are
# proven rather than checked while running.

FROM python:3.12-slim

LABEL org.opencontainers.image.title="Sabline"
LABEL org.opencontainers.image.description="A language where signatures declare types, effects, and machine-checked promises."
LABEL org.opencontainers.image.source="https://github.com/gowrishankar-infra/sabline-lang"
LABEL org.opencontainers.image.licenses="MIT"

# What to install. The nightly install test (nightly.yml) builds this file
# with the wheel it built from main; everyone else gets the release on PyPI.
ARG SABLINE="sabline-lang[full]"
RUN pip install --no-cache-dir "$SABLINE" && sabline doctor

WORKDIR /work
ENTRYPOINT ["sabline"]
CMD ["--version"]
