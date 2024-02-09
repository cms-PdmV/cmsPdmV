# Angular templates
FROM node:20.11.0-alpine3.19@sha256:9b61ed13fef9ca689326f40c0c0b4da70e37a18712f200b4c66d3b44fd59d98e AS frontend
WORKDIR /usr/app

# Copy the static files
COPY ./scripts ./scripts
COPY Gruntfile.js .
COPY package.json .

RUN npm install
RUN ./node_modules/grunt/bin/grunt

# Python packages
FROM python:2.7.18-stretch@sha256:58e0d45ffe8fca0cde7faecb39ff4f9a0329d83c856bb196eda3b385f77ed529 AS build

WORKDIR /usr/app
RUN pip install --upgrade pip setuptools wheel virtualenv
RUN virtualenv venv
ENV PATH="/usr/app/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install -r requirements.txt

# Create image for deployment
FROM python:2.7.18-stretch@sha256:58e0d45ffe8fca0cde7faecb39ff4f9a0329d83c856bb196eda3b385f77ed529 AS backend
RUN pip install --upgrade pip setuptools wheel
RUN apt purge -y mercurial && apt autoremove -y

# User and application folder
RUN useradd --no-create-home --shell /bin/bash --uid 1001 pdmv
RUN mkdir -p /usr/app && chown -R pdmv:pdmv /usr/app
WORKDIR /usr/app

COPY --chown=pdmv:pdmv --from=build /usr/app/venv ./venv
COPY --chown=pdmv:pdmv --from=frontend /usr/app/node_modules ./node_modules
COPY --chown=pdmv:pdmv . .
COPY --chown=pdmv:pdmv --from=frontend /usr/app/scripts ./scripts

USER 1001

ENV PATH="/usr/app/venv/bin:$PATH"
CMD [ "python", "main.py" ]