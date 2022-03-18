"""
Module that contains ConnectionWrapper class
"""
import logging
import os
import json
import time
import ssl
from http import client


class ConnectionWrapper():
    """
    HTTP and HTTPS client wrapper class to re-use existing connection
    Supports user certificate authentication
    """

    def __init__(self,
                 host,
                 cert_file=None,
                 key_file=None):
        self.logger = logging.getLogger('mcm_error')
        self.connection = None
        host = host.rstrip('/')
        self.https = host.startswith('https://')
        self.host_url = host.replace('https://', '', 1).replace('http://', '', 1)
        self.port = 443 if self.https else 80
        if ':' in self.host_url:
            host_port = self.host_url.rsplit(':', 1)
            self.port = host_port[-1]
            self.host_url = host_port[0]

        self.logger.debug('Host: %s, port %s, https: %s', self.host_url, self.port, self.https)
        self.cert_file = cert_file or os.getenv('USERCRT', None)
        self.key_file = key_file or os.getenv('USERKEY', None)
        self.connection_attempts = 3
        self.timeout = 120

    def __enter__(self):
        self.logger.debug('Entering context, host: %s', self.host_url)
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        self.logger.debug('Exiting context, host: %s', self.host_url)
        self.close()

    def init_connection(self):
        """
        Return a new HTTPConnection or HTTPSConnection
        """
        params = {'host': self.host_url,
                  'port': self.port,
                  'timeout': self.timeout}
        if self.cert_file and self.key_file:
            params['cert_file'] = self.cert_file
            params['key_file'] = self.key_file

        if self.https:
            self.logger.info('Creating HTTPS connection for %s', self.host_url)
            params['context'] = ssl._create_unverified_context()
            self.connection = client.HTTPSConnection(**params)
        else:
            self.logger.info('Creating HTTP connection for %s', self.host_url)
            self.connection = client.HTTPConnection(**params)

    def close(self):
        """
        Close connection if it exists
        """
        if self.connection:
            self.logger.debug('Closing connection for %s', self.host_url)
            self.connection.close()
            self.connection = None

    def api(self, method, url, data=None, headers=None):
        """
        Make a HTTP request to given url
        """
        if not self.connection:
            self.init_connection()

        all_headers = {}
        if data and isinstance(data, dict):
            all_headers.update({"Accept": "application/json"})
            data = json.dumps(data) if data else None

        if headers:
            all_headers.update(headers)

        url = url.replace('#', '%23')
        for attempt in range(1, self.connection_attempts + 1):
            if attempt != 1:
                self.logger.debug('%s request to %s attempt %s', method, url, attempt)

            start_time = time.time()
            try:
                self.connection.request(method,
                                        url,
                                        body=data,
                                        headers=all_headers)
                response = self.connection.getresponse()
                response_to_return = response.read()
                if response.status != 200:
                    self.logger.error('Error %d while doing %s to %s: %s',
                                      response.status,
                                      method,
                                      url,
                                      response_to_return)
                    return response_to_return

                end_time = time.time()
                self.logger.debug('%s request to %s%s took %.2f',
                                  method,
                                  self.host_url,
                                  url,
                                  end_time - start_time)
                return response_to_return
            except Exception as ex:
                self.logger.error('Exception while doing a %s to %s: %s',
                                  method,
                                  url,
                                  str(ex))
                if attempt < self.connection_attempts:
                    sleep = attempt ** 3
                    self.logger.debug('Will sleep for %s and retry')
                    time.sleep(sleep)

                self.init_connection()

        self.logger.error('Request failed after %d attempts', self.connection_attempts)
        return None
