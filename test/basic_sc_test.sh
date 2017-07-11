#! /bin/bash
 
BINARY="docker"
if (( $# > 0 )); then
    BINARY="$1"
fi
VOLUME="exa_basic_sc_test_volume"
 
function wait_start () {
    echo -n "Waiting for container $1 to start... "
    while [[ -z $(docker logs "$1" 2>&1 | grep -e ".*Started.*exasql .*") ]]
    do
        sleep 3
    done
    echo "successful!"
    return 0
}

set -e
echo "=== Starting self-contained basic test ==="
echo "Creating container without a persistent volume"
CONTAINER=$("$BINARY" run --detach --privileged exasol/docker-db:latest) &&
wait_start "$CONTAINER" 
echo "Testing exaplus functionality"
"$BINARY" exec "$CONTAINER" /bin/bash -c 'X=$(ls /usr/opt/EXASuite-*/EXASolution-*/bin/Console/exaplus | tail -n1); echo "SELECT 123*42345;" | $X -c n11:8888 -u sys -P exasol' 2>&1 | tee /dev/stderr | grep -q 5208435
echo "Creating a file within the container"
"$BINARY" exec "$CONTAINER" touch /exa/my_file
echo "Stopping the container"
"$BINARY" stop -t 60 "$CONTAINER"
echo "Restarting the container"
"$BINARY" start "$CONTAINER"
wait_start "$CONTAINER"
echo -n "Checking if the file still exists... "
if [[ -z $("$BINARY" exec "$CONTAINER" find /exa -name my_file) ]]; then
    echo "File-check failed!"
    exit 1
else
    echo "successful!"
fi
echo "Stopping and deleting the container"
"$BINARY" stop "$CONTAINER"
"$BINARY" rm "$CONTAINER"
echo "Creating a new container with a persistent volume"
if [[ ! -z $("$BINARY" volume ls | grep "$VOLUME") ]]; then
    "$BINARY" volume rm "$VOLUME"
fi
CONTAINER=$("$BINARY" run --detach --privileged -v $VOLUME:/exa exasol/docker-db:latest) &&
wait_start "$CONTAINER" 

#TODO : test db persistency with exaplus (also DELETE the container before restarting it)

echo "Stopping and deleting the container"
"$BINARY" stop "$CONTAINER"
"$BINARY" rm "$CONTAINER"
"$BINARY" volume rm "$VOLUME"
echo "=== Successful! ==="
