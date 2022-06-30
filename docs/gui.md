# ParaView GUI plugins

With the GUI plugins you can explore waveform data in the ParaView application:

1. We need to make ParaView aware of our Python environment and the plugins in
   this repository. This is easiest done from the command line. Before launching
   the ParaView GUI, make sure the Python environment is activated as described
   in [Installation](installation). Then launch ParaView like this:
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
