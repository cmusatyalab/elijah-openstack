#!/bin/bash -ex
echo "nameserver ip: $CLOUDLET_NAMESERVER_IP"
echo "nameserver port: $CLOUDLET_NAMESERVER_PORT"
echo "nameserver pw: $CLOUDLET_NAMESERVER_PW"
echo "cloudlet instance id: $CLOUDLET_INSTANCE_ID"
MY_IP=$(ip route get 1.1.1.1 | awk '{print $NF; exit}')

# Turn on legacy flag
# lego demo should be using gabriel V1 to communicate, modify the version number here
# TODO: should change it to be a command line argument for control and ucomm
sed -i 's/LEGACY_JSON_ONLY_RESULT = False/LEGACY_JSON_ONLY_RESULT = True/' /gabriel/server/gabriel/common/config.py
# TODO: should move this to a gabriel feature. instead of changing the source file
# swarm is using eth1 as the public networking card
sed -i 's/eth0/eth1/' /gabriel/server/gabriel/common/network/util.py

if [ -z "$CLOUDLET_NAMESERVER_IP" ]; then
  control_vm_ip=${MY_IP}
  cd /gabriel/server/bin/
  python gabriel-control &
  sleep 2
  python gabriel-ucomm -s $MY_IP:8021 &
  sleep 2
else
  control_vm_ip=
  while [ -z "${control_vm_ip}" ]; do
    echo "getting control vm ip from nameserver..."
    control_vm_ip=$(redis-cli -h $CLOUDLET_NAMESERVER_IP -p $CLOUDLET_NAMESERVER_PORT -a $CLOUDLET_NAMESERVER_PW get "${1}_vm.${CLOUDLET_INSTANCE_ID}")
    sleep 2
  done
fi

echo "control vm ip: ${control_vm_ip}"
cd /gabriel-apps/"$1"/
python proxy.py -s ${control_vm_ip}:8021
