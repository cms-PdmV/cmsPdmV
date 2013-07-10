#!/usr/bin/env python

from json_base import json_base

class sequence(json_base):
    def __init__(self,  json_input={}):
        self._json_base__schema = {
            'index':-1,
            'step':[], 
            'conditions':'',
            'eventcontent':[],
            'datatier':[], 
            'beamspot':'',
            'customise':'',
            'filtername':'',
            'geometry':'', 
            'magField':'', 
            'pileup':'', 
            'datamix':'', 
            'scenario':'',
            'processName':'',
            'harvesting':'',
            'particle_table':'',
            'inputCommands':'',
            'dropDescendant':False,
            'donotDropOnInput':'',
            'restoreRNDSeeds':'',
            'slhc':'',
            'inputEventContent':'',
            'gflash':'',
            'geometry':'',
            'repacked':'',
            'runsScenarioForMC':'',
            'hltProcess':'',
            'triggerResultsProcess':'',
            'runsAndWeightsForMC':'',
            'customise_commands':'',
            'inputCommands':'',
            'custom_conditions':'',
            'extra':''} 

        ## how to get the options ?
        # in cmssw
        # import  Configuration.PyReleaseValidation.Options as opt
        # map( lambda s : s.replace('--','') ,opt.parser._long_opt.keys() )
        
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

    """  
    def build(self,  
              steps=[],  
              conditions='',  
              eventcontent=[],
              datatier=[],
              beamspot='',
              customise=[],
              filtername='',
              geometry='',
              magField='',
              pileup='NoPileUp',
              datamix='NODATAMIXER',
              scenario='',
              processName='',
              harvesting='',
              particle_table='',
              inputCommands='',
              dropDescendant=False,
              donotDropOnInput='',
              restoreRNDSeeds='',
              slhc=''):
        self.set_attribute('steps',  steps)
        self.set_attribute('evt_type',  evt_type)
        self.set_attribute('conditions', conditions)
        self.set_attribute('eventcontent', eventcontent)
        self.set_attribute('datatier', datatier)
        self.set_attribute('beamspot', beamspot)
        self.set_attribute('customise', customise)
        self.set_attribute('filtername', filtername)
        self.set_attribute('geometry', geometry)
        self.set_attribute('magField', magField)
        self.set_attribute('pileup', pileup)
        self.set_attribute('datamix', datamix)
        self.set_attribute('scenario', scenario)
        self.set_attribute('processName', processName)
        self.set_attribute('harvesting', harvesting)
        self.set_attribute('particle_table', particle_table)
        self.set_attribute('inputCommands', inputCommands)
        self.set_attribute('dropDescendant', dropDescendant)
        self.set_attribute('donotDropOnInput', donotDropOnInput)
        self.set_attribute('restoreRNDSeeds', restoreRNDSeeds)
        self.set_attribute('slhc', slhc)
        return self._json_base__json
        """

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
      elif attribute == 'extra' and self.get_attribute(attribute):
          return self.get_attribute(attribute)
      elif self.get_attribute(attribute):
        #return "--"+attribute+"="+self.srepr(self.get_attribute(attribute))
          return "--"+attribute+" "+self.srepr(self.get_attribute(attribute))
      else:
          return ''

    def to_string(self):
        text=''
        keys=self.json().keys()
        keys.sort()
        for key in keys:
            if key in []: continue
            text+=key+str(self.get_attribute(key))
        return text

    def build_cmsDriver(self):
      ### always MC in McM. better to say it
      command = ' --mc '

      for key in self.json():
        command += self.to_command_line(key)
        command += ' '
      return command 
    
if __name__=='__main__':
    s = sequence()
    s.print_self()
