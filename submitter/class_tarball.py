'''
Created on Apr 13, 2012

@author: nnazirid
'''

from random import uniform
import tarfile
import shutil
import os

class tarball():
    class NoneTypeException(Exception):
        def __init__(self, name):
            self.name = name
        def __str__(self):
            if not self.name:
                return 'Error: Attribute given was None.'
            return 'Error: Attribute ' + str(self.name) + ' was NoneType'
    class PackageNotInitializedException(Exception):
        def __init__(self, pack):
            self.pack = pack
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
        else:
            self.tarball = self.workdir + tarball
        
        # hidden and temporary untar directory
        self.__unpack_directory = self.workdir + 'temp-' + self.tarball.rsplit('/')[-1].rsplit('.tgz')[0]+'/'#.rsplit('-')[1] + '/'#'prep-' + rand + '/'
        
        # init archive
        self.open_archive()
    
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
            raise tarfile.TarError('Archive is empty')
        if not os.path.exists(self.__unpack_directory):
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
            raise tarfile.TarError('Filename was NoneType')
        if not self.__tarfile:
            raise self.PackageNotInitializedException
        if not os.path.exists(filename):
            raise tarfile.TarError('File ' + filename + ' does not exist.')
        if os.path.isdir(filename):
            self.add_directory(filename) # if directory, you know
            return
        self.__tarfile.add(filename)
    
    # add directory to the archive
    def add_directory(self, directory):
        if not directory:
            raise tarfile.TarError('Directory was NoneType')
        if not self.__tarfile:
            raise self.PackageNotInitializedException
        if not os.path.exists(directory):
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
            raise tarfile.TarError('Filename was NoneType')
        if not self.__tarfile:
            raise self.PackageNotInitializedException
        # get files path
        path = self.get_filepath(filename)
        if not path:
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
            print 'WARNING: cannot repack directory ' + self.__unpack_directory + '. Directory does not exist.'
            return
        
        for filename in os.listdir(self.__unpack_directory):
            print 'Adding ' + filename + ' to tarball...'
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
            print 'WARNING: cannot repack directory ' + self.__unpack_directory + '. Directory does not exist.'
            return
        
        for filename in os.listdir(self.__unpack_directory):
            print 'Adding ' + filename + ' to tarball...'
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
