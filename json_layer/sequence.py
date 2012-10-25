#!/usr/bin/env python

from json_base import json_base

class sequence(json_base):
    def __init__(self,  json_input={}):
        self._json_base__schema = {
            'index':-1,
            'step':[], 
            'conditions':'',
            'event_content':[],
            'data_tier':[], 
            'beamspot':'',
            'customise':'',
            'filter_name':'',
            'geometry':'', 
            'mag_field':'', 
            'pileup':'', 
            'datamix':'', 
            'scenario':'',
            'process_name':'',
            'harvesting':'',
            'particle_table':'',
            'input_commands':'',
            'drop_descendant':False,
            'do_not_drop_on_input':'',
            'restore_rnd_seeds':'',
            'slhc':''} 

        # update self according to json_input
        self.__update(json_input)
        self.__validate()

    def __validate(self):
        if not self._json_base__json:
            return 
        for key in self._json_base__schema:
            if key not in self._json_base__json:
                raise self.IllegalAttributeName(key)
    
    # for all parameters in json_input store their values 
    # in self._json_base__json
    def __update(self,  json_input):
        self._json_base__json = {}
        if not json_input:
            self._json_base__json = self._json_base__schema
        else:
            for key in self._json_base__schema:
                if key in json_input:
                    self._json_base__json[key] = json_input[key]
                else:
                    self._json_base__json[key] = self._json_base__schema[key]

    def build(self,  
              steps=[],  
              conditions='',  
              event_content=[],
              data_tier=[],
              beamspot='',
              customise=[],
              filter_name='',
              geometry='',
              mag_field='',
              pileup='NoPileUp',
              datamix='NODATAMIXER',
              scenario='',
              process_name='',
              harvesting='',
              particle_table='',
              input_commands='',
              drop_descendant=False,
              do_not_drop_on_input='',
              restore_rnd_seeds='',
              slhc=''):
        self.set_attribute('steps',  steps)
        self.set_attribute('evt_type',  evt_type)
        self.set_attribute('conditions', conditions)
        self.set_attribute('event_content', event_content)
        self.set_attribute('data_tier', data_tier)
        self.set_attribute('beamspot', beamspot)
        self.set_attribute('customise', customise)
        self.set_attribute('filter_name', filter_name)
        self.set_attribute('geometry', geometry)
        self.set_attribute('mag_field', mag_field)
        self.set_attribute('pileup', pileup)
        self.set_attribute('datamix', datamix)
        self.set_attribute('scenario', scenario)
        self.set_attribute('process_name', process_name)
        self.set_attribute('harvesting', harvesting)
        self.set_attribute('particle_table', particle_table)
        self.set_attribute('input_commands', input_commands)
        self.set_attribute('drop_descendant', drop_descendant)
        self.set_attribute('do_not_drop_on_input', do_not_drop_on_input)
        self.set_attribute('restore_rnd_seeds', restore_rnd_seeds)
        self.set_attribute('slhc', slhc)
        return self._json_base__json

    def srepr(self,arg):
      if isinstance(arg, basestring): # Python 3: isinstance(arg, str)
        return arg.decode('utf-8')
      try:
        return ",".join(self.srepr(x) for x in arg)
      except TypeError: # catch when for loop fails
        return arg.decode('utf-8') # not a sequence so just return repr

    def to_command_line(self, attribute):
      if attribute == 'index':
        return ''
      if self.get_attribute(attribute) == '':
        return ''
      elif self.get_attribute(attribute) == True:
        return "--"+str(attribute)
      elif self.get_attribute(attribute) == False:
        return ''
      else :
        return "--"+attribute+"="+self.srepr(self.get_attribute(attribute))

    def build_cmsDriver(self):
      command = ' '

      for key in self.json():
        command += self.to_command_line(key)
        command += ' '
      return command 
    
if __name__=='__main__':
    s = sequence()
    s.print_self()
