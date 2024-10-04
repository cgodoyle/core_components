import yaml
import os


def get_config():
    basedir = os.path.dirname(os.path.realpath(__file__))
    config_path = os.path.join(basedir, 'config.yml')
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    return config
    