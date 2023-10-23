#!/bin/sh

# We need to source some files which are only available on prplWrt
# devices, so prevent shellcheck from trying to read them:
# shellcheck disable=SC1091

set -e

service prplmesh stop

# Start with a new log file:
rm -f /var/log/messages && syslog-ng-ctl reload


ubus wait_for IP.Interface


# Stop and disable the DHCP clients and servers:
# if ubus call DHCPv4Server _list ; then
#   ubus call DHCPv4Server _set '{"parameters": { "Enable": False }}'
#   echo "Disabled DHCPv4!"
# else
#     echo "DHCPv6 service not active!"
# fi
# if ubus call DHCPv6Server _list ; then
#   ubus call DHCPv6Server _set '{"parameters": { "Enable": False }}'
#   echo "Disabled DHCPv6!"
# else
#     echo "DHCPv6 service not active!"
# fi

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

# Automatic removal of WiFi backhaul agents
ubus-cli Device.WiFi.DataElements.Configuration.BandSteeringEnabled=1
ubus-cli Device.WiFi.DataElements.Configuration.HealthCheckTaskEnabled=1

# ?
ubus-cli X_PRPL-ORG_WiFiController.Configuration.ClientRoamingEnabled=1

uci set prplmesh.config.management_mode='Multi-AP-Controller-and-Agent'
uci set prplmesh.config.operating_mode='Gateway'
uci set prplmesh.config.wired_backhaul=0
uci set prplmesh.config.master=1
uci set prplmesh.config.gateway=1
uci commit prplmesh


# Wired backhaul interface:
uci set prplmesh.config.backhaul_wire_iface='eth0_5'
uci commit

# Devices which should support backhaul:
ubus-cli "WiFi.Radio.*.STA_Mode=1"

# ??
# ubus-cli WiFi.Radio.*.KickRoamingStation=0

# enable Wi-Fi radios (Enabled by SSID enable)
# ubus-cli WiFi.Radio.[OperatingFrequencyBand == \"2.4GHz\"].Enable=1
# ubus-cli WiFi.Radio.[OperatingFrequencyBand == \"5GHz\"].Enable=1
# ubus-cli WiFi.Radio.[OperatingFrequencyBand == \"6GHz\"].Enable=1

sleep 10

# Reconfigure the DHCPv4 server for the LAN pool (only controller)
# ubus-cli DHCPv4Server.Enable=0
# ubus-cli DHCPv4Server.Pool.[Alias==\"lan\"].Enable=0
# ubus-cli DHCPv4Server.Pool.[Alias==\"lan\"].DNSServers="192.168.100.1"
# ubus-cli DHCPv4Server.Pool.[Alias==\"lan\"].IPRouters="192.168.100.1"
# ubus-cli DHCPv4Server.Pool.[Alias==\"lan\"].MinAddress="192.168.100.100"
# ubus-cli DHCPv4Server.Pool.[Alias==\"lan\"].MaxAddress="192.168.100.249"

# ubus-cli DHCPv4Server.Pool.[Alias==\"lan\"].Enable=1
# ubus-cli DHCPv4Server.Enable=1

# all pwhm default configuration can be found in /etc/amx/wld/wld_defaults.odl.uc

# Restart the ssh server
# sh /etc/init.d/ssh-server restart

# Required for config_load:
. /lib/functions/system.sh
# Required for config_foreach:
. /lib/functions.sh


# Radio.1. => 2.4GHz
# Radio.2. => 5GHz
# Radio.3. => 6GHz

