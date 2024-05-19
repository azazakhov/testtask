# syntax=docker/dockerfile:1

###
### Build stage:
###
FROM python:3.12.2-slim AS build

# pip config
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV PIP_NO_DEPS=1

# build venv
ENV VENV_PATH=/opt/venv
RUN python -m venv "$VENV_PATH"
ENV PATH="$VENV_PATH/bin:$PATH"

# src
ENV SRC_PATH=/usr/src/
WORKDIR "$SRC_PATH"

ADD ./requirements/main.txt ./requirements/main.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --require-hashes -r requirements/main.txt

ADD . .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install .


###
### Runtime stage:
###
FROM python:3.12.2-slim AS runtime

# Keeps Python from buffering stdout and stderr to avoid situations where
# the application crashes without emitting any logs due to buffering.
ENV PYTHONUNBUFFERED=1

# Create a non-root user
RUN groupadd -r worker && useradd --no-log-init --system --gid worker worker
USER worker

ENV VENV_PATH=/opt/venv

# Copy venv with all dependencies and packages
COPY --from=build "$VENV_PATH" "$VENV_PATH"
ENV PATH="$VENV_PATH/bin:$PATH"

ENTRYPOINT ["python", "-m", "aiohttp.web", "assetsrates.app:create_app"]
CMD ["-H", "0.0.0.0", "-P", "8080"]

EXPOSE 8080
