# Installation

## Option 1: Pre-built Docker container

1. Install [Docker](https://www.docker.com).
2. `docker run nilsleiffischer/gwpv:latest`

Try rendering one of the example scenes:

```sh
docker run -v $PWD:/out nilsleiffischer/gwpv:latest \
  scene Examples/Rainbow/Still.yaml -o /out
```

Docker will pull the latest pre-built image and run it. The container runs the
`gwrender` entrypoint automatically (see [Usage](usage)).

To output rendered frames and load data from your system you can mount
directories using Docker's `-v` option. In the example above we mount the
current working directory `$PWD` as the directory `/out` in the container and
use it to output frames. You can mount additional directories to make your scene
configuration files and data available in the container (see [Usage](usage)).

## Option 2: Native environment

1. Install ParaView (v5.10 or above). You can
   [download a pre-built binary](https://www.paraview.org/download/)
   or use [Spack](https://spack.readthedocs.io/en/latest/) to configure a build
   to your liking and compile it from source. Make sure to install ParaView with
   support for Python 3.
2. Create a [virtual environment](https://docs.python.org/3/tutorial/venv.html)
   with ParaView's Python. You could do this:
   ```sh
   path/to/python3 -m venv path/to/new/env
   ```
   Make sure to set up the environment with the same Python installation that
   ParaView uses. If you are unsure, try this:
   ```sh
   # Start interactive ParaView Python shell
   path/to/pvpython
   # Output path to the Python executable
   >>> import sys
   >>> sys.executable
   ```
   On macOS the `pvpython` executable is typically located in
   `/Applications/ParaView-X.Y.Z.app/Contents/bin`. The Python executable
   determined by the script above may be named `vtkpython`, in which case you
   can look for the `python3` executable in the same directory or a `bin`
   subdirectory. If you can't find ParaView's Python executable, try using a
   Python installation with the same version as ParaView's.
3. Give ParaView access to the environment. If you have created the environment
   with Python 3's `venv` then copy the `scripts/activate_this.py` script to the
   environment:

   ```sh
   cp scripts/activate_this.py path/to/new/env/bin
   ```

   Note that environments created with the `virtualenv` package include this
   script automatically and you don't need to copy it. The script is used to
   activate the environment from within Python scripts. It allows ParaView's
   Python to pick up the packages installed in the environment (see [this blog
   post for details](https://blog.kitware.com/using-pvpython-and-virtualenv/)).

   You may also want to add the ParaView executables such as `pvpython` to your
   `PATH` when the environment is activated for convenient access. To do so you
   can append the following line to `path/to/env/bin/activate` as well:

   ```sh
   export PATH="path/to/paraview/bin/:$PATH"
   ```

   On macOS you may also need to append this line to pick up the `paraview` GUI
   executable:

   ```sh
   export PATH="path/to/paraview/MacOS/:$PATH"
   ```

4. Install the following packages in the environment, making sure to use
   ParaView's HDF5 when installing `h5py`:
   ```sh
   . env/bin/activate
   HDF5_DIR=path/to/paraview/hdf5/ pip install --no-binary=h5py h5py
   pip install [-e] path/to/this/repository
   ```
   Note that the `HDF5_DIR` should have `include` and `lib` directories with
   ParaView's HDF5. On macOS it is typically
   `/Applications/ParaView-X.Y.Z.app/Contents/`. Add the `-e` flag when
   installing this repository's Python package to install it in "editable" mode,
   i.e. symlink instead of copy it so changes to the repository are reflected in
   the installation.
