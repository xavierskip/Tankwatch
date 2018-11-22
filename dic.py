#!/usr/bin/env python3
# coding: utf-8
from ruamel.yaml import YAML

class YAMLdict(dict):
    '''
    don't use like dict!
    magic methods
    https://segmentfault.com/a/1190000007256392
    https://pycoders-weekly-chinese.readthedocs.io/en/latest/issue6/a-guide-to-pythons-magic-methods.html
    '''
    def __init__(self, file):
        self.yaml = YAML()
        self.yaml.indent(mapping=4)
        self.__file = file
        with open(file) as f:
            self.__config = self.yaml.load(f)

    def __len__(self):
        return self.__config

    def __getitem__(self, key):
        return self.__config[key]
    
    def __setitem__(self, key, val):
        self.__config[key] = val
    
    def __delitem__(self, key):
        del self.__config[key]

    def __iter__(self):
        return iter(self.__config)
    
    def __reversed__(self):
        return reversed(self.__config)

    def __contains__(self, value):
        return value in self.__config
    
    def get(self, key, default=None):
        return self.__config.get(key, default)

    def save(self, file=None):
        if file:
            save_file = file
        else:
            save_file = self.__file
        with open(save_file, 'w') as f:
            self.yaml.dump(self.__config, f)

if __name__ == "__main__":
    config = YAMLdict('config.yaml')
    print(config)
    print(config['logfile'])
    print(config['alarm']['run'])
    config['alarm']['run'] = 'None'
    config.save()
    print(config.get('mail'))
    print(config['mail'].get('subject'))