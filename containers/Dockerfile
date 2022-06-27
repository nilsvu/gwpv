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
COPY setup.py ./
COPY README.md ./
COPY gwpv ./gwpv
COPY scripts/gwrender.py ./scripts/gwrender.py
COPY paraview_plugins ./paraview_plugins
COPY scene_overrides ./scene_overrides
RUN pip install .
WORKDIR /root
COPY Examples/ ./Examples

# Provide access to the pre-installed application
FROM install AS app
ENTRYPOINT [ "gwrender.py" ]
CMD [ "-h" ]
