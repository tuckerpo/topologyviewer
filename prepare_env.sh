#!/bin/bash
scriptdir="$(cd "${0%/*}"; pwd)"
controller_addr=$(awk -F "=" '/controller-addr/ {print $2}' "$scriptdir/config.ini" | tr -d '\r')
controller_port=$(awk -F "=" '/controller-port/ {print $2}' "$scriptdir/config.ini" | tr -d '\r')

print_color() {
    echo -e "\e[0;33m$1\e[0m"
}

print_color "Preparing Python environment:"
python -m venv $scriptdir
source "$scriptdir/bin/activate"
python -m pip install -r "$scriptdir/requirements.txt"

print_color "Getting session token from controller on ${controller_addr}:"
session_id=$(curl --silent -X POST "http://${controller_addr}:${controller_port}/session" --data '{"username":"admin","password":"admin"}' | jq -r .sessionID)

print_color "HTTP header if you want to use the session token:"
print_color "Authorization: bearer ${session_id}"

# Use session token to get the datamodel
#curl -X GET "http://192.168.1.1/serviceElements/Device.WiFi.DataElements." -H "Authorization: bearer $session_id"
