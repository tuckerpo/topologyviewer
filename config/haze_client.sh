#!/bin/sh

# We need to source some files which are only available on prplWrt
# devices, so prevent shellcheck from trying to read them:
# shellcheck disable=SC1091

set -e

# Start with a new log file:
rm -f /var/log/messages && syslog-ng-ctl reload


ubus wait_for IP.Interface

# Wired backhaul interface:
uci set prplmesh.config.backhaul_wire_iface='lan3'
uci commit

# Devices which should support backhaul:
ubus-cli "WiFi.Radio.*.STA_Mode=1"


# Stop and disable the DHCP clients and servers:
if ubus call DHCPv4Server _list ; then
  ubus call DHCPv4Server _set '{"parameters": { "Enable": False }}'
  echo "Disabled DHCPv4 server!"
else
    echo "DHCPv6 service not active!"
fi
if ubus call DHCPv6Server _list ; then
  ubus call DHCPv6Server _set '{"parameters": { "Enable": False }}'
  echo "Disabled DHCPv6 server!"
else
    echo "DHCPv6 service not active!"
fi


# Set the LAN bridge IP:
ubus call "IP.Interface" _set '{ "rel_path": ".[Name == \"br-lan\"].IPv4Address.[Alias == \"lan\"].", "parameters": { "IPAddress": "192.168.1.14" } }'

service prplmesh restart



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
ubus wait_for Bridging.Bridge
ubus call "Bridging.Bridge" _get '{ "rel_path": ".[Alias == \"lan\"].Port.[Name == \"wan\"]." }' || {
    echo "Adding interface to bridge"
    ubus call "Bridging.Bridge" _add '{ "rel_path": ".[Alias == \"lan\"].Port.",  "parameters": { "Name": "wan", "Alias": "WAN", "LowerLayers": "Device.Ethernet.Interface.1." ,"Enable": true } }'
}

sleep 10



# Wired backhaul interface:
uci set prplmesh.config.backhaul_wire_iface='lan3'
uci commit

# enable Wi-Fi radios
# ubus call "WiFi.Radio" _set '{ "rel_path": ".[OperatingFrequencyBand == \"2.4GHz\"].", "parameters": { "Enable": "true" } }'
# ubus call "WiFi.Radio" _set '{ "rel_path": ".[OperatingFrequencyBand == \"5GHz\"].", "parameters": { "Enable": "true" } }'
# ubus call "WiFi.Radio" _set '{ "rel_path": ".[OperatingFrequencyBand == \"6GHz\"].", "parameters": { "Enable": "true" } }'

sleep 10



