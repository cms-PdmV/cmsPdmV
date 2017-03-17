import logging
import os
import shutil

from tools.locator import locator
from rest_api.BatchPrepId import BatchPrepId

class installer:
    """
    that class is meant for initializing the request directory and care of removing it

    """
    logger = logging.getLogger("mcm_error")

    def __init__(self, sub_directory, care_on_existing=True, clean_on_exit=True, is_abs_path=False):

        self.cleanup = clean_on_exit

        self.careOfExistingDirectory = care_on_existing
        if is_abs_path:
            self.directory = sub_directory
        else:
            self.directory = self.build_location(sub_directory)
        # check if directory is empty
        if not self.directory:
            self.logger.error('Data directory is not defined')
            raise Exception('Data directory is not defined.')

        # check if exists (and force)
        if os.path.exists(self.directory):
            if self.careOfExistingDirectory:
                self.logger.error( os.popen('echo %s; ls -f %s' % (self.directory, self.directory)).read())
                self.logger.error('Directory ' + self.directory + ' already exists.')
                raise Exception('Data directory %s already exists' % self.directory)
            else:
                self.logger.info('Directory ' + self.directory + ' already exists.')
        else:
            self.logger.info('Creating directory :' + self.directory)

            # recursively create any needed parents and the dir itself
            os.makedirs(self.directory)

    @staticmethod
    def build_location(sub_directory):
        l_type = locator()
        directory = l_type.workLocation()
        return os.path.abspath(directory) + '/' + sub_directory + '/'

    def location(self):
        return self.directory

    def do_not_clean(self):
        self.cleanup = False

    def close(self):
        if self.cleanup:
            try:
                self.logger.error('Deleting the directory: %s' % self.directory)
                shutil.rmtree(self.directory)
            except Exception as ex:
                self.logger.error('Could not delete directory "%s". Reason: %s' % (self.directory, ex))

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
