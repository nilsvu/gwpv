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

1. Install ParaView (v5.13 or above). You can
   [download a pre-built binary](https://www.paraview.org/download/)
   or use [Spack](https://spack.readthedocs.io/en/latest/) to compile it from
   source. For example, download ParaView 6.0 for a Linux machine like this:
   ```sh
   wget -O paraview.tar.gz "https://www.paraview.org/paraview-downloads/download.php?submit=Download&version=v6.0&type=binary&os=Linux&downloadFile=ParaView-6.0.0-RC3-MPI-Linux-Python3.12-x86_64.tar.gz"
   tar -xzf paraview.tar.gz
   mv ParaView-* paraview
   rm paraview.tar.gz
   export PARAVIEW_DIR=$PWD/paraview
   # optional: add to PATH
   export PATH="$PARAVIEW_DIR/bin:$PATH"
   ```
2. Create a Python environment with the same Python version as your ParaView
   installation. To find out what Python version ParaView uses you can do this:
   ```sh
   $PARAVIEW_DIR/bin/pvpython -c "import sys; print(sys.version)"
   ```

   If you don't have this Python version already installed, one way to install
   it is with [pyenv](https://github.com/pyenv/pyenv.git):
   ```sh
   export PYENV_ROOT="$HOME/.pyenv"  # change location if you prefer
   git clone https://github.com/pyenv/pyenv.git $PYENV_ROOT
   export PATH="$PYENV_ROOT/bin:$PATH"
   eval "$(pyenv init - bash)"
   pyenv install 3.12  # or whatever version ParaView uses
   pyenv shell 3.12  # select the Python version for this shell
   ```

   Now create a [virtual environment](https://docs.python.org/3/tutorial/venv.html)
   with this Python version where you can install packages:
   ```sh
   export VENV_DIR=$HOME/envs/gwpv  # change to your preferred location
   python3 -m venv $VENV_DIR
   source $VENV_DIR/bin/activate
   ```
3. Install `gwpv` in the Python environment:
   ```sh
   pip install [-e] path/to/this/repository
   ```
   The optional `-e` flag installs `gwpv` in "editable" mode, i.e. symlinks
   instead of copies it so changes to the repository are reflected in the
   installation.
4. Point the Python environment to your ParaView installation. You can do this
   by adding a `.pth` file to the Python environment:
   ```sh
   echo "$PARAVIEW_DIR/lib/python3.12/site-packages/" > $VENV_DIR/lib/python3.12/site-packages/paraview.pth
   ```

   Alternatively, you can set the `PYTHONPATH` environment variable:
   ```sh
   export PYTHONPATH=$PARAVIEW_DIR/lib/python3.12/site-packages:$PYTHONPATH
   ```
