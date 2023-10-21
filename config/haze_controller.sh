#!/bin/sh

# We need to source some files which are only available on prplWrt
# devices, so prevent shellcheck from trying to read them:
# shellcheck disable=SC1091

set -e

# Start with a new log file:
rm -f /var/log/messages && syslog-ng-ctl reload

# Save the IP settings persistently (PPM-2351):
sed -ri 's/(dm-save.*) = false/\1 = true/g' /etc/amx/ip-manager/ip-manager.odl
sh /etc/init.d/ip-manager restart && sleep 15

ubus wait_for IP.Interface


# Stop and disable the DHCP clients and servers:
if ubus call DHCPv4Server _list ; then
  ubus call DHCPv4Server _set '{"parameters": { "Enable": False }}'
  echo "Disabled DHCPv4!"
else
    echo "DHCPv6 service not active!"
fi
if ubus call DHCPv6Server _list ; then
  ubus call DHCPv6Server _set '{"parameters": { "Enable": False }}'
  echo "Disabled DHCPv6!"
else
    echo "DHCPv6 service not active!"
fi

# We use WAN for the control interface.
# Add the IP address if there is none yet:
# ubus call IP.Interface _get '{ "rel_path": ".[Alias == \"wan\"].IPv4Address.[Alias == \"wan\"]." }' || {
#     echo "Adding IP address $IP"
#     ubus call "IP.Interface" _add '{ "rel_path": ".[Alias == \"wan\"].IPv4Address.", "parameters": { "Alias": "wan", "AddressingType": "Static" } }'
# }
# Configure it:
# ubus call "IP.Interface" _set '{ "rel_path": ".[Alias == \"wan\"].IPv4Address.1", "parameters": { "IPAddress": "192.168.250.1", "SubnetMask": "255.255.255.0", "AddressingType": "Static", "Enable" : true } }'
# Enable it:
# ubus call "IP.Interface" _set '{ "rel_path": ".[Alias == \"wan\"].", "parameters": { "IPv4Enable": true } }'


# Move the WAN port into the LAN bridge, so that it can also be used to connect other agents:
# Lowerlayers path: ubus-cli Device.Ethernet.Interface.["Alias"==\"WAN\"].?
# ubus wait_for Bridging.Bridge
# ubus call "Bridging.Bridge" _get '{ "rel_path": ".[Alias == \"lan\"].Port.[Name == \"wan\"]." }' || {
#     echo "Adding interface to bridge"
#     ubus call "Bridging.Bridge" _add '{ "rel_path": ".[Alias == \"lan\"].Port.",  "parameters": { "Name": "wan", "Alias": "WAN", "LowerLayers": "Device.Ethernet.Interface.1." ,"Enable": true } }'
# }

sleep 10

# Set the LAN bridge IP:
ubus call "IP.Interface" _set '{ "rel_path": ".[Name == \"br-lan\"].IPv4Address.[Alias == \"lan\"].", "parameters": { "IPAddress": "192.168.1.1" } }'

# Wired backhaul interface:
uci set prplmesh.config.backhaul_wire_iface='lan3'
uci commit

# enable Wi-Fi radios
ubus call "WiFi.Radio" _set '{ "rel_path": ".[OperatingFrequencyBand == \"2.4GHz\"].", "parameters": { "Enable": "true" } }'
ubus call "WiFi.Radio" _set '{ "rel_path": ".[OperatingFrequencyBand == \"5GHz\"].", "parameters": { "Enable": "true" } }'
ubus call "WiFi.Radio" _set '{ "rel_path": ".[OperatingFrequencyBand == \"6GHz\"].", "parameters": { "Enable": "true" } }'

sleep 10

