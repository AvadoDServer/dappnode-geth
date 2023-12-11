#!/bin/sh

case ${NETWORK} in
"goerli")
  P2P_PORT=39303
  DATA_DIR="/goerli"
  NET_ARG="--goerli"
  ;;
"holesky")
  P2P_PORT=39393
  DATA_DIR="/data"
  NET_ARG="--holesky"
  ;;
*)
  P2P_PORT=30303
  DATA_DIR="/root/.ethereum/ethchain-geth/"
  NET_ARG="--mainnet"
  ;;
esac

# Older installations use the deprecated option "--rpcapi" so replace it by "--http.api"
export EXTRA_OPTS_PARSED=$(echo -n $EXTRA_OPTS | sed s/--rpcapi/--http\.api/g)

# Get JWT Token
JWT_TOKEN="${DATA_DIR}/geth/jwttoken"
mkdir -p $(dirname ${JWT_TOKEN})
until $(curl --silent --fail "http://dappmanager.my.ava.do/jwttoken.txt" --output "${JWT_TOKEN}"); do
  echo "Waiting for the JWT Token"
  sleep 5
done

echo "EXTRA_OPTS=$EXTRA_OPTS_PARSED"
echo "GETH_CMD=$GETH_CMD"

# Print version to the log
/usr/local/bin/geth version

/usr/local/bin/geth \
  --datadir ${DATA_DIR} \
  ${NET_ARG} \
  --port ${P2P_PORT} \
  --http \
  --http.addr="0.0.0.0" \
  --http.corsdomain="*" \
  --http.vhosts="*" \
  --ws \
  --ws.origins="*" \
  --ws.addr="0.0.0.0" \
  --authrpc.vhosts="*" \
  --authrpc.addr="0.0.0.0" \
  --authrpc.port="8551" \
  --authrpc.jwtsecret="${JWT_TOKEN}" \
  ${EXTRA_OPTS_PARSED}