# WiFi.SSID.1.
# WiFi.SSID.1.Alias="vap5g0priv"
# WiFi.SSID.1.BSSID="5a:13:d3:02:fc:86"
# WiFi.SSID.1.Enable=0
# WiFi.SSID.1.Index=27
# WiFi.SSID.1.LastStatusChangeTimeStamp="2023-10-17T08:25:35Z"
# WiFi.SSID.1.LowerLayers="Device.WiFi.Radio.2."
# WiFi.SSID.1.MACAddress="5A:13:D3:02:FC:86"
# WiFi.SSID.1.Name="wlan2.1"
# WiFi.SSID.1.SSID="prplOS"
# WiFi.SSID.1.Status="Down"
# WiFi.SSID.2.
# WiFi.SSID.2.Alias="vap2g0priv"
# WiFi.SSID.2.BSSID="5a:13:d3:02:fa:85"
# WiFi.SSID.2.Enable=0
# WiFi.SSID.2.Index=28
# WiFi.SSID.2.LastStatusChangeTimeStamp="2023-10-17T08:25:36Z"
# WiFi.SSID.2.LowerLayers="Device.WiFi.Radio.1."
# WiFi.SSID.2.MACAddress="5A:13:D3:02:FA:85"
# WiFi.SSID.2.Name="wlan0.1"
# WiFi.SSID.2.SSID="prplOS"
# WiFi.SSID.2.Status="Down"
# WiFi.SSID.3.
# WiFi.SSID.3.Alias="vap6g0priv"
# WiFi.SSID.3.BSSID="58:13:d3:02:f9:87"
# WiFi.SSID.3.Enable=0
# WiFi.SSID.3.Index=29
# WiFi.SSID.3.LastStatusChangeTimeStamp="2023-10-17T08:25:36Z"
# WiFi.SSID.3.LowerLayers="Device.WiFi.Radio.3."
# WiFi.SSID.3.MACAddress="58:13:D3:02:F9:87"
# WiFi.SSID.3.Name="wlan4.1"
# WiFi.SSID.3.SSID="prplOS"
# WiFi.SSID.3.Status="Down"
# WiFi.SSID.4.
# WiFi.SSID.4.Alias="vap5g0guest"
# WiFi.SSID.4.BSSID="5a:13:d3:02:fc:87"
# WiFi.SSID.4.Enable=0
# WiFi.SSID.4.Index=30
# WiFi.SSID.4.LastStatusChangeTimeStamp="2023-10-17T08:25:36Z"
# WiFi.SSID.4.LowerLayers="Device.WiFi.Radio.2."
# WiFi.SSID.4.MACAddress="5A:13:D3:02:FC:87"
# WiFi.SSID.4.Name="wlan2.2"
# WiFi.SSID.4.SSID="prplOS-guest"
# WiFi.SSID.4.Status="Down"
# WiFi.SSID.5.
# WiFi.SSID.5.Alias="vap2g0guest"
# WiFi.SSID.5.BSSID="5a:13:d3:02:fa:86"
# WiFi.SSID.5.Enable=0
# WiFi.SSID.5.Index=31
# WiFi.SSID.5.LastStatusChangeTimeStamp="2023-10-17T08:25:36Z"
# WiFi.SSID.5.LowerLayers="Device.WiFi.Radio.1."
# WiFi.SSID.5.MACAddress="5A:13:D3:02:FA:86"
# WiFi.SSID.5.Name="wlan0.2"
# WiFi.SSID.5.SSID="prplOS-guest"
# WiFi.SSID.5.Status="Down"
# WiFi.SSID.6.
# WiFi.SSID.6.Alias="vap6g0guest"
# WiFi.SSID.6.BSSID="58:13:d3:02:f9:88"
# WiFi.SSID.6.Enable=0
# WiFi.SSID.6.Index=32
# WiFi.SSID.6.LastStatusChangeTimeStamp="2023-10-17T08:25:36Z"
# WiFi.SSID.6.LowerLayers="Device.WiFi.Radio.3."
# WiFi.SSID.6.MACAddress="58:13:D3:02:F9:88"
# WiFi.SSID.6.Name="wlan4.2"
# WiFi.SSID.6.SSID="prplOS-guest"
# WiFi.SSID.6.Status="Down"
# WiFi.SSID.7.
# WiFi.SSID.7.Alias="ep5g0"
# WiFi.SSID.7.BSSID="00:00:00:00:00:00"
# WiFi.SSID.7.Enable=1
# WiFi.SSID.7.Index=33
# WiFi.SSID.7.LastStatusChangeTimeStamp="2023-10-17T08:26:04Z"
# WiFi.SSID.7.LowerLayers="Device.WiFi.Radio.2."
# WiFi.SSID.7.MACAddress="5A:13:D3:02:FC:89"
# WiFi.SSID.7.Name="wlan3"
# WiFi.SSID.7.SSID="PWHM_SSID7"
# WiFi.SSID.7.Status="Dormant"
# WiFi.SSID.7.Stats.WmmPacketsSent.AC_VO=0

#wpa_cli
#wps_pbc multiap=1

# configure private vaps
# 5GHz
ubus-cli WiFi.SSID.1.SSID="prplmesh_Paris_5GHz"
ubus-cli WiFi.AccessPoint.1.Security.KeyPassPhrase="prplmesh"
ubus-cli WiFi.AccessPoint.1.Security.ModeEnabled="WPA2-Personal"
#ubus-cli WiFi.AccessPoint.1.WPS.ConfigMethodsEnabled="PushButton"
sleep 5
ubus-cli WiFi.SSID.2.SSID="prplmesh_Paris_2.4GHz"
ubus-cli WiFi.AccessPoint.2.Security.KeyPassPhrase="prplmesh"
ubus-cli WiFi.AccessPoint.2.Security.ModeEnabled="WPA2-Personal"
#ubus-cli WiFi.AccessPoint.2.WPS.ConfigMethodsEnabled="PushButton"
sleep 5
ubus-cli WiFi.SSID.3.SSID="prplmesh_Paris_6GHz"
ubus-cli WiFi.AccessPoint.3.Security.KeyPassPhrase="prplmesh"
#ubus-cli WiFi.AccessPoint.3.Security.ModeEnabled="WPA2-Personal"
#ubus-cli WiFi.AccessPoint.3.WPS.ConfigMethodsEnabled="PushButton"

