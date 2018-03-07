#! /bin/bash
 
DOCKER="$(which docker)"
VOLUME="exa_basic_sc_test_volume"
IMAGE="exasol/docker-db-dev:latest"
  
usage() {
    echo "Usage: $0 [-i IMAGE] [-D DOCKER CMD]"
    echo "Parameters:"
    echo "-i    : Docker image to use for the test (default: '$IMAGE')."
    echo "-D    : Docker command (default: '$DOCKER')."
}
   
log() { 
    echo "[$(basename ${0})]: ${*}"
}
     
die() { 
    log "FATAL: ${*}"
    exit 1
}
 
# parse parameters
while getopts "i:D:h" opt; do
    case "$opt" in
        i)
            IMAGE="$OPTARG"
            log "INFO:: Using image '$IMAGE'."
            ;;
        D)
            DOCKER="$OPTARG"
            log "INFO:: Using Docker command '$DOCKER'."
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
 
wait_start() {
    echo -n "Waiting for container $1 to start... "
    while [[ -z $(docker logs "$1" 2>&1 | grep -e ".*Started.*exasql .*") ]]
    do
        sleep 3
    done
    echo "successful!"
    return 0
}

"$DOCKER" pull "$IMAGE" # does not work with local built dev-images
set -e
log "=== Starting self-contained basic test ==="
log "Creating container without a persistent volume"
CONTAINER=$("$DOCKER" run --detach --privileged "$IMAGE") &&
wait_start "$CONTAINER" 
echo "Testing exaplus functionality"
"$DOCKER" exec "$CONTAINER" /bin/bash -c 'X=$(ls /usr/opt/EXASuite-*/EXASolution-*/bin/Console/exaplus | tail -n1); echo "SELECT 123*42345;" | $X -c n11:8888 -u sys -P exasol' 2>&1 | tee /dev/stderr | grep -q 5208435
echo "Creating a file within the container"
"$DOCKER" exec "$CONTAINER" touch /exa/my_file
echo "Stopping the container"
"$DOCKER" stop -t 60 "$CONTAINER"
echo "Restarting the container"
"$DOCKER" start "$CONTAINER"
wait_start "$CONTAINER"
echo -n "Checking if the file still exists... "
if [[ -z $("$DOCKER" exec "$CONTAINER" find /exa -name my_file) ]]; then
    echo "File-check failed!"
    exit 1
else
    echo "successful!"
fi
echo "Stopping and deleting the container"
"$DOCKER" stop "$CONTAINER"
"$DOCKER" rm "$CONTAINER"
log "Creating a new container with a persistent volume"
if [[ ! -z $("$DOCKER" volume ls | grep "$VOLUME") ]]; then
    "$DOCKER" volume rm "$VOLUME"
fi
CONTAINER=$("$DOCKER" run --detach --privileged -v $VOLUME:/exa "$IMAGE") &&
wait_start "$CONTAINER" 

#TODO : test db persistency with exaplus (also DELETE the container before restarting it)

echo "Stopping and deleting the container"
"$DOCKER" stop "$CONTAINER"
"$DOCKER" rm "$CONTAINER"
"$DOCKER" volume rm "$VOLUME"
log "=== Successful! ==="
