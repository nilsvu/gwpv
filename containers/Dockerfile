# How to update the container:
#
# 1. Build the dev container:
#
#     docker build -f containers/Dockerfile --target=dev -t nilsleiffischer/gwpv:latest-dev .
#
# 2. Push to Dockerhub
#
#     docker push nilsleiffischer/gwpv:latest-dev
#
# The production container (target 'app') is built automatically by CI.

FROM ubuntu:latest AS dev
USER root

ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /root

RUN apt-get -yqq update \
 && apt-get -yqq upgrade \
 && apt-get -yqq install --no-install-recommends \
      curl \
      ffmpeg \
      git \
      make \
      python3 \
      python3-pip \
      python-is-python3 \
      wget \
  && apt-get clean

# Install ParaView
RUN wget -O paraview.tar.gz --no-check-certificate "https://www.paraview.org/paraview-downloads/download.php?submit=Download&version=v5.10&type=binary&os=Linux&downloadFile=ParaView-5.10.1-osmesa-MPI-Linux-Python3.9-x86_64.tar.gz" \
  && tar -xzf paraview.tar.gz \
  && rm paraview.tar.gz \
  && mv ParaView-* /opt/paraview

ENV PYTHONPATH="/usr/local/lib/python3.10/dist-packages:/opt/paraview/lib/python3.9/site-packages" \
  PATH="/opt/paraview/bin:$PATH"

# Provide the pre-installed application as another build stage
FROM dev AS install
WORKDIR /opt/gwpv
COPY pyproject.toml ./
COPY setup.cfg ./
COPY README.md ./
COPY LICENSE ./
COPY gwpv ./gwpv
RUN pip install .
WORKDIR /root
COPY Examples/ ./Examples

# Provide access to the pre-installed application
FROM install AS app
ENTRYPOINT [ "gwrender" ]
CMD [ "-h" ]
