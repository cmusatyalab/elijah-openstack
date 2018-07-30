# need to source open stack rc
source openrc.sh
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
export CAAS_SECRET='super-secret-key'
export FLASK_APP=$DIR/autoapp.py
export FLASK_DEBUG=1
export DB_USER='database-user'
export DB_PW='database-password'
export CAAS_CERT=$HOME/env/caas/keys/domain.crt
export CAAS_KEY=$HOME/env/caas/keys/domain.key
export DEFAULT_PROVIDER='cloudlet'
export DEFAULT_PROVIDER_PW='cloudlet-caas'
export REDIS_NAMESERVER_PW='cloudlet-caas'
