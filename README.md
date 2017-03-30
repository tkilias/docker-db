
# What is EXASOL?          

EXASOL is the intelligent, high-performance in-memory analytic database that just works.

# What is in this repository?

This repository contains a dockerized version of the EXASOL DB version 6.0 suitable for testing.

Currently supported features:
- create / start / stop a database in a virtual cluster
- use the UDF framework
- expose ports from containers on the local host
- update the virtual cluster
- create backups on archive volumes

Features to be supported soon:
- block devices for data storage
- backups on remote volumes
- license handling

Features still in development:
- multinode setup
- XML/RPC interface

# How to use this image

- Pull the image to your Docker host:

```console
$ docker pull exasol/docker-db:6.0.0-d1
```

- Install the `exadt` dependencies:

```console
$ pip install docker ipaddr ConfigObj
```

- Install `exadt`:

```console
$ git clone git@github.com:EXASOL/docker-db.git
$ cd docker-db
```

- Create and configure your virtual EXASOL cluster by using the commands described in the `exadt` documentation below.

# EXASOL Docker Tool — `exadt`

The `exadt` command-line tool is used to create, initialize, start, stop, update and delete a Docker based EXASOL cluster.

## 1. Creating a cluster

Select a root directory for your EXASOl cluster. It will be used to store the data, metadata and buckets of all local containers and should therefore be located on a filesystem with sufficient free space (min. 10 GiB are recommended).

```console
$ ./exadt create-cluster --root ~/MyCluster/ --create-root MyCluster
Successfully created cluster 'MyCluster' with root directory '/home/user/MyCluster/'.
```

`exadt` stores information about all clusters within `$HOME/.exadt.conf` and `/etc/exadt.conf` (if the current user has write permission in `/etc`). Both files are searched when executing a command that needs the cluster name as an argument. 

In order to list all existing clusters you can use `exadt list-clusters`:

```console
$ ./exadt list-clusters
 CLUSTER                     ROOT                                       IMAGE                    
 MyCluster                   /home/user/MyCluster                       <uninitialized>
```

## 2. Initializing a cluster

After creating a cluster it has to be initialized. Mandatory parameters are:

- the EXASOL Docker image 
- the license file
- the type of EXAStorage devices (currently only 'file' is supported)

```console
$ ./exadt init-cluster --image exasol/docker-db:6.0.0-d1 --license license.xml --device-type file --auto-storage --force MyCluster
Successfully initialized configuration in '/home/user/MyCluster/EXAConf'.
Successfully initialized root directory '/home/user/MyCluster/'.
```

This command creates subdirectories for each virtual node in the root directory. These are mounted as Docker volumes within each container (at '/exa') and contain all data, metadata and buckets.

It also creates the file `EXAConf` in the root directory, which contains the configuration for the whole cluster and currently has to be edited manually if a non-default setup is used.

### Automatically creating and assigning file devices

The example above uses the `--auto-storage` option which tells `exadt` to automatically create file-devices for all virtual nodes (within the root directory). These devices are assigned to the EXAStorage volumes, that are also automatically created. The devices need at least 10GiB of free space and use up to 100GiB of it (all devices combined). 

If `--auto-storage` is used, you can skip the next step entirely (and *continue with section 4*).

## 3. Adding EXAStorage devices

NOTE:  This step can be skipped if `--auto-storage` has been used during initialization.

Next, devices for EXAStorage need to be added. This can be done by executing:

```console
$ ./exadt create-file-devices --size 80GiB MyCluster
Successfully created the following file devices:
Node 11 : ['/home/user/MyCluster/n11/data/storage/dev.1']
```

This example creates two devices per container, but a single device is sufficient. As you can see, the file devices are created within the `data/storage` subdirectory of each node's Docker root. They are created as *sparse files*, i. e. their size is stated as the given size but they actually have size 0 and grow as new data is being written.

All devices must be assigned to a 'disk'. A disk is a group of devices that can be assigned to an EXAStorage volume. The disk name can be specified with the `--disk` parameter. If omitted, the newly created devices will be assigned to the disk named 'default'.

### Assigning devices to volumes

After creating the devices, they have to be assigned to the corresponding volumes. If you did not use `--auto-storage` (see above), you have to edit `EXAConf` manually. Open it and locate the following section:

```
[EXAVolume : DataVolume1]
    Type = data
    Nodes = 11
    Disk =
    Size =
    Redundancy = 1
```

Now add the name of the disk ('default', if you did not specify a name when executing `create-file-devices`) and the volume size, e. g:

