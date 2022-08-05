import paraview.servermanager as pvserver
import paraview.simple as pv

from gwpv.scene_configuration import parse_as


def set_background(bg_config, view, datasources):
    if isinstance(bg_config, list):
        if isinstance(bg_config[0], list):
            assert (
                len(bg_config) == 2
            ), "When 'Background' is a list of colors, it must have 2 entries."
            try:
                view.BackgroundColorMode = "Gradient"
            except AttributeError:
                # ParaView < 5.10
                pass
            view.Background = parse_as.color(bg_config[0])
            view.Background2 = parse_as.color(bg_config[1])
        else:
            try:
                view.BackgroundColorMode = "Single Color"
            except AttributeError:
                # ParaView < 5.10
                pass
            view.Background = parse_as.color(bg_config)
        try:
            view.UseColorPaletteForBackground = 0
        except AttributeError:
            # ParaView < 5.10
            pass
    else:
        view.BackgroundColorMode = "Texture"
        skybox_datasource = bg_config["Datasource"]
        background_texture = pvserver.rendering.ImageTexture(
            FileName=parse_as.path(datasources[skybox_datasource])
        )
        background_sphere = pv.Sphere(
            Radius=bg_config["Radius"], ThetaResolution=100, PhiResolution=100
        )
        background_texture_map = pv.TextureMaptoSphere(Input=background_sphere)
        pv.Show(
            background_texture_map,
            view,
            Texture=background_texture,
            BackfaceRepresentation="Cull Frontface",
            Ambient=1.0,
        )
