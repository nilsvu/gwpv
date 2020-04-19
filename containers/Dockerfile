
FROM kitware/paraview:pv-v5.8.0-osmesa-py3
USER root

RUN apt-get update && apt-get install -y git wget g++

WORKDIR /root

# Install pip
RUN wget https://bootstrap.pypa.io/get-pip.py \
  && python get-pip.py \
  && rm get-pip.py

# Install the same HDF5 version that Paraview uses.
RUN wget https://support.hdfgroup.org/ftp/HDF5/releases/hdf5-1.10/hdf5-1.10.5/src/hdf5-1.10.5.tar.bz2 -O hdf5.tar.bz2 \
  && tar jxf hdf5.tar.bz2 && rm hdf5.tar.bz2 && mv hdf5* hdf5 && cd hdf5 \
  && ./configure --prefix=/opt/hdf5 && make -j && make install && cd .. \
  && rm -r hdf5

# Install h5py using the same HDF5.
# Work around https://github.com/h5py/h5py/issues/1533 by installing from
# master.
RUN git clone https://github.com/h5py/h5py && cd h5py \
  && python setup.py configure --hdf5=/opt/hdf5 \
  && python setup.py install && cd ..

# Install remaining Python dependencies
RUN pip install pyyaml tqdm scipy spherical_functions numba
