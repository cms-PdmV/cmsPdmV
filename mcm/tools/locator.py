import os
import sys
import logging


class locator:
    """
    Groups all the required configuration variables for the web application
    """

    def __init__(self):
        self.logger = self.__create_logger()

    def __create_logger(self):
        """
        Creates a logger for the class
        """
        logger = logging.getLogger(__name__)
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(fmt='[%(asctime)s][%(levelname)s]%(message)s')

        handler.setLevel(logging.INFO)
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        return logger

    def isDev(self):
        return not self.isProd()

    def isProd(self):
        """
        Determine if the application should run using the production configuration.

        Returns:
            bool: True if the application runs using the production
                configuration, False otherwise.
        """
        production = bool(os.getenv("MCM_PRODUCTION"))
        self.logger.info("Running in production: %s", production)
        return production

    def database_url(self):
        """
        Retrieve the connection URL for the McM CouchDB instance.
        This configuration is taken via the environment variable:
            `MCM_COUCHDB_URL`

        For example: http://vocms0485.cern.ch:5984/

        Returns:
            str: Connection URL. An empty string in case this is
                not set
        Raises:
            RuntimeError: In case the value is not provided.
        """
        db_url = os.getenv("MCM_COUCHDB_URL", "")
        self.logger.info("McM CouchDB URL: %s", db_url)
        if not db_url:
            raise RuntimeError("Set MCM_COUCHDB_URL to the McM CouchDB connection url")
        return db_url

    def lucene_url(self):
        """
        Retrieve the connection URL for the CouchDB Lucene indexer.
        This configuration is taken via the environment variable:
            `MCM_LUCENE_URL`.

        For example: http://vocms0485.cern.ch:5985/

        Returns:
            str: Connection URL. An empty string in case this is
                not set
        Raises:
            RuntimeError: In case the value is not provided.
        """
        lucene_url = os.getenv("MCM_LUCENE_URL", "")
        self.logger.info("McM CouchDB Lucene URL: %s", lucene_url)
        if not lucene_url:
            raise RuntimeError(
                "Set MCM_LUCENE_URL to the McM CouchDB Lucene connection url"
            )
        return lucene_url

    def workLocation(self):
        """
        Retrieve the absolute path (in AFS) of the work folder used to store
        the injection scripts and to upload the request configuration to ReqMgr2.
        This can be overwitten using the environment variable:
            `MCM_WORK_LOCATION_PATH`

        Returns:
            str: Work folder absolute path
        """
        custom_work_path = os.getenv("MCM_WORK_LOCATION_PATH")
        if custom_work_path:
            self.logger.info("Using the custom work folder: %s", custom_work_path)
            return custom_work_path

        if self.isDev():
            return "/afs/cern.ch/cms/PPD/PdmV/work/McM/dev-submit/"
        else:
            return "/afs/cern.ch/cms/PPD/PdmV/work/McM/submit/"

    def baseurl(self):
        """
        Retrieve the McM web service base URL. This is used for building the
        links including in e-mail notifications.
        This can be overwritten using the environment variable:
            `MCM_BASE_URL`

        Returns:
            str: McM web application base URL
        """
        custom_base_url = os.getenv("MCM_BASE_URL")
        if custom_base_url:
            self.logger.info("Using the custom base URL: %s", custom_base_url)
            return custom_base_url

        if self.isDev():
            return "https://cms-pdmv-dev.web.cern.ch/mcm/"
        else:
            return "https://cms-pdmv-prod.web.cern.ch/mcm/"

    def cmsweburl(self):
        """
        Retrieve the base URL for the CMS Web services
        """
        if self.isDev():
            return "https://cmsweb-testbed.cern.ch/"
        else:
            return "https://cmsweb.cern.ch/"

    def database_credentials(self):
        """
        Retrieve the credential's header to the CouchDB database.
        It is taken from the runtime environment.

        Returns:
            str: CouchDB basic credentials coded as base64.
        Raises:
            RuntimeError: If they are not provided.
        """
        cred_header = os.getenv("COUCH_CRED", "")
        if not cred_header:
            raise RuntimeError("Set COUCH_CRED to the CouchDB authentication header")
        return cred_header

    def stats_database_url(self):
        """
        Retrieve the Stats2 CouchDB connection URL.
        This can be overwritten using the environment variable:
            `MCM_STATS2_DB_URL`

        Returns:
            str: Stats2 CouchDB connection URL.
        """
        custom_url = os.getenv("MCM_STATS2_DB_URL")
        default_url = "http://vocms074.cern.ch:5984/"
        if custom_url:
            self.logger.info("Stats2 custom connection URL: %s", custom_url)
            return custom_url

        return default_url

    def mcm_executor_node(self):
        """
        Returns the remote hostname used by McM to
        perform SSH executions for processing some tasks
        like approving requests, upload request configuration to ReqMgr2,
        or execute injection commands.

        This can be overwritten using the environment variable:
            `MCM_EXECUTOR_HOST`

        Returns:
            str: McM executor node hostname.
        """
        custom_node = os.getenv("MCM_EXECUTOR_HOST")
        default_node = "vocms0481.cern.ch"
        if custom_node:
            self.logger.info("Using a custom McM executor node: %s", custom_node)
            return custom_node
        return default_node

    def host(self):
        """
        Returns the binded host for the web application.
        """
        return os.getenv("MCM_HOST", "0.0.0.0")

    def port(self):
        """
        Returns the port for the web application.
        """
        return os.getenv("MCM_PORT", "8000")

    def debug(self):
        """
        Enables the DEBUG level for logging.
        """
        return bool(os.getenv("MCM_DEBUG"))

    def logs_folder(self):
        """
        Retrieve the absolute path for the log folder.
        This can be overwritten using the environment variable:
            `MCM_LOG_FOLDER`

        Returns:
            str: Log folder absolute path.
        """
        custom_path = os.getenv("MCM_LOG_FOLDER")
        default_path = os.path.join(os.getcwd(), "logs")
        if custom_path:
            self.logger.info("Using a custom log folder: %s", custom_path)
            return custom_path
        return default_path
