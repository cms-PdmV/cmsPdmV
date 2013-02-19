'''
Created on Apr 13, 2012

@author: nnazirid
'''

from random import uniform
import tarfile
import shutil
import os

import logging
from tools.logger import logger as logfactory, prep2_formatter

class tarball():
    logger = logfactory('prep2')
    hname = '' # handler's name

    class NoneTypeException(Exception):
        def __init__(self, name):
            self.name = name
            if not self.name:
                tarball.logger.inject('Attribute given was None.', level='critical', handler=tarball.hname)
            else:
                tarball.logger.inject('Attribute "%s" was None' % (self.name), level='critical', handler=tarball.hname)

        def __str__(self):
            if not self.name:
                return 'Error: Attribute given was None.'
            return 'Error: Attribute ' + str(self.name) + ' was NoneType'

    class PackageNotInitializedException(Exception):
        def __init__(self, pack):
            self.pack = pack
            if not self.pack:
                tarball.logger.inject('Package is not initialized', level='error', handler=tarball.hname)
            else:
                tarball.logger.inject('Package "%s" was not initialized' % (self.pack), level='error', handler=tarball.hname)

        def __str__(self):
            if not self.pack:
                return 'Error: Package is not initialized'
            return 'Error: Package ' + str(self.pack) + ' is not initialized'
        
    def __init__(self, tarball=None, workdir=None):
        self.__tarfile = None
        self.__new = True
        
        if not workdir:
            self.workdir = os.path.abspath('.') + '/'
        else:
            self.workdir = os.path.abspath(workdir) + '/'
        
        rand = repr(int(uniform(1111,9999)))
        
        if not tarball:
            self.tarball = self.workdir + 'prep-' + rand + '.tgz'
        elif '.tgz' not in tarball:
            self.tarball = self.workdir + tarball + '.tgz'
            self.hname = tarball
        else:
            self.tarball = self.workdir + tarball
            self.hname = tarball.rsplit('.')[0]

        if self.hname:
            self.__build_logger()
        
        # hidden and temporary untar directory
        self.__unpack_directory = self.workdir + 'temp-' + self.tarball.rsplit('/')[-1].rsplit('.tgz')[0]+'/'#.rsplit('-')[1] + '/'#'prep-' + rand + '/'
        
        # init archive
        self.open_archive()

    def __build_logger(self):

        # define logger
        #logger = logging.getLogger('prep2_inject')

        # define .log file
        #self.__logfile = self.directory + self.request.get_attribute('prepid') + '.log'

            #self.logger.setLevel(1)

            # main stream handler using the stderr
            #mh = logging.StreamHandler()
            #mh.setLevel((6 - self.__verbose) * 10) # reverse verbosity

            # filename handler outputting to log
        fh = logging.FileHandler(self.workdir + '/' + self.hname + '/' + self.hname + '.log')
        fh.setLevel(logging.DEBUG) # log filename is most verbose

            # format logs
            #formatter = logging.Formatter("%(levelname)s - %(asctime)s - %(message)s")
            #mw.setFormatter(formatter)
        fh.setFormatter(prep2_formatter())

            # add handlers to main logger - good to go
        self.logger.add_inject_handler(name=self.hname, handler=fh)
            #self.logger.addHandler(mh)
    
    # checks to see if the tar exists and it opens it
    # for read or write accordingly
    def open_archive(self):
        if not self.tarball:
            raise tarfile.TarError
        
        self.__tarfile = tarfile.open(self.tarball, 'w|gz')
        self.__new = True
    
    # extract all files to the working directory
    def __extract_all_members(self):
        if self.__new:
            self.logger.inject('Archive is empty', level='error', handler=self.hname)
            raise tarfile.TarError('Archive is empty')
        if not os.path.exists(self.__unpack_directory):
            self.logger.inject('Directory "%s" does not exist. Creating ...' % self.__unpack_directory, level='warning', handler=self.hname)
            os.mkdir(self.__unpack_directory)
            
        if self.__tarfile.extractall(path=self.__unpack_directory):
            return True
        return False
    
    def __get_directory_contents(self, directory):
        contents = []
        directory = os.path.abspath(directory) + '/'
        for filename in os.listdir(directory):
            contents.append(directory + filename)
        return contents
    
    # recursive depth-first greedy algo to find
    # a filename in the directory given
    def __find(self, filename, directory):
        directory = os.path.abspath(directory) + '/'
        for filen in os.listdir(directory):
            if os.path.isdir(directory+filen):
                ret = self.__find(filename, directory+filen)
                if ret:
                    return ret
            if filename in filen:
                return directory + filen
        return None
    
    # gets the filepath to the archive contents
    def get_filepath(self, filename):
        if not filename:
            raise self.NoneTypeException('get_file() filename parameter')
        return self.__find(filename, self.__unpack_directory)
    
    # add a file or directory to the archive
    def add(self, filename):
        if not filename:
            self.logger.inject('File "None" could not be added to the archive.', level='error', handler=self.hname)
            raise tarfile.TarError('Filename was NoneType')
        if not self.__tarfile:
            raise self.PackageNotInitializedException
        if not os.path.exists(filename):
            self.logger.inject('File "%s" could not be added to the archive. Reason: file does not exist' % (filename), level='error', handler=self.hname)
            raise tarfile.TarError('File ' + filename + ' does not exist.')
        if os.path.isdir(filename):
            self.add_directory(filename) # if directory, you know
            return
        self.__tarfile.add(filename)
    
    # add directory to the archive
    def add_directory(self, directory):
        if not directory:
            self.logger.inject('Directory "None" could not be added to the archive' , level='error', handler=self.hname)
            raise tarfile.TarError('Directory was NoneType')
        if not self.__tarfile:
            raise self.PackageNotInitializedException
        if not os.path.exists(directory):
            self.logger.inject('Directory "%s" could not be added to the archive. Reason: directory does not exist' % (directory), level='error', handler=self.hname)
            raise tarfile.TarError('Directory ' + directory + ' does not exist.')
        if not os.path.isdir(directory):
            self.add(directory) # if not directory, add it normally
            return
        directory = os.path.abspath(directory) + '/'
        
        arcdir = os.path.basename(os.path.dirname(directory))
        for filename in os.listdir(directory):
            self.__tarfile.add(directory + filename, arcname=arcdir + '/' + filename, recursive=True)
    
    # remove a file or a directory from the archive
    def remove(self, filename):
        if self.__new:
            raise self.PackageNotInitializedException
        if not filename:
            self.logger.inject('File "None" could not be deleted. Reason: file does not exist', level='error', handler=self.hname)
            raise tarfile.TarError('Filename was NoneType')
        if not self.__tarfile:
            raise self.PackageNotInitializedException
        # get files path
        path = self.get_filepath(filename)
        if not path:
            self.logger.inject('File "%s" was not found in the archive.' % (filename), level='error', handler=self.hname)
            raise tarfile.TarError('File ' + filename + ' was not found in the archive')
        if os.path.isdir(path): # check if directory
            shutil.rmtree(path)
            return
        # remove file
        os.remove(path)
    
    # public accessor of __repack()
    def repack(self):
        self.__tarfile.close() # close read stream
        os.remove(self.tarball) # delete original
        self.open_archive()
        
        if not os.path.exists(self.__unpack_directory):
            self.logger.inject('Cannot repack directory "%s". Reason: directory does not exist.' % (self.__unpack_directory), level='error', handler=self.hname)
            return
        
        for filename in os.listdir(self.__unpack_directory):
            self.logger.inject('Adding "%s" to archive...' % (filename), level='debug', handler=self.hname)
            self.add(self.__unpack_directory + filename)    
        self.__tarfile.close()
        # delete temp
        shutil.rmtree(self.__unpack_directory)
        
    # this method deletes the original and repacks everything to a
    # new archive (from .tarpack directory)
    def __repack(self):
        if self.__new:
            return
        #self.__tarfile.close() # close read stream
        os.remove(self.tarball) # delete original
        self.open_archive()
        
        if not os.path.exists(self.__unpack_directory):
            self.logger.inject('Cannot repack directory "%s". Reason: directory does not exist.' % (self.__unpack_directory), level='error', handler=self.hname)
            return
        
        for filename in os.listdir(self.__unpack_directory):
            self.logger.inject('Adding "%s" to archive...' % (filename), level='debug', handler=self.hname)
            self.add(self.__unpack_directory + filename)
        self.__tarfile.close()
        # delete temp
        shutil.rmtree(self.__unpack_directory)
    
    def cleanup(self):
        try:
            # delete temp
            shutil.rmtree(self.__unpack_directory)
        except Exception as ex:
            pass
    
    def close(self):
        self.__tarfile.close()
        self.__repack() # if needed

    def get_unpack_directory(self):
        return self.__unpack_directory
