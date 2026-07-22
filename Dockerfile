# Prebaked render environment: saves the ~2-5 billed minutes every render
# currently spends on apt-get + pip install. Built by build-image.yml.
#
# ONE-TIME STEP after the first successful build: make the package PUBLIC
# (repo -> Packages -> tiktok-render -> Package settings -> Change visibility)
# so render.yml can pull it credential-free and storage stays free. The image
# contains only open-source dependencies - no repo code, no secrets.
FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive PIP_BREAK_SYSTEM_PACKAGES=1
RUN apt-get update -q && apt-get install -y -q --no-install-recommends \
      python3 python3-pip ffmpeg git ca-certificates curl && \
    mkdir -p /etc/apt/keyrings && \
    curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
      -o /etc/apt/keyrings/githubcli-archive-keyring.gpg && \
    echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
      > /etc/apt/sources.list.d/github-cli.list && \
    apt-get update -q && apt-get install -y -q gh && \
    rm -rf /var/lib/apt/lists/*
COPY pipeline/requirements.txt /tmp/requirements.txt
RUN pip3 install -q -r /tmp/requirements.txt && rm -f /tmp/requirements.txt
