# **EasyMesh Network Topology UI**

## **Requirements**
For initial set-up, you'll need a serial or SSH connection to the Controller in your EasyMesh network (for running `ubus` commands.)
- The controller in the prplMesh network must have `lighttpd` and `amx-fcgi` built/deployed.
- The port that the controller will listen for HTTP requests on is configurable in the `lighttpd.conf` file,
located at `/etc/lighttpd/lighttpd.conf`
    - Change the port via the `server.port = <int>` entry. Defaults to 8080.
- Configure the firewall to allow incoming requests
    - `ubus-cli Firewall.X_Prpl_Service.+{Alias="serviceelements",Action="Accept",DestinationPort="<your_port_here>",Enable=1,IPVersion=4,Interface="<your_interface_here>",Protocol="TCP"}`

To test whether or not the HTTP<->Ambiorix proxy is running, and the port is open, do:

`curl -u username:pass "http://<controller_ip>:<controller_port>/serviceElements/Device."`

## **To Run:**

`python -m venv ./`

`source ./bin/activate`

`python -m pip install -r requirements.txt`

`python main.py`

`firefox localhost:8050 & disown`

## **Tests:**

`python tests.py`

## **TODO:**

- Client steering is a stub. Making a `ubus` call over the `amx-fcgi` interface is not documented. I'm sure it's possible.

- Unassociated stations. Not handled in the UI, because they're not handled in prplMesh itself.

- RSSI/time plotting, to visualize VBSS switching decisions. Good for a demo.