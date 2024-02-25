# Test folder

This folder contains all the software and packages related to testing. No module in test folder should be referenced by any other part of the application. Currently, this folder only stores system tests related to check the API and the underlying functionality. For this reason:

1. There is an isolated `requirements.txt` file that described the required packages.
2. The interpreter version used for writing and executing the test is: **Python 3.11**