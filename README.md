
<p align="center" id="banner"><img src="https://raw.githubusercontent.com/nilsleiffischer/gwpv/master/docs/banner.png"></p>

# gwpv

![Tests](https://github.com/nilsleiffischer/gwpv/workflows/Tests/badge.svg)

This Python package uses the [ParaView](https://www.paraview.org) scientific
visualization toolkit to produce 3D renderings of gravitational-wave data from a
numerical simulation or a waveform model.

Try it now:

```sh
docker run -v $PWD:/out nilsleiffischer/gwpv:latest \
  scene Examples/Rainbow/Still.yaml -o /out
```

## Table of contents

- [Installation](#installation)
  - [Option 1: Pre-built Docker container](#option-1-pre-built-docker-container)
  - [Option 2: Native environment](#option-2-native-environment)
- [Usage](#usage)
  - [Compose configuration files to define a scene](#compose-configuration-files-to-define-a-scene)
  - [Datasources](#datasources)
- [Explore waveform data in the ParaView GUI application](#explore-waveform-data-in-the-paraview-gui-application)
- [Gallery](#gallery)
- [Licensing and credits](#licensing-and-credits)

## Installation

### Option 1: Pre-built Docker container

1. Install [Docker](https://www.docker.com).
2. `docker run nilsleiffischer/gwpv:latest`

Docker will pull the latest pre-built image and run it. The container runs the
`gwrender.py` entrypoint automatically (see [Usage](#usage)). To output rendered
frames and load data from your system you can mount directories using Docker's
`-v` option. Try rendering one of the example scenes:

```sh
docker run -v $PWD:/out nilsleiffischer/gwpv:latest \
  scene Examples/Rainbow/Still.yaml -o /out
```

Here we mount the current working directory `$PWD` as the directory `/out` in
the container and use it to output frames. You can mount additional directories
to make your scene configuration files and data available in the container (see
[Usage](#usage)).

### Option 2: Native environment

> It is strongly recommended to use Python 3 for this program. In particular,
> parallel rendering may not work with Python 2 and setting up the environment
> with Python 3's [`venv`](https://docs.python.org/3/library/venv.html) is more
> robust than Python 2's `virtualenv`.

1. Install [ParaView](https://www.paraview.org/download/). Prefer versions
   with Python 3. This program was tested thoroughly with ParaView version 5.8.
2. Create a [virtual environment](https://docs.python.org/3/tutorial/venv.html)
   with ParaView's Python. With Python 3 you could do this:
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
   can look for the `python2` or `python3` executable in the same directory or a
   `bin` subdirectory.
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
   `/Applications/ParaView-X.Y.Z.app/Contents/`.  Add the `-e` flag when
   installing this repository's Python package to install it in "editable" mode,
   i.e. symlink instead of copy it so changes to the repository are reflected in
   the installation. On Python 2, `pip install llvmlite==0.31.0` manually
   because later versions drop support for Python 2.

## Usage

Try rendering one of the example scenes like this:

```sh
gwrender.py scene Examples/Rainbow/Still.yaml -o ./
```

The rendered scene is a still frame defined by the configuration file
[`Examples/Rainbow/Still.yaml`](Examples/Rainbow/Still.yaml). It is based on
[`Examples/Rainbow/Rainbow.yaml`](Examples/Rainbow/Rainbow.yaml) which, by
itself, defines a short movie:

```sh
gwrender.py scene Examples/Rainbow/Rainbow.yaml \
  --render-movie-to-file ./Rainbow
  --num-jobs NUM_JOBS
```

Feel free to turn up `NUM_JOBS` to render the frames in parallel.

### Compose configuration files to define a scene

A _scene_ is defined by a stack of one or more YAML configuration files. The
configuration files can be source-controlled and shared, so each visualization
is reproducible. See
[`Examples/Rainbow/Rainbow.yaml`](Examples/Rainbow/Rainbow.yaml) for an example
of a scene configuration file.

Multiple configuration files can be stacked to compose a scene. Configurations
in later files override those in earlier files. You find a collection of useful
configuration files in the directory [`scene_overrides/`](scene_overrides/).
They are found automatically by `gwrender.py`, so you can, for example, easily
adjust the background of the scene or the rendering resolution:

```sh
gwrender.py \
  scene Examples/Rainbow/Still.yaml Background/Light Resolutions/High -o ./
```

Scene configuration files can specify that they always include others so you
don't have to build the composition stack on the command line:

```yaml
Include:
  - Background/Light
  - Resolutions/High
```

You can also list scene compositions in a file such as
[`Examples/Rainbow/Scenes.yaml`](Examples/Rainbow/Scenes.yaml):

```yaml
Scenes:
  - Name: RainbowLight
    Composition:
      - Rainbow
      - Background/Light
```

You can sequentially render all scenes listed in such a file by calling the
`scenes` entrypoint:

```sh
gwrender.py scenes Examples/Rainbow/Scenes.yaml -o ./ --num-jobs NUM_JOBS
```

To render a single scene from the file, use the `scene` entrypoint and specify
the name of the scene:

```sh
gwrender.py scene Examples/Rainbow/Scenes.yaml:Rainbow -o ./ --num-jobs NUM_JOBS
```

Sometimes it can be useful to override particular configurations from the
command line, for example to reduce the frame rate for a test rendering. To do
so, you can pass key-value pairs of scene configuration options to `gwrender.py`
like this:

```sh
gwrender.py scene Examples/Rainbow/Rainbow.yaml -o ./ \
  --override Animation.FrameRate=1
```

The key of each `override` is parsed as the key-path into the scene
configuration to replace, and its value is parsed as YAML.

### Datasources

To specify datasources for the rendered scenes, such as waveform data or horizon
shapes from a simulation, the configuration file
[`Examples/Rainbow/Rainbow.yaml`](Examples/Rainbow/Rainbow.yaml) includes
[`Examples/Rainbow/Datasources.yaml`](Examples/Rainbow/Datasources.yaml).

> Specifying the datasources in a separate configuration file allows excluding
> it from source control, e.g. to set local file system paths on a particular
> rendering machine.

Datasources can refer to a local file system path or a remote URL. They will be
downloaded and cached, if needed. For example, you can pick any simulation from
the [SXS waveform catalog](https://data.black-holes.org/waveforms/catalog.html)
and use the URL to one of its public waveform data files:

```yaml
Datasources:
  Waveform:
    File: https://zenodo.org/record/3321679/files/Lev3/rhOverM_Asymptotic_GeometricUnits_CoM.h5
    Subfile: Extrapolated_N2.dir
    Cache: ./waveform_data_cache
```

## Explore waveform data in the ParaView GUI application

1. We need to make ParaView aware of our Python environment and the plugins in
   this repository. This is easiest done from the command line. Before launching
   the ParaView GUI, make sure the Python environment is activated as described
   in [Installation](#installation). Then launch ParaView like this:
   ```sh
   PV_PLUGIN_PATH=path/to/paraview_plugins path/to/paraview
   ```
   You will now find the plugins provided by this repository in the ParaView GUI
   when you select 'Tools' > 'Manage Plugins'.
3. Open a waveform data file in ParaView and select the _Waveform Data Reader_
   to load it. Waveform data files in
   [SpEC](https://www.black-holes.org/code/SpEC.html)'s output format are
   currently supported.
4. Add the _Waveform To Volume_ filter to the loaded data.
5. Change the representation to _Volume_ and adjust the following properties:
   - Volume Rendering Mode (try _GPU Based_ and enable _Shade_)
   - Scalar Opacity Unit Distance (try a quarter of the domain size)
   - Transfer function (select _Edit color map_)

## Gallery

Here's a few images and movies produces with this software package:

### GW190412

[![GW190412 PanoramaLargeScaleNoTail_frame.000023](https://www.aei.mpg.de/2490709/original-1587376764.png?t=eyJ3aWR0aCI6ODAwLCJoZWlnaHQiOjYwMCwib2JqX2lkIjoyNDkwNzA5fQ==--a38cd313aa655bd3990f4172ade0a414a3729a1a)](https://dcc.ligo.org/DocDB/0167/G2000575/005/PanoramaLargeScaleNoTail_frame.000023_watermarked.png)

[![GW190412 CloseupSlowdownWithSpins_frame.000003](https://www.aei.mpg.de/2495564/original-1587376766.png?t=eyJ3aWR0aCI6ODAwLCJoZWlnaHQiOjYwMCwib2JqX2lkIjoyNDk1NTY0fQ==--0d65e7118cefc0b8b3f6e89308b7e252b601593e)](https://dcc.ligo.org/DocDB/0167/G2000575/005/CloseupSlowdownWithSpins_frame.000003_watermarked.png)

[![GW190412 FaceOnMerger](https://www.aei.mpg.de/2491271/original-1587376765.png?t=eyJ3aWR0aCI6ODAwLCJoZWlnaHQiOjYwMCwib2JqX2lkIjoyNDkxMjcxfQ==--4c1703f7d733854bbf740439a1dba0da9247d4b5)](https://dcc.ligo.org/public/0167/G2000575/005/FaceOnMerger_frame_watermarked.png)

- More information and images available at: https://www.aei.mpg.de/2482853/gw190412 and https://dcc.ligo.org/LIGO-G2000575/public
- Video:

  [![GW190412 video](http://img.youtube.com/vi/5AkT4bPk-00/0.jpg)](http://www.youtube.com/watch?v=5AkT4bPk-00)
- Selected media coverage:
  - https://www.nature.com/articles/d41586-020-01153-7
  - https://www.sciencenews.org/article/gravitational-waves-unevenly-sized-black-holes-ligo-virgo
  - https://www.aei.mpg.de/2482444/a-signal-like-none-before
  - https://www.ligo.org/detections/GW190412
  - https://www.ligo.caltech.edu/news/ligo20200420
  - https://www.spektrum.de/news/neuartiges-gravitationswellensignal/1725506

### GW190814

[![GW190814 MergerFaceOnAllModes](https://www.aei.mpg.de/2513085/original-1592920551.png?t=eyJ3aWR0aCI6ODAwLCJoZWlnaHQiOjYwMCwib2JqX2lkIjoyNTEzMDg1fQ==--8d9006ed5e85c48a6fa5554b589df5e64d2b2708)](https://dcc.ligo.org/DocDB/0168/G2000730/003/MergerFaceOnAllModes_frame_watermarked.png)

[![GW190814 PanoramaModesCompositionFaceOn_frame.000003](https://www.aei.mpg.de/2514336/original-1592920549.png?t=eyJ3aWR0aCI6ODAwLCJoZWlnaHQiOjYwMCwib2JqX2lkIjoyNTE0MzM2fQ==--c443f111f62a5f474943efd100a109a33a52f7df)](https://dcc.ligo.org/DocDB/0168/G2000730/003/PanoramaModesCompositionFaceOn_frame.000003_watermarked.png)

[![GW190814 PanoramaAllModesFaceOn_frame.000006](https://www.aei.mpg.de/2513506/original-1592920551.png?t=eyJ3aWR0aCI6ODAwLCJoZWlnaHQiOjYwMCwib2JqX2lkIjoyNTEzNTA2fQ==--6d792b86639fcb318352d55d43b429c578363de1)](https://dcc.ligo.org/DocDB/0168/G2000730/003/PanoramaAllModesFaceOn_frame.000006_watermarked.png)

- More information and images available at: https://www.aei.mpg.de/2509258/gw190814 and https://dcc.ligo.org/LIGO-G2000730/public
- Video:

  [![GW190814 video](http://img.youtube.com/vi/p4xHz-If6kw/0.jpg)](http://www.youtube.com/watch?v=p4xHz-If6kw)

- Selected media coverage:
  - https://www.aei.mpg.de/2508194/a-black-hole-with-a-puzzling-companion
  - https://www.ligo.org/detections/GW190814
  - https://www.space.com/smallest-black-hole-biggest-neutron-stary-mystery-object.html
  - https://www.dailymail.co.uk/sciencetech/article-8451939/Mysterious-cosmic-object-lighter-black-hole-heavier-neutron-star-discovered.html

## Licensing and credits

This code is distributed under the MIT license. Please see the
[`LICENSE`](LICENSE) for details. When you use code from this project or
publish media produced by this code, please include a reference back to the
[nilsleiffischer/gwpv](https://github.com/nilsleiffischer/gwpv) repository.

Copyright (c) 2020 Nils Leif Fischer
