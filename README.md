# gwpw

> Render **g**ravitational **w**aves from waveform data with [**P**ara**V**iew](https://www.paraview.org)

## Setting up the Python environment:

1. Create a [virtual environment](https://docs.python.org/3/tutorial/venv.html)
   **with ParaView's Python**. With Python 3 you could do this:
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
   The displayed executable may be named `vtkpython`, in which case you can look
   for the `python2` or `python3` executable in the same directory or a `bin`
   subdirectory.
2. Give ParaView access to the environment. For example, append the following
   line to `path/to/env/bin/activate` (adjusting the Python version
   appropriately):
   ```sh
   export PYTHONPATH="$VIRTUAL_ENV/lib/pythonX.Y/site-packages/:$PYTHONPATH"
   ```
   This will allow ParaView's Python to pick up the packages installed in the
   environment once the environment is activated.
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
   Note that the `path/to/paraview` on MacOS is likely something like
   `/Applications/ParaView-X.Y.Z.app/Contents` if you installed the standard
   GUI application.
3. Install the following packages in the environment, making sure to use
   ParaView's HDF5 when installing `h5py`:
   ```sh
   . env/bin/activate
   HDF5_DIR=path/to/paraview/hdf5/ pip install --no-binary=h5py h5py
   pip install scipy spherical_functions numba pyyaml tqdm
   pip install [-e] path/to/this/repository
   ```
   Note that the `HDF5_DIR` should have `include` and `lib` directories with
   ParaView's HDF5. Add the `-e` flag when installing this repository's
   Python package to install it in "editable" mode, i.e. symlink instead of copy
   it so changes to the repository are reflected in the installation.

## Exploring waveform data in the ParaView GUI application

1. We need to make ParaView aware of our Python environment and the plugins in
   this repository. This is easiest done from the command line. Before launching
   the ParaView GUI, make sure the Python environment is activated and the
   `PYTHONPATH` is set as described in the section above. Then launch ParaView
   like this:
   ```sh
   PV_PLUGIN_PATH=path/to/paraview_plugins path/to/paraview
   ```
   You will now find the plugins provided by this repository in the ParaView GUI
   when you select 'Tools' > 'Manage Plugins'.
3. Open a waveform data file in ParaView and select the _Waveform Data Reader_
   to load it.
4. Add the _Waveform To Volume_ filter to the loaded data.
5. Change the representation to _Volume_ and adjust the following properties:
   - Volume Rendering Mode (try _GPU Based_ and enable _Shade_)
   - Scalar Opacity Unit Distance (try a quarter of the domain size)
   - Transfer function (select _Edit color map_)

## Rendering without the ParaView GUI

With your Python environment activated (see section above), run
`scripts/gwrender.py` like this:

```sh
scripts/gwrender.py \
  Examples/Rainbow/Rainbow.yaml \
  --render-movie-to-file path/to/output/filename \
  --num-jobs NUM_JOBS \
```

You find examples for scene configuration files in `Examples/`.

Feel free to turn up the `NUM_JOBS` to render the frames in parallel.

If you get import errors, make sure you have activated the virtual environment
and the `PYTHONPATH` contains a reference to its `site-packages`.