# Reconfigure the DHCPv4 server for the LAN pool (only controller)
# ubus-cli DHCPv4Server.Enable=0
# ubus-cli DHCPv4Server.Pool.[Alias==\"lan\"].Enable=0
# ubus-cli DHCPv4Server.Pool.[Alias==\"lan\"].DNSServers="192.168.100.1"
# ubus-cli DHCPv4Server.Pool.[Alias==\"lan\"].IPRouters="192.168.100.1"
# ubus-cli DHCPv4Server.Pool.[Alias==\"lan\"].MinAddress="192.168.100.100"
# ubus-cli DHCPv4Server.Pool.[Alias==\"lan\"].MaxAddress="192.168.100.249"
ubus-cli DHCPv4Server.Pool.[Alias==\"lan\"].Enable=1
ubus-cli DHCPv4Server.Enable=1

# all pwhm default configuration can be found in /etc/amx/wld/wld_defaults.odl.uc

# Restart the ssh server
sh /etc/init.d/ssh-server restart

# Required for config_load:
. /lib/functions/system.sh
# Required for config_foreach:
. /lib/functions.sh

# configure private vaps
ubus call "WiFi.SSID.1" _set '{ "parameters": { "SSID": "prplmesh_Paris_2.4GHz" } }'
ubus call "WiFi.SSID.2" _set '{ "parameters": { "SSID": "prplmesh_Paris_5GHz" } }'
ubus call "WiFi.SSID.6" _set '{ "parameters": { "SSID": "prplmesh_Paris_6GHz" } }'
ubus call "WiFi.AccessPoint.1.Security" _set '{ "parameters": { "KeyPassPhrase": "prplmesh_pass" } }'
ubus call "WiFi.AccessPoint.2.Security" _set '{ "parameters": { "KeyPassPhrase": "prplmesh_pass" } }'
ubus call "WiFi.AccessPoint.5.Security" _set '{ "parameters": { "KeyPassPhrase": "prplmesh_pass" } }'
ubus call "WiFi.AccessPoint.1.Security" _set '{ "parameters": { "ModeEnabled": "WPA2-Personal" } }'
ubus call "WiFi.AccessPoint.2.Security" _set '{ "parameters": { "ModeEnabled": "WPA2-Personal" } }'
ubus call "WiFi.AccessPoint.5.Security" _set '{ "parameters": { "ModeEnabled": "WPA2-Personal" } }'
ubus call "WiFi.AccessPoint.1.WPS" _set '{ "parameters": { "ConfigMethodsEnabled": "PushButton" } }'
ubus call "WiFi.AccessPoint.2.WPS" _set '{ "parameters": { "ConfigMethodsEnabled": "PushButton" } }'
ubus call "WiFi.AccessPoint.5.WPS" _set '{ "parameters": { "ConfigMethodsEnabled": "PushButton" } }'

ubus-cli WiFi.AccessPoint.1.Enable=1
ubus-cli WiFi.AccessPoint.2.Enable=1
ubus-cli WiFi.AccessPoint.5.Enable=1

ubus-cli WiFi.SSID.1.Enable=1
ubus-cli WiFi.SSID.2.Enable=1
ubus-cli WiFi.SSID.6.Enable=1


# Restrict channel bandwidth or the certification test could miss beacons
# (see PPM-258)
ubus call "WiFi.Radio" _set '{ "rel_path": ".[OperatingFrequencyBand == \"2.4GHz\"].", "parameters": { "OperatingChannelBandwidth": "20MHz" } }'
ubus call "WiFi.Radio" _set '{ "rel_path": ".[OperatingFrequencyBand == \"5GHz\"].", "parameters": { "OperatingChannelBandwidth": "20MHz" } }'

sleep 5

# Make sure specific channels are configured. If channel is set to 0,
# ACS will be configured. If ACS is configured hostapd will refuse to
# switch channels when we ask it to. Channels 1 and 48 were chosen
# because they are NOT used in the WFA certification tests (this
# allows to verify that the device actually switches channel as part
# of the test).
# See also PPM-1928.
ubus call "WiFi.Radio" _set '{ "rel_path": ".[OperatingFrequencyBand == \"2.4GHz\"].", "parameters": { "Channel": "8" } }'
ubus call "WiFi.Radio" _set '{ "rel_path": ".[OperatingFrequencyBand == \"5GHz\"].", "parameters": { "Channel": "44" } }'

sleep 10

# Try to work around PCF-681: if we don't have a connectivity, restart
# tr181-bridging
# Check the status of the LAN bridge
ip a |grep "br-lan:" |grep "state UP" >/dev/null || (echo "LAN Bridge DOWN, restarting bridge manager" && sh /etc/init.d/tr181-bridging restart && sleep 15)


sh /etc/init.d/ip-manager restart && sleep 15

# Stop the default ssh server on the lan-bridge
sh /etc/init.d/ssh-server stop
sleep 5

# Add command to start dropbear to rc.local to allow SSH access after reboot
BOOTSCRIPT="/etc/rc.local"
SERVER_CMD="sleep 20 && sh /etc/init.d/ssh-server stop && dropbear -F -T 10 -p192.168.1.1:22 &"
if ! grep -q "$SERVER_CMD" "$BOOTSCRIPT"; then { head -n -2 "$BOOTSCRIPT"; echo "$SERVER_CMD"; tail -2 "$BOOTSCRIPT"; } >> btscript.tmp; mv btscript.tmp "$BOOTSCRIPT"; fi

# Stop and disable the firewall:
#sh /etc/init.d/tr181-firewall stop
#rm -f /etc/rc.d/S22tr181-firewall

ubus-cli Firewall.Enable=0
/etc/init.d/tr181-firewall stop
iptables -P INPUT ACCEPT

# Start an ssh server on the control interface
dropbear -F -T 10 -p192.168.1.1:22 &