# WiFi.SSID.1.
# WiFi.SSID.1.Alias="DEFAULT_RADIO0"
# WiFi.SSID.1.BSSID="4e:68:6c:c4:26:1c"
# WiFi.SSID.1.Enable=0
# WiFi.SSID.1.Index=15
# WiFi.SSID.1.LastStatusChangeTimeStamp="2023-10-12T09:44:49Z"
# WiFi.SSID.1.LowerLayers="Device.WiFi.Radio.1."
# WiFi.SSID.1.MACAddress="4E:68:6C:C4:26:1C"
# WiFi.SSID.1.Name="wlan0.1"
# WiFi.SSID.1.SSID="prplOS"
# WiFi.SSID.1.Status="Down"
# WiFi.SSID.2.
# WiFi.SSID.2.Alias="GUEST_RADIO0"
# WiFi.SSID.2.BSSID="4e:68:6c:c4:26:1d"
# WiFi.SSID.2.Enable=0
# WiFi.SSID.2.Index=16
# WiFi.SSID.2.LastStatusChangeTimeStamp="2023-10-12T09:44:49Z"
# WiFi.SSID.2.LowerLayers="Device.WiFi.Radio.1."
# WiFi.SSID.2.MACAddress="4E:68:6C:C4:26:1D"
# WiFi.SSID.2.Name="wlan0.2"
# WiFi.SSID.2.SSID="prplOS-guest"
# WiFi.SSID.2.Status="Down"
# WiFi.SSID.3.
# WiFi.SSID.3.Alias="DEFAULT_RADIO1"
# WiFi.SSID.3.BSSID="4e:68:6c:c4:25:1a"
# WiFi.SSID.3.Enable=0
# WiFi.SSID.3.Index=10
# WiFi.SSID.3.LastStatusChangeTimeStamp="2023-10-12T09:44:52Z"
# WiFi.SSID.3.LowerLayers="Device.WiFi.Radio.2."
# WiFi.SSID.3.MACAddress="4E:68:6C:C4:25:1A"
# WiFi.SSID.3.Name="wlan1"
# WiFi.SSID.3.SSID="prplOS"
# WiFi.SSID.3.Status="Down"
# WiFi.SSID.4.
# WiFi.SSID.4.Alias="GUEST_RADIO1"
# WiFi.SSID.4.BSSID="4e:68:6c:c4:27:1b"
# WiFi.SSID.4.Enable=0
# WiFi.SSID.4.Index=17
# WiFi.SSID.4.LastStatusChangeTimeStamp="2023-10-12T09:44:49Z"
# WiFi.SSID.4.LowerLayers="Device.WiFi.Radio.2."
# WiFi.SSID.4.MACAddress="4E:68:6C:C4:27:1B"
# WiFi.SSID.4.Name="wlan1.1"
# WiFi.SSID.4.SSID="prplOS-guest"
# WiFi.SSID.4.Status="Down"
# WiFi.SSID.5.
# WiFi.SSID.5.Alias="DEFAULT_RADIO2"
# WiFi.SSID.5.BSSID="4e:68:6c:c4:25:1c"
# WiFi.SSID.5.Enable=0
# WiFi.SSID.5.Index=11
# WiFi.SSID.5.LastStatusChangeTimeStamp="2023-10-12T09:44:53Z"
# WiFi.SSID.5.LowerLayers="Device.WiFi.Radio.3."
# WiFi.SSID.5.MACAddress="4E:68:6C:C4:25:1C"
# WiFi.SSID.5.Name="wlan2"
# WiFi.SSID.5.SSID="prplOS"
# WiFi.SSID.5.Status="Down"
# WiFi.SSID.6.
# WiFi.SSID.6.Alias="GUEST_RADIO2"
# WiFi.SSID.6.BSSID="4e:68:6c:c4:25:1d"
# WiFi.SSID.6.Enable=0
# WiFi.SSID.6.Index=18
# WiFi.SSID.6.LastStatusChangeTimeStamp="2023-10-12T09:44:49Z"
# WiFi.SSID.6.LowerLayers="Device.WiFi.Radio.3."
# WiFi.SSID.6.MACAddress="4E:68:6C:C4:25:1D"
# WiFi.SSID.6.Name="wlan2.1"
# WiFi.SSID.6.SSID="prplOS-guest"
# WiFi.SSID.6.Status="Down"
# WiFi.SSID.7.
# WiFi.SSID.7.Alias="ep5g0"
# WiFi.SSID.7.BSSID="00:00:00:00:00:00"
# WiFi.SSID.7.Enable=1
# WiFi.SSID.7.Index=9
# WiFi.SSID.7.LastStatusChangeTimeStamp="2023-10-12T09:44:48Z"
# WiFi.SSID.7.LowerLayers="Device.WiFi.Radio.1."
# WiFi.SSID.7.MACAddress="4E:68:6C:C4:25:1B"
# WiFi.SSID.7.Name="wlan0"
# WiFi.SSID.7.SSID="PWHM_SSID7"
# WiFi.SSID.7.Status="Dormant"
# WiFi.SSID.7.Stats.WmmPacketsSent.AC_VO=0








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
sh /etc/init.d/ssh-server restart

# Required for config_load:
. /lib/functions/system.sh
# Required for config_foreach:
. /lib/functions.sh

# add private vaps to lan to workaround Netmodel missing wlan mib
# this must be reverted once Netmodel version is integrated
# brctl addif br-lan wlan0 > /dev/null 2>&1 || true
# brctl addif br-lan wlan1 > /dev/null 2>&1 || true
# brctl addif br-lan wlan2 > /dev/null 2>&1 || true

