#!/bin/bash
# Quickly deploys a reverse proxy for enabling the web page
# for development environments. The reverse proxy to be used is:
# Caddy: https://github.com/caddyserver/caddy

# Download URL
CADDY_BUNDLE='https://github.com/caddyserver/caddy/releases/download/v2.9.1/caddy_2.9.1_linux_amd64.tar.gz'
CADDY_PORT='10000'
USER_EMAIL=''

# Notification email
if [ -z "$USER_EMAIL" ]; then
    echo 'Set $USER_EMAIL with your personal email!'
    exit 1
fi

# Path to the McM source code
if [ -z "$REPO_PATH" ]; then
    echo 'Set $REPO_PATH with the absolute path to the McM source code including the mcm/ internal folder'
    exit 1
fi

# McM port
if [ -z "$MCM_PORT" ]; then
    echo '$MCM_PORT is not set. Have you already deployed the application?'
    exit 1
fi

# Create a folder for caddy
CADDY_FOLDER="${REPO_PATH}/caddy"
if ! mkdir -p "${CADDY_FOLDER}"; then
    echo "Error: Unable to create a folder for caddy"
    exit 1
fi

function download_caddy () {
    echo "Downloading Caddy at: ${CADDY_FOLDER}"
    curl -sfSL "${CADDY_BUNDLE}" | tar -xzC "${CADDY_FOLDER}"
    if [ ! -f "${CADDY_FOLDER}/caddy" ]; then
        echo "Error: Caddy not found!"
        exit 1
    fi
}

# Create a configuration file
function create_config () {
cat <<EndCaddyConfig > "${CADDY_FOLDER}/CaddyFile"
:${CADDY_PORT} {
    handle_path /mcm* {
        reverse_proxy 0.0.0.0:${MCM_PORT} {
            header_up Adfs-Group "default-role"
            header_up Adfs-Login "development"
            header_up Adfs-Fullname "Development User"
            header_up Adfs-Firstname "Development User"
            header_up Adfs-Lastname "Development User"
            header_up Adfs-Email "${USER_EMAIL}"
        }
    }
}
EndCaddyConfig
}

# Check if Caddy exists
CADDY_BIN="${CADDY_FOLDER}/caddy"
if [ ! -f "${CADDY_BIN}" ]; then
    download_caddy
fi

# Create a config file
create_config

# Start the proxy
$CADDY_BIN run --config "${CADDY_FOLDER}/CaddyFile" > "${CADDY_FOLDER}/caddy.log" 2>&1 & echo $! > "${CADDY_FOLDER}/caddy.pid"
