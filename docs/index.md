
![banner](banner.png)

# gwpv

This Python package uses the [ParaView](https://www.paraview.org) scientific
visualization toolkit to produce 3D renderings of gravitational-wave data from a
numerical simulation or a waveform model.

Try it now:

```sh
docker run -v $PWD:/out nilsleiffischer/gwpv:latest \
  scene Examples/Rainbow/Still.yaml -o /out
```

## Table of contents

```{eval-rst}
.. toctree::
   :maxdepth: 2

   installation
   usage
   gui
```
