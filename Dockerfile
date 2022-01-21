#####################
# AKAMAI CLI BUILDER
#########

FROM golang:alpine3.14 AS akamai-cli

RUN apk add --no-cache git \
  && git clone --depth=1 https://github.com/akamai/cli \
  && cd cli \
  && go mod tidy \
  # -ldflags="-s -w" strips debug information from the executable
  && go build -o /akamai -ldflags="-s -w" cli/main.go

#####################
# JSONNET BUILDER
#########
# The jsonnet CLI depends on jsonnetfmt being available on the PATH
# to prettyfy its output.
# It also makes sense to include both jsonnet and jsonnetfmt in this
# image since it is likely that the user will want to render the
# templates, not just generate them.
FROM golang:alpine3.14 AS jsonnet

RUN apk add --no-cache git \
  && git clone https://github.com/google/go-jsonnet.git \
  && cd go-jsonnet \
  && go build -o /jsonnet -ldflags="-s -w" ./cmd/jsonnet \
  && go build -o /jsonnetfmt -ldflags="-s -w" ./cmd/jsonnetfmt \
  && chmod +x /jsonnet*

#####################
# FINAL
#########

FROM python:3.9.10-alpine3.14

COPY --from=akamai-cli /akamai /bin/akamai
COPY --from=jsonnet /jsonnet /usr/bin/jsonnet
COPY --from=jsonnet /jsonnetfmt /usr/bin/jsonnetfmt

ADD . /bossman

RUN apk add --virtual devtools --no-cache musl-dev libffi-dev openssl-dev gcc \
  && python3 -m pip install /bossman  \
  && python3 -m pip install httpie httpie-edgegrid  \
  && apk add --no-cache jq bash git make openssh

RUN adduser -Ds /bin/bash bossman
USER bossman

ENV AKAMAI_CLI_HOME=/home/bossman/
ENV AKAMAI_CLI_CACHE_PATH=${AKAMAI_CLI_HOME}/.akamai-cli/cache
RUN mkdir -p $AKAMAI_CLI_HOME/.akamai-cli ${AKAMAI_CLI_CACHE_PATH}

RUN akamai install https://github.com/akamai-contrib/cli-jsonnet.git

USER root
RUN apk del devtools

USER bossman
VOLUME /work
WORKDIR /work

# When bossman invokes git to interact with a remote, force the git command
# to ignore host key checking.
ENV GIT_SSH_COMMAND="ssh -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no"

ENTRYPOINT ["bossman"]
