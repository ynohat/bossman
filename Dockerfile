FROM python:3.8
RUN pip3 install bossman
RUN useradd -ms /bin/bash bossman
USER bossman
VOLUME work
WORKDIR work
ENTRYPOINT ["bossman"]