# configure private vaps
# ubus call "WiFi.SSID.1" _set '{ "parameters": { "SSID": "prplmesh_Paris_2.4GHz" } }'
# ubus call "WiFi.SSID.2" _set '{ "parameters": { "SSID": "prplmesh_Paris_5GHz" } }'
# ubus call "WiFi.SSID.6" _set '{ "parameters": { "SSID": "prplmesh_Paris_6GHz" } }'
# ubus call "WiFi.AccessPoint.1.Security" _set '{ "parameters": { "KeyPassPhrase": "prplmesh_pass" } }'
# ubus call "WiFi.AccessPoint.2.Security" _set '{ "parameters": { "KeyPassPhrase": "prplmesh_pass" } }'
# ubus call "WiFi.AccessPoint.5.Security" _set '{ "parameters": { "KeyPassPhrase": "prplmesh_pass" } }'
# ubus call "WiFi.AccessPoint.1.Security" _set '{ "parameters": { "ModeEnabled": "WPA2-Personal" } }'
# ubus call "WiFi.AccessPoint.2.Security" _set '{ "parameters": { "ModeEnabled": "WPA2-Personal" } }'
# ubus call "WiFi.AccessPoint.5.Security" _set '{ "parameters": { "ModeEnabled": "WPA2-Personal" } }'
# ubus call "WiFi.AccessPoint.1.WPS" _set '{ "parameters": { "ConfigMethodsEnabled": "PushButton" } }'
# ubus call "WiFi.AccessPoint.2.WPS" _set '{ "parameters": { "ConfigMethodsEnabled": "PushButton" } }'
# ubus call "WiFi.AccessPoint.5.WPS" _set '{ "parameters": { "ConfigMethodsEnabled": "PushButton" } }'





# configure private vaps - new image (preview 3.1)
# ubus call "WiFi.SSID.1" _set '{ "parameters": { "SSID": "prplmesh_Paris_5GHz" } }'
# ubus call "WiFi.SSID.3" _set '{ "parameters": { "SSID": "prplmesh_Paris_2.4GHz" } }'
# ubus call "WiFi.SSID.5" _set '{ "parameters": { "SSID": "prplmesh_Paris_6GHz" } }'
#
# ubus call "WiFi.AccessPoint.1.Security" _set '{ "parameters": { "KeyPassPhrase": "prplmesh_pass" } }'
# ubus call "WiFi.AccessPoint.2.Security" _set '{ "parameters": { "KeyPassPhrase": "prplmesh_pass" } }'
# ubus call "WiFi.AccessPoint.5.Security" _set '{ "parameters": { "KeyPassPhrase": "prplmesh_pass" } }'
# ubus call "WiFi.AccessPoint.1.Security" _set '{ "parameters": { "ModeEnabled": "WPA2-Personal" } }'
# ubus call "WiFi.AccessPoint.2.Security" _set '{ "parameters": { "ModeEnabled": "WPA2-Personal" } }'
# ubus call "WiFi.AccessPoint.5.Security" _set '{ "parameters": { "ModeEnabled": "WPA2-Personal" } }'
# ubus call "WiFi.AccessPoint.1.WPS" _set '{ "parameters": { "ConfigMethodsEnabled": "PushButton" } }'
# ubus call "WiFi.AccessPoint.2.WPS" _set '{ "parameters": { "ConfigMethodsEnabled": "PushButton" } }'
# ubus call "WiFi.AccessPoint.5.WPS" _set '{ "parameters": { "ConfigMethodsEnabled": "PushButton" } }'


#ubus-cli WiFi.AccessPoint.1.Enable=1
#ubus-cli WiFi.AccessPoint.2.Enable=1
#ubus-cli WiFi.AccessPoint.5.Enable=1

ubus-cli WiFi.SSID.1.Enable=1 # 5GHz
ubus-cli WiFi.SSID.3.Enable=1 # 2.4GHz
ubus-cli WiFi.SSID.5.Enable=1 # 6GHz


# Restrict channel bandwidth or the certification test could miss beacons
# (see PPM-258)
#ubus call "WiFi.Radio" _set '{ "rel_path": ".[OperatingFrequencyBand == \"2.4GHz\"].", "parameters": { "OperatingChannelBandwidth": "20MHz" } }'
#ubus call "WiFi.Radio" _set '{ "rel_path": ".[OperatingFrequencyBand == \"5GHz\"].", "parameters": { "OperatingChannelBandwidth": "20MHz" } }'

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
SERVER_CMD="sleep 20 && sh /etc/init.d/ssh-server stop && dropbear -F -T 10 -p192.168.1.10:22 &"
if ! grep -q "$SERVER_CMD" "$BOOTSCRIPT"; then { head -n -2 "$BOOTSCRIPT"; echo "$SERVER_CMD"; tail -2 "$BOOTSCRIPT"; } >> btscript.tmp; mv btscript.tmp "$BOOTSCRIPT"; fi

# Stop and disable the firewall:
sh /etc/init.d/tr181-firewall stop
rm -f /etc/rc.d/S22tr181-firewall

# Start an ssh server on the control interface
dropbear -F -T 10 -p192.168.1.10:22 &
