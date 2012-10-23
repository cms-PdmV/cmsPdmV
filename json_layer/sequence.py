#!/usr/bin/env python

from json_base import json_base

class sequence(json_base):
    def __init__(self,  json_input={}):
        self._json_base__schema = {
            'index':-1,
            'nameorfragment': 'STEP',
            'step':[], 
            'conditions':'',
            'event_content':[],
            'data_tier':[], 
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
            'donotDropOnInput':True,
            'restoreRNDSeeds':'',
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
              nameorfragment='STEP', 
              conditions='',  
              event_content=[],
              data_tier=[],
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
              donotDropOnInput=True,
              restoreRNDSeeds='',
              slhc=''):
        self.set_attribute('steps',  steps)
        self.set_attribute('nameorfragment',  nameorfragment)
        self.set_attribute('conditions', conditions)
        self.set_attribute('event_content', event_content)
        self.set_attribute('data_tier', data_tier)
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

    def srepr(self,arg):
      if isinstance(arg, basestring): # Python 3: isinstance(arg, str)
        return repr(arg).decode('utf-8')
      try:
        return ",".join(self.srepr(x) for x in arg)
      except TypeError: # catch when for loop fails
        return repr(arg).decode('utf-8') # not a sequence so just return repr
 

    def tocommandline(self, attribute):
      if attribute == 'index':
        return ''
      if attribute == 'nameorfragment':
        return self.get_attribute(attribute).decode('utf-8')
      if self.get_attribute(attribute) == '':
        return ''
      elif self.get_attribute(attribute) == True:
        return "--"+str(attribute)
      elif self.get_attribute(attribute) == False:
        return ''
      else :
        return "--"+attribute+"="+self.srepr(self.get_attribute(attribute))  


    def buildCmsDriver(self): 
      command = 'cmsDriver.py '
      for key in self._json_base__schema:
        print key
        command += self.tocommandline(key)
        command += ' ' 
      return command

      
    
if __name__=='__main__':
    s = sequence()
    s.print_self()
    #print s.buildCmsDriver()
