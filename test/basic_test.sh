#! /bin/bash

source "$(dirname $0)/functions.sh"

BINARY="$(readlink -f "$(dirname "$0")/../exadt")"
LICENSE="$(readlink -f "$(dirname "$0")/../license/license.xml")"
ROOT="$HOME"
IMAGE="exasol/docker-db-testing:latest"
DOCKER="$(which docker)"
TMP_DIR=$(mktemp -d)
INFO_FILE="$TMP_DIR/exasol_info.tgz"

cleanup() {
    rm -rf "$TMP_DIR"
}
trap cleanup exit
  
log() { 
    echo "[$(basename ${0})]: ${*}"
}
     
die() { 
    log "FATAL: ${*}"
    exit 1
}
 
usage() {
    echo "Usage: $0 [-i IMAGE] [-r ROOT] [-b EXADT_BINARY]"
    echo "Parameters:"
    echo "-i    : Docker image to use for the test (default: '$IMAGE')."
    echo "-D    : Docker command (default: '$DOCKER')."
    echo "-r    : Root directory for cluster creation (default: '$ROOT')."
    echo "-b    : The exadt binary (default: '$BINARY')."
    echo "-l    : The license (default: '$LICENSE')."
}

# parse parameters
while getopts "i:D:r:b:l:" opt; do
    case "$opt" in
        i)
            IMAGE="$OPTARG"
            log "INFO:: Using image '$IMAGE'."
            ;;
        D)
            DOCKER="$OPTARG"
            log "INFO:: Using Docker command '$DOCKER'."
            ;;
        r)
            ROOT="$(readlink -f "$OPTARG")"
            log "INFO:: Using root directory '$ROOT'."
            ;;
        b)
            BINARY="$(readlink -f $(which "$OPTARG"))"
            log "INFO:: Using binary '$BINARY'."
            ;;
        l)
            LICENSE="$(readlink -f "$OPTARG")"
            log "INFO:: Using license '$LICENSE'."
            ;;
        h)
            usage
            exit 0
            ;;
        ?)
            usage
            exit 1
            ;;
    esac
done


log "=== Starting exadt basic test ==="
set -e
$DOCKER pull "$IMAGE"
"$BINARY" list-clusters
"$BINARY" create-cluster --root "$ROOT/MyCluster/" --create-root MyCluster
"$BINARY" list-clusters
"$BINARY" collect-info --outfile "$INFO_FILE" MyCluster
"$BINARY" init-cluster --image "$IMAGE" --license "$LICENSE" --device-type file --auto-storage --force MyCluster
"$BINARY" list-clusters
"$BINARY" collect-info --outfile "$INFO_FILE" MyCluster
"$BINARY" start-cluster MyCluster
"$BINARY" ps MyCluster
"$BINARY" exec -c "/bin/date" -a MyCluster
wait_db "$BINARY" "DB1" MyCluster
"$BINARY" list-dbs MyCluster
"$BINARY" collect-info --outfile "$INFO_FILE" MyCluster
"$BINARY" exec -c "/bin/bash -c 'X=\$(ls /usr/opt/EXASuite-*/EXASolution-*/bin/Console/exaplus | tail -n1); echo \"SELECT 123*42345;\" | \$X -c n11:8888 -u sys -P exasol'" MyCluster 2>&1 | tee /dev/stderr | grep -q 5208435
"$BINARY" list-dbs MyCluster
"$BINARY" stop-db MyCluster
"$BINARY" start-db MyCluster
"$BINARY" stop-cluster MyCluster
"$BINARY" create-file-devices --size 10GiB MyCluster
yes | "$BINARY" create-file-devices --size 10GiB MyCluster --replace --path $HOME
"$BINARY" update-cluster --image "$IMAGE" MyCluster
"$BINARY" start-cluster MyCluster
"$BINARY" stop-cluster MyCluster
"$BINARY" start-cluster MyCluster --command "/bin/sleep 30"
"$BINARY" stop-cluster MyCluster --timeout 2
yes | "$BINARY" delete-cluster MyCluster
set +x
log "=== Successful! ==="
