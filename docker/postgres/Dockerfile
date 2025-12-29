FROM pgvector/pgvector:pg16

ARG PG_UID=1024
ARG PG_GID=100

USER root

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        ca-certificates \
        flex \
        bison \
        git \
        postgresql-server-dev-16 \
    && git clone --depth 1 https://github.com/apache/age.git /tmp/age \
    && cd /tmp/age \
    && make install \
    && rm -rf /tmp/age \
    && apt-get purge -y --auto-remove \
        build-essential \
        flex \
        bison \
        git \
        postgresql-server-dev-16 \
    && rm -rf /var/lib/apt/lists/*

RUN echo "shared_preload_libraries = 'age'" >> /usr/share/postgresql/postgresql.conf.sample

RUN if ! getent group "${PG_GID}" >/dev/null; then groupadd -g "${PG_GID}" pguser; fi \
    && if ! getent passwd "${PG_UID}" >/dev/null; then useradd -u "${PG_UID}" -g "${PG_GID}" -m pguser; fi

USER ${PG_UID}:${PG_GID}
