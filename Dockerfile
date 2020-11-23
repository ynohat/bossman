#####################
# AKAMAI CLI BUILDER
#########

FROM golang:alpine3.11 as akamai-cli

RUN apk add --no-cache git upx \
  && go get -d github.com/akamai/cli \
  && cd $GOPATH/src/github.com/akamai/cli \
  && go mod init \
  && go mod tidy \
  # -ldflags="-s -w" strips debug information from the executable 
  && go build -o /akamai -ldflags="-s -w" \
  # upx creates a self-extracting compressed executable
  && upx -3 -o/akamai.upx /akamai

#####################
# JSONNET BUILDER
#########

# The jsonnet CLI depends on jsonnetfmt being available on the PATH
# to prettyfy its output.
# It also makes sense to include both jsonnet and jsonnetfmt in this
# image since it is likely that the user will want to render the
# templates, not just generate them.

FROM golang:alpine3.11 as jsonnet

RUN apk add --no-cache git upx \
  && git clone https://github.com/google/go-jsonnet.git \
  && cd go-jsonnet \
  && go build -o /jsonnet -ldflags="-s -w" ./cmd/jsonnet \
  && upx -3 -o/jsonnet.upx /jsonnet \
  && go build -o /jsonnetfmt -ldflags="-s -w" ./cmd/jsonnetfmt \
  && upx -3 -o/jsonnetfmt.upx /jsonnetfmt \
  && chmod +x /jsonnet*

#####################
# FINAL
#########

FROM python:3-alpine3.11

COPY --from=akamai-cli /akamai.upx /bin/akamai
COPY --from=jsonnet /jsonnet.upx /usr/bin/jsonnet
COPY --from=jsonnet /jsonnetfmt.upx /usr/bin/jsonnetfmt

ADD . /bossman

RUN apk add --virtual devtools --no-cache musl-dev libffi-dev openssl-dev gcc \
  && python3 -m pip install /bossman  \
  && python3 -m pip install httpie httpie-edgegrid  \
  && apk add --no-cache jq bash git make

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

ENTRYPOINT ["bossman"]