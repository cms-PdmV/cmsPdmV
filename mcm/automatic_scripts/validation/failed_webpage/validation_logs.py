"""This module manages the deletion of orphan validation failed records.

It scans the validation failed folder and removes any folder older than
a threshold.
"""

import datetime
import logging
import os
import re
import shutil
import sys
from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# Configure the logger
logging.basicConfig(level=logging.INFO, stream=sys.stdout, format='[%(asctime)s][%(levelname)s] %(message)s')


class ValidationFailedDeletion:
    """It scans the validation failed folder removing orphan records."""
    def __init__(self):
        self.folder = Path(os.getenv("MCM_VALIDATION_FAILED_EOS_FOLDER", str(Path.cwd())))
        self.context = {}
        self.logger = logging.getLogger()

        # Set up the timezone
        tz_name = os.getenv("TZ")
        try:
            self.tz = ZoneInfo(tz_name)
        except Exception:
            self.tz = ZoneInfo("Europe/Zurich")

        # Number of days to keep a records
        days = os.getenv("MCM_VALIDATION_FAILED_KEEP_DAYS")
        try:
            self.days = int(days)
        except Exception:
            self.days = 30

        self.logger.info("Scanning folder: %s", self.folder)
        self.logger.info("Using timezone: %s", self.tz)
        self.logger.info("Number of days for retention: %s", self.days)


    def _scan_folders(self) -> list[Path]:
        """Scan all the request folders and pick some information"""
        mcm_request_regex = re.compile(r"^[A-Z]{3}-.*")
        request_folders = []
        now_dt = datetime.now(tz=self.tz)
        for el in self.folder.glob("*"):
            if el.is_dir() and mcm_request_regex.match(el.name):
                latest_change = el.stat().st_mtime
                latest_change_dt = datetime.fromtimestamp(latest_change, tz=self.tz)
                elapsed = now_dt - latest_change_dt
                if elapsed > timedelta(days=self.days):
                    self.logger.info("Including (%s) for removal. Elapsed time: %s", el, elapsed)
                    request_folders.append(el)

        return request_folders

    def remove(self):
        """Scan the folders and performs a removal."""
        folders = self._scan_folders()
        self.logger.info("Will remove the following folders: %s", folders)
        for folder in folders:
            shutil.rmtree(folder)


if __name__ == "__main__":
    validation_deletion = ValidationFailedDeletion()
    validation_deletion.remove()
