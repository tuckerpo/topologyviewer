## **Demo:**
These are the steps needed to allow for a prplMesh demonstration.
This demo shows off device steering and onboarding external prplMesh and proprietary easymesh agents.

### **Demo devices:**
- 2x GL-iNet B1300 (running prplOs / prplmesh)
- 1x non-1905 device to steer (not all devices respond well to a steering request; the device can choose to disconnect to the network)
- 1x Turris-omnia (running RDK-B / prplmesh)
- 1x Arris/Commscope X5042 (proprietary easymesh extender)
- 1x Sagemcom extender running prplMesh
- 1x “control”/ visualization PC (running this topologyviewer)

### **Demo configuration:**
One of the GL-iNet devices will be used as a Controller(+Agent), the other as an Agent.
The Agent GL-iNet and Arris will be wirelessly onboarded (using their WPS button).
The RDK-B Turris-omnia and Sagemcom extender will be onboarded over Ethernet.

#### **Flashing the demo images - prplMesh ipk's:**
The prplOS version that is used: [Release 3.1.0](https://gitlab.com/prpl-foundation/prplmesh/prplMesh/-/releases/3.1.0)
The RDK-B image that is used on the Turris-omnia can be downloaded from this release's corresponding pipeline: [build-for-rdkb-turris-omnia](https://gitlab.com/prpl-foundation/prplmesh/prplMesh/-/jobs/3120295567)

PrplOS needs to be flashed on both GL-iNet's: [Deploying-prplMesh-on-Gl.iNet](https://gitlab.com/prpl-foundation/prplmesh/prplMesh/-/wikis/Deploying-prplMesh-on-Gl.iNet)
As well as the Turris-Omnia: [Deploying-prplMesh-on-Turris-Omnia-(RDK-B)](https://gitlab.com/prpl-foundation/prplmesh/prplMesh/-/wikis/Deploying-prplMesh-on-Turris-Omnia-(RDK-B))

After flashing prplOS, a newer version of prplMesh must replace the existing one on the image: [build-for-glinet-b1300](https://gitlab.com/prpl-foundation/prplmesh/prplMesh/-/jobs/3189663642)
This build removes an existing limitation in prplMesh that limits the maximum number of backhaul STA's a device can have.

It is possible to use the deploy script inside the prplMesh repository to copy and replace the prplMesh IPK's ([deploy_ipk.sh](https://gitlab.com/prpl-foundation/prplmesh/prplMesh/-/raw/master/tools/deploy_ipk.sh))
Assuming the devices are reachable over SSH on TARGET_DEVICE_NAME, you can invoke it with:
`./deploy_ipk.sh TARGET_DEVICE_NAME insert_new_prplMesh_ipk_name.ipk`

#### **(pre)Configuring the devices:**
All configuration that is needed to run the demo is contained in a per-device shell script [PPM-2303-add-configuration-files-for-prpl-summit-demo-devices](https://gitlab.com/prpl-foundation/prplmesh/prplMesh/-/tree/feature/PPM-2303-add-configuration-files-for-prpl-summit-demo-devices/ci/configuration/demo/prpl_summit_2022)

Copy the corresponding shell script to each device, and execute it:
eg assuming the controller is already reachable over SSH at **controller-glinet**:
```
scp glinet-b1300-1.sh controller-glinet:/tmp/glinet-b1300-1.sh
ssh controller-glinet 'sh /tmp/glinet-b1300-1.sh'
```

OR:
Copy the configuration script over serial line and execute it.

The configuration contains predefined IP settings:
| Device | IP Address |
| ----------- | ----------- |
| Controller GL-iNet | 192.168.250.172 |
| Agent GL-iNet | 192.168.250.172 |
| Agent RDK-B Turris-Omnia | 192.168.250.170 |

Feel free to adapt these to your needs.
The controller will be configured to keep it's DHCP server running.

### **Demo actions:**
- Power on the Controller GL-iNet
- Connect the visualisation PC to it's network (using ethernet or Wi-Fi)
- Start the topologyviewer (see above) and connect to the controller IP
- Power on the Agent GL-iNet
- Onboard the Agent over WPS (press mesh button <2 seconds on the Controller; press mesh button 5 seconds on the Agent)
- The topologyviewer should display the onboarded Agent
- Connect a station to the network
- Steer the station to another interface using the form (select client steering, the station mac and the interface to steer to)
- Power on and onboard the Arris device (press WPS button <2 seconds on the Arris and any GL-iNet)
- Power on and onboard RDK-B Turris-omnia (Ethernet onboarding happens automatically)
- Power on and onboard Sagemcom Extender (Ethernet onboarding happens automatically)
