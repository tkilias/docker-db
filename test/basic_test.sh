#! /bin/bash

BINARY="./exadt"
if (( $# > 0 )); then
    BINARY="$1"
fi

ROOT="$HOME"
if (( $# > 1 )); then
    ROOT="$2"
fi

function wait_db () {
    echo "waiting for $1 to start"
    while [[ -z $("$BINARY" exec -q -c "dwad_client shortlist" MyCluster) ]]
    do
        sleep 3
    done
    "$BINARY" exec -c "dwad_client wait-state $1 running 60" MyCluster
    while true
    do
        "$BINARY" exec -q -c "dwad_client print-params $1" MyCluster 2>&1 | grep -q 'Connection state: up' && break
        sleep 3
    done
    return 0
}

echo "=== Starting exadt basic test ==="
set -e
set -x
"$BINARY" list-clusters
"$BINARY" create-cluster --root "$ROOT/MyCluster/" --create-root MyCluster
"$BINARY" list-clusters
"$BINARY" init-cluster --image exasol/docker-db:6.0.2-d1 --license ./license.xml --device-type file --auto-storage --force MyCluster
"$BINARY" list-clusters
"$BINARY" start-cluster MyCluster
"$BINARY" ps MyCluster
"$BINARY" exec -c "/bin/date" -a MyCluster
wait_db "DB1"
"$BINARY" exec -c "/bin/bash -c 'X=\$(ls /usr/opt/EXASuite-*/EXASolution-*/bin/Console/exaplus | tail -n1); echo \"SELECT 123*42345;\" | \$X -c n11:8888 -u sys -P exasol'" MyCluster 2>&1 | tee /dev/stderr | grep -q 5208435
"$BINARY" stop-db MyCluster
"$BINARY" start-db MyCluster
"$BINARY" stop-cluster MyCluster
"$BINARY" create-file-devices --size 10GiB MyCluster
yes | "$BINARY" create-file-devices --size 10GiB MyCluster --replace --path $HOME
"$BINARY" update-cluster --image exasol/docker-db:latest MyCluster
"$BINARY" start-cluster MyCluster
"$BINARY" stop-cluster MyCluster
"$BINARY" start-cluster MyCluster --command "/bin/sleep 30"
"$BINARY" stop-cluster MyCluster --timeout 2
yes | "$BINARY" delete-cluster MyCluster
set +x
echo "=== Successful! ==="
