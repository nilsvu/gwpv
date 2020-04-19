import os


def path(config, relative_to='.'):
    assert isinstance(config, str), "Expected file system path but got: {}".format(config)
    if config.startswith('/'):
        return os.path.realpath(config)
    elif config.startswith('~'):
        return os.path.realpath(os.path.expanduser(config))
    else:
        return os.path.realpath(os.path.join(relative_to, config))


def file_and_subfile(config):
    if isinstance(config, str):
        file_and_subfile = config.split(':')
        assert len(
            file_and_subfile
        ) <= 2, "Only one ':' to separate file and subfile is allowed in ''.".format(
            config)
        if len(file_and_subfile) == 1:
            file_and_subfile.append("/")
        file_and_subfile[0] = path(file_and_subfile[0])
        return file_and_subfile
    else:
        return (path(config['File']),
                config['Subfile'] if 'Subfile' in config else '/')
