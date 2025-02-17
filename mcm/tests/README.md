# Test folder

This folder includes a Python package with all the tests cases to check McM's API and its features. Currently, it acts as a black box/isolated test.

#### Development version

Create an isolated virtual environment using a Python version >= 3.9 via:

`python3.9 -m venv venv && source ./venv/bin/activate`

Install `poetry` and the required dependencies.

`pip install poetry && poetry install`

Run the test suite via:
`poetry run pytest -s -vv`