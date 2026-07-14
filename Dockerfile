FROM hashicorp/terraform:1.15.8 AS terraform

FROM debian:bookworm-slim

ARG OPENCODE_VERSION=1.18.1

ENV DEBIAN_FRONTEND=noninteractive \
    HOME=/home/opencode \
    OPENCODE_CONFIG_DIR=/home/opencode/.config/opencode \
    PATH=/home/opencode/.opencode/bin:${PATH}

# Keep the runtime small while providing the tools OpenCode and this Skill use.
RUN apt-get update \
    && apt-get install --yes --no-install-recommends \
        bash \
        ca-certificates \
        curl \
        git \
        less \
        openssh-client \
        python3 \
        python3-yaml \
        ripgrep \
        tini \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /bin/bash --uid 1000 opencode

COPY --from=terraform /bin/terraform /usr/local/bin/terraform

USER opencode

# Use OpenCode's official installer and pin the default for reproducible builds.
RUN curl -fsSL https://opencode.ai/install --output /tmp/opencode-install \
    && bash /tmp/opencode-install --version "${OPENCODE_VERSION}" --no-modify-path \
    && rm /tmp/opencode-install \
    && opencode --version \
    && terraform version

USER root

# Store the Skill outside the config volume so mounting that volume cannot hide it.
COPY --chown=opencode:opencode \
    SKILL.md \
    requirements.txt \
    /opt/opencode-skills/huawei-cloud-terraform/
COPY --chown=opencode:opencode agents /opt/opencode-skills/huawei-cloud-terraform/agents
COPY --chown=opencode:opencode policies /opt/opencode-skills/huawei-cloud-terraform/policies
COPY --chown=opencode:opencode references /opt/opencode-skills/huawei-cloud-terraform/references
COPY --chown=opencode:opencode schemas /opt/opencode-skills/huawei-cloud-terraform/schemas
COPY --chown=opencode:opencode scripts /opt/opencode-skills/huawei-cloud-terraform/scripts
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh

RUN chmod 0755 /usr/local/bin/docker-entrypoint.sh \
    && mkdir -p /home/opencode/.config/opencode /workspace \
    && chown -R opencode:opencode /home/opencode/.config /workspace

USER opencode
WORKDIR /workspace

# Persist OpenCode configuration, agents, plugins, credentials, and global skills.
VOLUME ["/home/opencode/.config/opencode"]

EXPOSE 4096

ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/docker-entrypoint.sh"]
CMD ["opencode"]