```
    Disk = default
    Size = 100GiB
```

Then do the same for the section `[EXAVolume : ArchiveVolume1]`.

Make sure not to make the volume too big! The specified size is the size that is available for the database, i. e. if the redundancy is 2, the volume will actually use twice the amount of space! Also make sure to leave some free space for the temporary volume, that is created by the database during startup.

## 4. Starting a cluster

The cluster is started using the `exadt start-cluster` command. Before the containers are actually created, `exadt` checks if there is enough free space for the sparse files (if they grow to their max. size). If not, the startup will fail:

```console
$ ./exadt start-cluster MyCluster
Free space on '/' is only 22.2 GiB, but accumulated size of (sparse) file-devices is 80.0 GiB!
'ERROR::DockerHandler: Check for space usage failed! Aborting startup.'
```

If that's the case, you can replace the existing devices with smaller ones and (optionally) place them on an external partition:

```console
$ ./exadt create-file-devices --size 10GiB MyCluster --replace --path /mnt/data/
Do you really want to replace all file-devices of cluster 'MyCluster'? (y/n): y
The following file devices have been removed:
Node 11 : ['/home/user/MyCluster/n11/data/storage/dev.1']
Successfully created the following file devices:
Node 11 : ['/mnt/data/n11/dev.1']
```

The devices that are located outside of the root directory are mapped into the file system of the container (within `/exa/data/storage/`). They are often referenced as 'mapped devices'.

Now the cluster can be started:

```console
$ ./exadt start-cluster MyCluster
Copying EXAConf to all node volumes.
Creating private network 10.10.10.0/24 ('MyCluster_priv')... successful
No public network specified.
Creating container 'MyCluster_11'... successful
Starting container 'MyCluster_11'... successful
```

This command creates and starts all containers and networks. Each cluster uses one or two networks to connect the containers. These networks are not connected to other clusters. 

The containers are (re)created each time the cluster is started and they are destroyed when it is deleted! All persistent data is stored within the root directory (and the mapped devices, if any).

## 5. Inspecting a cluster

All containers of an existing cluster can be listed by executing:

```console
$ ./exadt ps MyCluster
 NODE ID      STATUS          IMAGE                       HOSTNAME   CONTAINER ID   CONTAINER NAME    EXPOSED PORTS       
 11           Up 5 seconds    exasol/docker-db:6.0.0-d1   n11        e9347c3e41ca   MyCluster_11      8898->8888,6593->6583
```

The `EXPOSED PORTS` column shows all container ports that are reachable from outside the local host ('host'->'container'), usually one for the database and one for BucketFS.

## 6. Stopping a cluster

A cluster can be stopped by executing:

```console
$ ./exadt stop-cluster MyCluster
Stopping container 'MyCluster_11'... successful
Removing container 'MyCluster_11'... successful
Removing network 'MyCluster_priv'... successful
```

As stated above, the containers are deleted when a cluster is stopped, but the root directory is preserved (as well as all mapped devices). Also the automatically created networks are removed. 
 
## 7. Updating a cluster

A cluster can be updated by exchanging the EXASOL Docker image:

```console
$ ./exadt update-cluster --image exasol/docker-db:latest MyCluster
Cluster 'MyCluster' has been successfully updated!
- Image :  exasol/docker-db:6.0.beta3 --> exasol/docker-db:6.0.0-d1
- DB    :  6.0.beta3                  --> 6.0.0
- OS    :  6.0.beta3                  --> 6.0.0
Restart the cluster in order to apply the changes.
```

The cluster has to be restarted in order to recreate the containers from the new image (and trigger the internal update mechanism).
 
## 8. Deleting a cluster

A cluster can be completely deleted by executing:

```console
$ ./exadt delete-cluster MyCluster
Do you really want to delete cluster 'MyCluster' (and all file-devices)?  (y/n): y
Deleting directory '/mnt/data/n11'.
Deleting directory '/mnt/data/n11'.
Deleting root directory '/home/user/MyCluster/'.
Successfully removed cluster 'MyCluster'.
```

Note that all file devices (even the mapped ones) and the root directory are deleted. You can use `--keep-root` and `--keep-mapped-devices` in order to prevent this.

A cluster has to be stopped before it can be deleted (even if all containers are down)!
  
# Supported Docker versions

`exadt` and the EXASOL Docker image have been developed and tested with Docker version 1.12.x. It may also work with earlier versions, but that is not guaranteed.

Please see [the Docker installation documentation](https://docs.docker.com/installation/) for details on how to upgrade your Docker daemon.
 
