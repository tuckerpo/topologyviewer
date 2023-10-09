#!/bin/sh
python -m venv ./
source ./bin/activate
python -m pip install -r requirements.txt

session_id=$(curl --silent -X POST "http://192.168.1.1/session" --data '{"username":"admin","password":"admin"}' | jq -r .sessionID)

echo "To use a session token with HTTP header:"
echo "Authorization: bearer ${session_id}"

# Use session token to get the datamodel
#curl -X GET "http://192.168.1.1/serviceElements/Device.WiFi.DataElements." -H "Authorization: bearer $session_id"
