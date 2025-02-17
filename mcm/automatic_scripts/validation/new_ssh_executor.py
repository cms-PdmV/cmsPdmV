import os
import logging
import json
import paramiko
import paramiko.ssh_gss


class SSHExecutor():
    """
    SSH executor allows to perform remote commands and upload/download files
    """

    def __init__(self, host, credentials_path):
        self.ssh_client = None
        self.ftp_client = None
        self.logger = logging.getLogger()
        self.remote_host = host
        self.credentials_file_path = credentials_path
        self.timeout = 3600

    def setup_ssh(self):
        """
        Initiate SSH connection and save it as self.ssh_client
        """
        self.logger.debug('Will set up ssh')
        if self.ssh_client:
            self.close_connections()

        with open(self.credentials_file_path) as json_file:
            credentials = json.load(json_file)

        self.logger.info('Credentials loaded successfully: %s', credentials['username'])
        self.ssh_client = paramiko.SSHClient()
        self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        gssapi_available = self._gssapi_with_mic_available()
        if gssapi_available and self._use_gssapi_with_mic_for_auth():
            self.logger.info(
                'Authenticating to remote host (%s) using: gssapi-with-mic',
                self.remote_host
            )
            self.ssh_client.connect(
                self.remote_host,
                username=credentials["username"],
                gss_auth=gssapi_available,
                timeout=30
            )
        else:
            self.logger.info(
                'Authenticating to remote host (%s) using: password',
                self.remote_host
            )
            self.ssh_client.connect(
                self.remote_host,
                username=credentials["username"],
                password=credentials["password"],
                timeout=30
            )

        self.logger.debug('Done setting up ssh')

    def _gssapi_with_mic_available(self) -> bool:
        """
        Check if the authentication method `gssapi-with-mic`
        is available so that Kerberos tickets can be used to
        authenticate to the target host.
        """
        use_gssapi_with_mic = False
        try:
            paramiko.ssh_gss.GSSAuth(auth_method="gssapi-with-mic")
            use_gssapi_with_mic = True
        except ImportError:
            pass

        return use_gssapi_with_mic

    def setup_ftp(self):
        """
        Initiate SFTP connection and save it as self.ftp_client
        If needed, SSH connection will be automatically set up
        """
        self.logger.debug('Will set up ftp')
        if self.ftp_client:
            self.close_connections()

        if not self.ssh_client:
            self.setup_ssh()

        self.ftp_client = self.ssh_client.open_sftp()
        self.logger.debug('Done setting up ftp')

    def execute_command(self, command):
        """
        Execute command over SSH
        """
        if not self.ssh_client:
            self.setup_ssh()

        if isinstance(command, list):
            command = '; '.join(command)

        self.logger.debug('Executing %s', command)
        (_, stdout, stderr) = self.ssh_client.exec_command(command, timeout=self.timeout)
        self.logger.debug('Executed %s. Reading response', command)
        stdout_list = []
        stderr_list = []
        for line in stdout.readlines():
            stdout_list.append(line[0:256])

        for line in stderr.readlines():
            stderr_list.append(line[0:256])

        stdout = ''.join(stdout_list).strip()
        stderr = ''.join(stderr_list).strip()

        # Read output from stdout and stderr streams
        if stdout:
            self.logger.debug('STDOUT (%s): %s', command, stdout)

        if stderr:
            self.logger.error('STDERR (%s): %s', command, stderr)

        return stdout, stderr

    def upload_file(self, copy_from, copy_to):
        """
        Upload a file
        """
        self.logger.debug('Will upload file %s to %s', copy_from, copy_to)
        if not self.ftp_client:
            self.setup_ftp()

        try:
            self.ftp_client.put(copy_from, copy_to)
            self.logger.debug('Uploaded file to %s', copy_to)
        except Exception as ex:
            self.logger.error('Error uploading file from %s to %s. %s', copy_from, copy_to, ex)
            return False

        return True

    def download_file(self, copy_from, copy_to):
        """
        Download file from remote host
        """
        self.logger.debug('Will download file %s to %s', copy_from, copy_to)
        if not self.ftp_client:
            self.setup_ftp()

        try:
            self.ftp_client.get(copy_from, copy_to)
            self.logger.debug('Downloaded file to %s', copy_to)
        except Exception as ex:
            self.logger.error('Error downloading file from %s to %s. %s', copy_from, copy_to, ex)
            return False

        return True

    def close_connections(self):
        """
        Close any active connections
        """
        if self.ftp_client:
            self.logger.debug('Closing ftp client')
            self.ftp_client.close()
            self.ftp_client = None
            self.logger.debug('Closed ftp client')

        if self.ssh_client:
            self.logger.debug('Closing ssh client')
            self.ssh_client.close()
            self.ssh_client = None
            self.logger.debug('Closed ssh client')

    def _use_gssapi_with_mic_for_auth(self):
        """
        In case `gssapi_with_mic` is available, use a Kerberos ticket
        for authenticating SSH sessions. Enable this behavior by
        setting the environment variable: $MCM_GSSAPI_WITH_MIC.
        """
        return bool(os.getenv("MCM_GSSAPI_WITH_MIC"))
