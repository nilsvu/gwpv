
def extract_color_by(config):
    color_by_config = config['ColorBy']
    if isinstance(color_by_config, str):
        color_by = ('POINTS', color_by_config)
    else:
        color_by = ('POINTS', color_by_config['Field'])
        if 'Component' in color_by_config:
            color_by += (color_by_config['Component'], )
    del config['ColorBy']
    return color_by
