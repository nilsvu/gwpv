# Data formats

## Waveform data

Waveform data is loaded by the `WaveformDataReader` plugin:

```{eval-rst}
.. autofunction:: gwpv.paraview_plugins.WaveformDataReader.WaveformDataReader
```

## Trajectory data

Trajectory data is loaded by the `TrajectoryDataReader` plugin:

```{eval-rst}
.. autofunction:: gwpv.paraview_plugins.TrajectoryDataReader.TrajectoryDataReader
```

## Horizons

Apparent horizon shapes are loaded from Paraview files that SpEC generates. Look
for files named 'AhA.pvd', 'AhB.pvd', or 'AhC.pvd'. They contain the deformed
apparent horizon surfaces over time. The surfaces will automatically be
time-interpolated and smoothed.
