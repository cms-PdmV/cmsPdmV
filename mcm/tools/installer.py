import logging
import os
import errno

from tools.locator import locator


class installer:
    """
    that class is meant for initializing the request directory and care of removing it
    """
    logger = logging.getLogger("mcm_error")

    def __init__(self, sub_directory, ssh_session, care_on_existing=True, clean_on_exit=True, is_abs_path=False):
        # self.ssh_session: <class: ssh_executor>
        self.ssh_session = ssh_session
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
        if self._folder_exists(self.directory):
            if self.careOfExistingDirectory:
                self.logger.error('Directory ' + self.directory + ' already exists.')
                raise Exception('Data directory %s already exists' % self.directory)
            else:
                self.logger.info('Directory ' + self.directory + ' already exists.')
        else:
            self.logger.info('Creating directory :' + self.directory)
            self._create_folder(self.directory)

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
                self._remove_folder(self.directory)
            except Exception as ex:
                self.logger.error('Could not delete directory "%s". Reason: %s' % (self.directory, ex))

    def _folder_exists(self, path):
        """
        Checks if a folder exists using the remote session.

        Arguments:
            path (str): Absolute path to check.

        Returns:
            bool: True if the folder exists, False otherwise.
        """
        try:
            _ = self.ssh_session.ssh_client.open_sftp().listdir(path)
            return True
        except IOError as e:
            if e.errno == errno.ENOENT:
                # Folder doesn't exists
                return False
            raise e
        
    def _create_folder(self, path):
        """
        Create a folder using the remote session.

        Arguments:
            path (str): Absolute path to create.
        """
        _, stdout, stderr = self.ssh_session.execute("mkdir -p '%s'" % (path))
        if not stdout and not stderr:
            msg = "SSH error to create a folder: %s" % (path)
            self.logger.error(msg)
            raise RuntimeError(msg)
        
        error = stderr.read()
        if error:
            raise RuntimeError("Unable to create the folder: %s - Description: %s" % (path, error))

        if not self._folder_exists(path):
            raise RuntimeError("Folder not found (%s), it should exist" % (path))
        
    def _remove_folder(self, path):
        """
        Removes a folder using the remote session.

        Arguments:
            path (str): Absolute path to remove.
        """
        _, stdout, stderr = self.ssh_session.execute("rm -rf '%s'" % (path))
        if not stdout and not stderr:
            msg = "SSH error to remove a folder: %s" % (path)
            self.logger.error(msg)
            raise RuntimeError(msg)
        
        error = stderr.read()
        if error:
            raise RuntimeError("Unable to remove the folder: %s - Description: %s" % (path, error))

        if self._folder_exists(path):
            raise RuntimeError("Folder found (%s), it should not exist" % (path))

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