sleep 5


# Restrict channel bandwidth or the certification test could miss beacons
# (see PPM-258)
# ubus call "WiFi.Radio" _set '{ "rel_path": ".[OperatingFrequencyBand == \"2.4GHz\"].", "parameters": { "OperatingChannelBandwidth": "20MHz" } }'
# ubus call "WiFi.Radio" _set '{ "rel_path": ".[OperatingFrequencyBand == \"5GHz\"].", "parameters": { "OperatingChannelBandwidth": "40MHz" } }'
# ubus call "WiFi.Radio" _set '{ "rel_path": ".[OperatingFrequencyBand == \"6GHz\"].", "parameters": { "OperatingChannelBandwidth": "80MHz" } }'


# Prplmesh should do this
sleep 10
ubus-cli WiFi.SSID.1.Enable=1 # 5GHz
sleep 2
ubus-cli WiFi.SSID.2.Enable=1 # 2.4 GHz
sleep 2
ubus-cli WiFi.SSID.3.Enable=1 # 6GHz
sleep 5

ubus-cli WiFi.SSID.4.Enable=0 # 6GHz
ubus-cli WiFi.SSID.5.Enable=0 # 6GHz
ubus-cli WiFi.SSID.6.Enable=0 # 6GHz

# Make sure specific channels are configured. If channel is set to 0,
# ACS will be configured. If ACS is configured hostapd will refuse to
# switch channels when we ask it to. Channels 1 and 48 were chosen
# because they are NOT used in the WFA certification tests (this
# allows to verify that the device actually switches channel as part
# of the test).
# See also PPM-1928.
# ubus call "WiFi.Radio" _set '{ "rel_path": ".[OperatingFrequencyBand == \"2.4GHz\"].", "parameters": { "Channel": "8" } }'
# ubus call "WiFi.Radio" _set '{ "rel_path": ".[OperatingFrequencyBand == \"5GHz\"].", "parameters": { "Channel": "44" } }'

sleep 10

# Try to work around PCF-681: if we don't have a connectivity, restart
# tr181-bridging
# Check the status of the LAN bridge
# ip a |grep "br-lan:" |grep "state UP" >/dev/null || (echo "LAN Bridge DOWN, restarting bridge manager" && sh /etc/init.d/tr181-bridging restart && sleep 15)

# Stop the default ssh server on the lan-bridge
# sh /etc/init.d/ssh-server stop
# sleep 5

# Add command to start dropbear to rc.local to allow SSH access after reboot
# BOOTSCRIPT="/etc/rc.local"
# SERVER_CMD="sleep 20 && sh /etc/init.d/ssh-server stop && dropbear -F -T 10 -p192.168.1.1:22 &"
# if ! grep -q "$SERVER_CMD" "$BOOTSCRIPT"; then { head -n -2 "$BOOTSCRIPT"; echo "$SERVER_CMD"; tail -2 "$BOOTSCRIPT"; } >> btscript.tmp; mv btscript.tmp "$BOOTSCRIPT"; fi

# Stop and disable the firewall:
#sh /etc/init.d/tr181-firewall stop
#rm -f /etc/rc.d/S22tr181-firewall


# lighttpd -f /etc/lighttpd/mod-lighttpd.conf -D

# Change fcgi endpoint
sed -i 's/command/commands/g' /etc/lighttpd/conf.d/51-prplos-webui.conf /etc/lighttpd/conf.d/60-amx-fcgi.conf
sed -i 's;// disable;disable;' /etc/amx/amx-fcgi/amx-fcgi.odl
/etc/init.d/amx-fcgi stop ; sleep 3; /etc/init.d/amx-fcgi start;
/etc/init.d/tr181-httpaccess stop; sleep 5; /etc/init.d/tr181-httpaccess start; sleep 3


ubus-cli Firewall.Enable=0
/etc/init.d/tr181-firewall stop
iptables -P INPUT ACCEPT

service prplmesh restart

# start lighthttp
# /usr/sbin/lighttpd -f /etc/lighttpd/lighttpd.conf

# Start an ssh server on the control interface
# dropbear -F -T 10 -p192.168.1.1:22 &
