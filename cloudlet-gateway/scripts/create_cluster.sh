#!/bin/bash -e
# A SHORT DESCRIPTION OF YOUR SCRIPT GOES HERE
###############################################################################
set -e          # exit on command errors (so you MUST handle exit codes properly!)
set -E          # pass trap handlers down to subshells
set -o pipefail # capture fail exit codes in piped commands
#set -x         # execution tracing debug messages

# Error handler
on_err() {
	echo ">> ERROR: $?"
	FN=0
	for LN in "${BASH_LINENO[@]}"; do
		[ "${FUNCNAME[$FN]}" = "main" ] && break
		echo ">> ${BASH_SOURCE[$FN]} $LN ${FUNCNAME[$FN]}"
		FN=$(( FN + 1 ))
	done
}
trap on_err ERR

# Exit handler
declare -a EXIT_CMDS
add_exit_cmd() { EXIT_CMDS+="$*;  "; }
on_exit(){ eval "${EXIT_CMDS[@]}"; }
trap on_exit EXIT

# Get command info
CMD_PWD=$(pwd)
CMD="$0"
CMD_DIR="$(cd "$(dirname "$CMD")" && pwd -P)"

# Defaults and command line options
[ "$VERBOSE" ] ||  VERBOSE=
[ "$DEBUG" ]   ||  DEBUG=
[ "$NUM" ]   ||  NUM=1

# Basic helpers
out() { echo "$(date +%Y%m%dT%H%M%SZ): $*"; }
err() { out "$*" 1>&2; }
vrb() { [ ! "$VERBOSE" ] || out "$@"; }
dbg() { [ ! "$DEBUG" ] || err "$@"; }
die() { err "EXIT: $1" && [ "$2" ] && [ "$2" -ge 0 ] && exit "$2" || exit 1; }

# Show help function to be used below
show_help() {
	awk 'NR>1{print} /^(###|$)/{exit}' "$CMD"
	echo "USAGE: $(basename "$CMD") [arguments]"
	echo "ARGS:"
	MSG=$(awk '/^NARGS=-1; while/,/^esac; done/' "$CMD" | sed -e 's/^[[:space:]]*/  /' -e 's/|/, /' -e 's/)//' | grep '^  -')
	EMSG=$(eval "echo \"$MSG\"")
	echo "$EMSG"
}

# Parse command line options (odd formatting to simplify show_help() above)
NARGS=-1; while [ "$#" -ne "$NARGS" ]; do NARGS=$#; case $1 in
	# SWITCHES
	-h|--help)      # This help message
		show_help; exit 1; ;;
	-d|--debug)     # Enable debugging messages (implies verbose)
		DEBUG=$(( DEBUG + 1 )) && VERBOSE="$DEBUG" && shift && echo "#-INFO: DEBUG=$DEBUG (implies VERBOSE=$VERBOSE)"; ;;
	-v|--verbose)   # Enable verbose messages
		VERBOSE=$(( VERBOSE + 1 )) && shift && echo "#-INFO: VERBOSE=$VERBOSE"; ;;
	# PAIRS
	-e|--envfile)     # openstack environment file
		shift && envfile="$1" && shift ; ;;
	-n|--number)      # number of nodes
		shift && number="$1" && shift && vrb "#-INFO: number=$NUM"; ;;
	-p|--prefix)      # node prefix
		shift && prefix="$1" && shift ; ;;
	*)
		break;
esac; done

[ "$DEBUG" ]  &&  set -x

create_machines(){
    local prefix=$1
    local number=$2
    docker-machine --debug create --driver openstack --openstack-flavor-name {{openstack_flavor}} \
--openstack-image-name {{openstack_image}} --openstack-net-name {{openstack_network}} --openstack-ssh-user {{ssh_user}} \
--openstack-sec-groups default --openstack-floatingip-pool nova --openstack-nova-network "$prefix-0" || \
die "ERROR: Failed to create swarm master!"
    # default docker_gwbridge conflicts with LEL vpn subnet (172.18.x.x), change the docker_gwbridge to 172.127
    # https://github.com/moby/moby/issues/17217
    docker-machine ssh "$prefix-0" "sudo docker network create --subnet=172.127.0.0/16 -o com.docker.network.bridge.enable_icc=false -o com.docker.network.bridge.name=docker_gwbridge -o com.docker.network.bridge.enable_ip_masquerade=true docker_gwbridge"

    local idx=1
    while [[ $idx -lt $number ]]; do
        docker-machine --debug create --driver openstack --openstack-flavor-name {{openstack_flavor}} \
    --openstack-image-name {{openstack_image}} --openstack-net-name {{openstack_network}} --openstack-ssh-user {{ssh_user}} \
    --openstack-sec-groups default --openstack-floatingip-pool nova --openstack-nova-network "${prefix}-${idx}" || \
    die "ERROR: Failed to create swarm slave ${idx}!"
        docker-machine ssh "${prefix}-${idx}" "sudo docker network create --subnet=172.127.0.0/16 -o com.docker.network.bridge.enable_icc=false -o com.docker.network.bridge.name=docker_gwbridge -o com.docker.network.bridge.enable_ip_masquerade=true docker_gwbridge"
        (( idx++ ))
    done
}

init_cluster(){
    echo "initializing swarm cluster"
    local prefix="$1"
    eval $(docker-machine env "${prefix}-0")
    log="$(docker swarm init)"
    echo "$log"
    token="$(echo "$log" | awk '/--token/{print $2}')"
    echo "swarm token is $token"
    leader_ip="$(echo "$log" | awk '/[0-9\.]+:[0-9]+/{print $1}')"
    echo "leader ip is $leader_ip"
    local num="$2"
    local idx=1
    while [[ $idx -lt $num ]]; do
       echo "join node $idx to swarm"
       eval $(docker-machine env "${prefix}-${idx}")
       docker swarm join --token "$token" "$leader_ip"
       (( idx++ ))
    done
    echo "point docker to swarm leader"
    eval $(docker-machine env "${prefix}-0")
}

check_cluster(){
    echo "check cluster"
    docker node ls
}

create_redis_nameserver(){
   # TODO: make the port number dynamic instead of fixed
   # redis is not secured by SSL
   docker service create --name redis-nameserver --replicas 1 --publish 8245:6379 redis --requirepass $REDIS_NAMESERVER_PW
}

create_monitor_services(){
  docker service create   --name=viz   --publish=8080:8080/tcp   --constraint=node.role==manager   --mount=type=bind,src=/var/run/docker.sock,dst=/var/run/docker.sock   dockersamples/visualizer
  docker service create --name portainer --publish 9000:9000 --constraint 'node.role == manager' --mount type=bind,src=/var/run/docker.sock,dst=/var/run/docker.sock portainer/portainer --no-auth -H unix:///var/run/docker.sock
}
###############################################################################

# Validate some things
#TODO: You will probably want to change this but this is an example of simple params validation
[ "$envfile" ]  ||  die "You must provide openstack rc file"
[ "$number" ]  ||  die "You must provide number of nodes"
[ "$prefix" ]  ||  die "You must provide node prefixes"
[ $# -eq 0 ]  ||  die "ERROR: Unexpected commands!"

if ! type "docker-machine" > /dev/null; then
     echo "no docker-machine found"
     exit 1
fi

source "$envfile"

create_machines $prefix $number
init_cluster $prefix $number
check_cluster
create_redis_nameserver
create_monitor_services
echo "finished!"