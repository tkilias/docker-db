#! /bin/bash

BINARY="./exadt"
if (( $# > 0 )); then
    BINARY="$1"
fi

ROOT="$HOME"
if (( $# > 1 )); then
    ROOT="$2"
fi

echo "=== Starting exadt basic test ==="
set -x &&
"$BINARY" list-clusters &&
"$BINARY" create-cluster --root "$ROOT/MyCluster/" --create-root MyCluster &&
"$BINARY" list-clusters &&
"$BINARY" init-cluster --image exasol/docker-db:6.0.0-d1 --license ./license.xml --device-type file --auto-storage --force MyCluster &&
"$BINARY" list-clusters &&
"$BINARY" start-cluster MyCluster &&
"$BINARY" ps MyCluster &&
"$BINARY" stop-cluster MyCluster &&
"$BINARY" create-file-devices --size 10GiB MyCluster &&
yes | "$BINARY" create-file-devices --size 10GiB MyCluster --replace --path $HOME &&
"$BINARY" update-cluster --image exasol/docker-db:latest MyCluster &&
"$BINARY" start-cluster MyCluster &&
"$BINARY" stop-cluster MyCluster &&
"$BINARY" start-cluster MyCluster --command "/bin/sleep 30" &&
"$BINARY" stop-cluster MyCluster --timeout 2 &&
yes | "$BINARY" delete-cluster MyCluster &&
set +x &&
echo "=== Successful! ==="
