#! /bin/bash

echo "=== Starting exadt basic test ==="
set -x &&
./exadt create-cluster --root ~/MyCluster/ --create-root MyCluster &&
./exadt list-clusters &&
./exadt init-cluster --image exasol/docker-db:6.0.0-d1 --license ./license.xml --device-type file --auto-storage --force MyCluster &&
./exadt start-cluster MyCluster &&
./exadt ps MyCluster &&
./exadt stop-cluster MyCluster &&
./exadt create-file-devices --size 10GiB MyCluster &&
./exadt create-file-devices --size 10GiB MyCluster --replace --path $HOME &&
./exadt update-cluster --image exasol/docker-db:latest MyCluster &&
./exadt start-cluster MyCluster &&
./exadt stop-cluster MyCluster &&
./exadt start-cluster MyCluster --command "/bin/sleep 30" &&
./exadt stop-cluster MyCluster --timeout 2 &&
./exadt delete-cluster MyCluster &&
set +x &&
echo "=== Successful! ==="
