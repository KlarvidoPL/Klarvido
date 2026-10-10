# CI-only equivalent of stripe/stripe-mock:v0.170.0, using its official release.
FROM mirror.gcr.io/library/alpine:3.19
ARG TARGETARCH
RUN apk --no-cache add ca-certificates \
    && case "$TARGETARCH" in \
        amd64) checksum=9c403e1664bf497b955b10a8e36f59d1f485ea2ebe2bfbdefa72d5cb50c73bb6 ;; \
        arm64) checksum=fedda1ec691a646b7308e79a617aab6dfa4e854574594b8e86efbfa504f08601 ;; \
        *) exit 1 ;; \
    esac \
    && wget -O /tmp/stripe-mock.tar.gz "https://github.com/stripe/stripe-mock/releases/download/v0.170.0/stripe-mock_0.170.0_linux_${TARGETARCH}.tar.gz" \
    && echo "$checksum  /tmp/stripe-mock.tar.gz" | sha256sum -c - \
    && tar -xzf /tmp/stripe-mock.tar.gz -C /bin stripe-mock \
    && rm /tmp/stripe-mock.tar.gz
ENTRYPOINT ["/bin/stripe-mock", "-http-port", "12111", "-https-port", "12112"]
EXPOSE 12111 12112
