# Usage

Try rendering one of the example scenes like this:

```sh
gwrender scene Examples/Rainbow/Still.yaml -o ./
```

The rendered scene is a still frame defined by the configuration file
[`Examples/Rainbow/Still.yaml`](Examples/Rainbow/Still.yaml). It is based on
[`Examples/Rainbow/Rainbow.yaml`](Examples/Rainbow/Rainbow.yaml) which, by
itself, defines a short movie:

```sh
gwrender scene Examples/Rainbow/Rainbow.yaml \
  --render-movie-to-file ./Rainbow
  --num-jobs NUM_JOBS
```

Feel free to turn up `NUM_JOBS` to render the frames in parallel.

## Compose configuration files to define a scene

A _scene_ is defined by a stack of one or more YAML configuration files. The
configuration files can be source-controlled and shared, so each visualization
is reproducible. See
[`Examples/Rainbow/Rainbow.yaml`](Examples/Rainbow/Rainbow.yaml) for an example
of a scene configuration file.

Multiple configuration files can be stacked to compose a scene. Configurations
in later files override those in earlier files. You find a collection of useful
configuration files in the directory [`gwpv/scene_overrides/`](gwpv/scene_overrides/).
They are found automatically by `gwrender`, so you can, for example, easily
adjust the background of the scene or the rendering resolution:

```sh
gwrender \
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
gwrender scenes Examples/Rainbow/Scenes.yaml -o ./ --num-jobs NUM_JOBS
```

To render a single scene from the file, use the `scene` entrypoint and specify
the name of the scene:

```sh
gwrender scene Examples/Rainbow/Scenes.yaml:Rainbow -o ./ --num-jobs NUM_JOBS
```

Sometimes it can be useful to override particular configurations from the
command line, for example to reduce the frame rate for a test rendering. To do
so, you can pass key-value pairs of scene configuration options to `gwrender`
like this:

```sh
gwrender scene Examples/Rainbow/Rainbow.yaml -o ./ \
  --override Animation.FrameRate=1
```

The key of each `override` is parsed as the key-path into the scene
configuration to replace, and its value is parsed as YAML.

## Datasources

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
