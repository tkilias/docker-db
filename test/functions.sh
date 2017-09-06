#! /bin/bash

# wait for the database to start and accept connections
# $1 = exadt binary
# $2 = database name
# $3 = cluster name
wait_db() {
    # 'exec' command has been introduced with 6.0.1, so we have to check for support first!
    if [[ -z $("$1" --help | grep exec) ]]; then
        echo "'exec' is not supported! Sleeping for 30 seconds instead"
        sleep 30
    else
        echo "waiting for $2 to start"
        while [[ -z $("$1" exec -c "dwad_client shortlist" "$3" | grep "$2") ]]
        do
            sleep 3
        done
        "$1" exec -c "dwad_client wait-state $2 running 60" "$3"
        while true
        do
            "$1" exec -c "dwad_client print-params $2" "$3" 2>&1 | grep -q 'Connection state: up' && break
            sleep 3
        done
    fi
    return 0
}
 
