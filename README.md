# **EasyMesh Network Topology UI**
[![Build Status](https://gitlab.com/prpl-foundation/prplmesh/topologyViewer/badges/master/pipeline.svg)](https://gitlab.com/prpl-foundation/prplmesh/topologyViewer/pipelines)

## **Requirements**
For initial set-up, you'll need a serial or SSH connection to the Controller in your EasyMesh network (for running `ubus` commands.)
- The controller in the prplMesh network must have `lighttpd` and `amx-fcgi` built/deployed.
- The port that the controller will listen for HTTP requests on is configurable in the `lighttpd.conf` file,
located at `/etc/lighttpd/lighttpd.conf`
    - Change the port via the `server.port = <int>` entry. Defaults to 8080.
- Configure the firewall on the Controller to permit incoming HTTP traffic on the port you want, or just do `iptables -P INPUT ACCEPT`

To test whether or not the HTTP<->Ambiorix proxy is running, and the port is open, do:

`curl -u username:pass "http://<controller_ip>:<controller_port>/serviceElements/Device."`

You'll additionally need some external packages:

`sudo apt install graphviz`

## **To Run the topologyviewer:**
Change the included `config.ini` file to match your setup.

### **Use included script:**

`source prepare_env.sh`

`python main.py`

-> open your browser at: http://localhost:8050/

### **Manually prepare python env:**

`python -m venv ./`

`source ./bin/activate`

`python -m pip install -r requirements.txt`

`python main.py`

`firefox localhost:8050 & disown`

This user interface was used to demonstrate AP onboarding and manufacturer interoperability within the prplMesh ecosystem [in this YouTube video](https://youtu.be/rYcfrIRljbQ)

To reproduce this demo, follow the steps in `DEMO.md`

## **Tests:**

`python tests.py`

