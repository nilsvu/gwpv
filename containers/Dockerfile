FROM kitware/paraview:pv-v5.8.0-osmesa-py3 AS dev
USER root

WORKDIR /root

RUN apt-get update && apt-get install -y git wget ffmpeg

# Install the same HDF5 version that Paraview uses so we can build h5py with it
RUN apt-get update && apt-get install -y g++ \
  && wget https://support.hdfgroup.org/ftp/HDF5/releases/hdf5-1.10/hdf5-1.10.5/src/hdf5-1.10.5.tar.bz2 -O hdf5.tar.bz2 \
  && tar jxf hdf5.tar.bz2 && rm hdf5.tar.bz2 && mv hdf5* hdf5 && cd hdf5 \
  && ./configure --prefix=/opt/hdf5 && make -j && make install && cd .. \
  && rm -r hdf5

# Install pip
RUN wget https://bootstrap.pypa.io/get-pip.py \
  && python get-pip.py \
  && rm get-pip.py

# Create a Python environment so our manually-installed versions of the Python
# packages take precedence over the ParaView-bundled versions.
# By setting `VIRTUAL_ENV` and `PATH` we essentially activate the environment.
ENV VIRTUAL_ENV /opt/envs/gwpv
RUN apt-get update && apt-get install -y python3-venv \
  && python -m venv $VIRTUAL_ENV
COPY scripts/activate_this.py /opt/envs/gwpv/bin
ENV PATH $VIRTUAL_ENV/bin:$PATH

# Install h5py using the manually-installed HDF5.
# Work around https://github.com/h5py/h5py/issues/1533 by installing from
# master.
RUN git clone https://github.com/h5py/h5py /opt/h5py && cd /opt/h5py \
  && python setup.py configure --hdf5=/opt/hdf5 \
  && python setup.py install && cd /root

# Install remaining Python dependencies
RUN pip install numpy scipy spherical_functions numba pyyaml tqdm astropy \
  matplotlib requests

# Make ParaView available in PATH
ENV PATH /opt/paraview/bin:$PATH

# Provide the pre-installed application as another build stage
FROM dev AS install
COPY setup.py ./
COPY README.md ./
COPY gwpv ./gwpv
COPY scripts/gwrender.py ./scripts/gwrender.py
COPY paraview_plugins ./paraview_plugins
COPY scene_overrides ./scene_overrides
RUN pip install .
WORKDIR /home/pv-user
COPY Examples/ ./Examples

# Provide access to the pre-installed application
FROM install AS app
ENTRYPOINT [ "gwrender.py" ]
CMD [ "-h" ]
