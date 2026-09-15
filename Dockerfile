# Velaris, ready to run.
#
#   docker build -t velaris .
#   docker run --rm -v "$PWD:/work" velaris check /work/main.vel
#   docker run --rm -v "$PWD:/work" velaris /work/main.vel
#   docker run --rm -v "$PWD:/work" velaris /work/main.vel --allow io,fs:read:/work
#
# A run with no --allow gets io - the console - and every other effect
# is refused (5.0). Name what the program needs, narrowest first.
#
# The image carries the prover and the native backend, so promises are
# proven rather than checked while running.

FROM python:3.12-slim

LABEL org.opencontainers.image.title="Velaris"
LABEL org.opencontainers.image.description="A language where signatures declare types, effects, and machine-checked promises."
LABEL org.opencontainers.image.source="https://github.com/gowrishankar-infra/velaris-lang"
LABEL org.opencontainers.image.licenses="MIT"

# What to install. The nightly install test (nightly.yml) builds this file
# with the wheel it built from main; everyone else gets the release on PyPI.
ARG VELARIS="velaris-lang[full]"
RUN pip install --no-cache-dir "$VELARIS" && velaris doctor

WORKDIR /work
ENTRYPOINT ["velaris"]
CMD ["--version"]
