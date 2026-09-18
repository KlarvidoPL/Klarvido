ARG SB_MIRROR_REPOSITORY=''
ARG SB_PULL_THROUGH_CACHE_REPOSITORY=''
##
# Chamber installation stage
##

FROM ${SB_MIRROR_REPOSITORY}segment/chamber:2 AS chamber

FROM ${SB_PULL_THROUGH_CACHE_REPOSITORY}python:3.11-slim-bullseye

ENV APP_PATH=/app
ENV SRC_CORE_PATH=packages/internal/core
ENV DEST_CORE_PATH=$APP_PATH/$SRC_CORE_PATH
ENV SRC_CLI_PATH=packages/internal/cli
ENV DEST_CLI_PATH=$APP_PATH/$SRC_CLI_PATH
ENV SRC_WORKERS_PATH=packages/workers
ENV DEST_WORKERS_PATH=$APP_PATH/$SRC_WORKERS_PATH

# deb.debian.org's live bullseye-security suite is inconsistent now that bullseye is EOL
# (Packages index lists versions whose pool files have already been purged from the CDN,
# causing intermittent 404s). Pin to a snapshot.debian.org mirror instead, which is immutable.
RUN printf '%s\n' \
  'deb [check-valid-until=no] http://snapshot.debian.org/archive/debian/20250721T000000Z bullseye main' \
  'deb [check-valid-until=no] http://snapshot.debian.org/archive/debian-security/20250721T000000Z bullseye-security main' \
  'deb [check-valid-until=no] http://snapshot.debian.org/archive/debian/20250721T000000Z bullseye-updates main' \
  > /etc/apt/sources.list

RUN apt-get update && apt-get install -y wget gnupg curl unzip make xz-utils build-essential \
  && pip install --upgrade pip \
  && pip install --no-cache-dir uv==0.9.29

RUN curl -fsS https://deb.nodesource.com/setup_20.x | bash - \
  && apt-get --no-install-recommends install -y nodejs \
  && npm i --ignore-scripts -g npm@^8 pnpm@~10.13.0 \
  && rm -rf /var/lib/apt/lists/*

COPY --from=chamber /chamber /bin/chamber

WORKDIR /pkgs
COPY packages/workers/uv.lock packages/workers/pyproject.toml /pkgs/
RUN uv sync --frozen

WORKDIR $APP_PATH
COPY /patches/ $APP_PATH/patches/
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml $APP_PATH/
COPY $SRC_CORE_PATH/package.json $DEST_CORE_PATH/
COPY $SRC_WORKERS_PATH/package.json $DEST_WORKERS_PATH/
COPY tsconfig* $APP_PATH/
COPY $SRC_CLI_PATH $DEST_CLI_PATH/
RUN pnpm install --include-workspace-root --frozen-lockfile --filter=workers... --filter=cli...

COPY nx.json tsconfig* jest* babel* .eslintrc* .prettier* .eslintrc* $APP_PATH/
COPY $SRC_CORE_PATH $DEST_CORE_PATH/
COPY $SRC_WORKERS_PATH $DEST_WORKERS_PATH/
RUN chmod +x $DEST_WORKERS_PATH/scripts/*.sh

ENV PYTHONPATH=/pkgs/.venv/lib/python3.11/site-packages \
    PATH=$PATH:/pkgs/.venv/bin

WORKDIR $DEST_WORKERS_PATH

CMD node ./scripts/runtime/local-trigger-server.js
