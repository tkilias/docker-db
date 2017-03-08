# What is EXASOL?          

EXASOL is the intelligent, high-performance in-memory analytic database that just works.

# How to use this image

- Pull the image to your local docker installation

```console
$ TODO 
```

- Install the `exadt` command-line tool (and all dependencies)

```console
$ TODO
```

- Create and configure your virtual EXASOL cluster.

# exadt

The `exadt` command-line tool is used to create, initialize, start, stop and delete a Docker based EXASOL cluster.

## Creating a cluster

You first have to select a root directory for your EXASOl cluster. It will be used to store the data, metadata and buckets of all local containers and should therefore be located on a filesystem with sufficient free space.

```console
$ exadt create-cluster --root ~/MyCluster/ --create-root MyCluster
Successfully created cluster 'MyCluster' with root directory '/home/user/MyCluster/'.
```

`exadt` stores information about all clusters within `$HOME/.exadt.conf` and `/etc/exadt.conf` (only if the current user has write permission in `/etc`). Both files are searched when executing any other cluster related command.

In order to list all existing clusters you can use `exadt list-clusters`:

```console
$ exadt list-clusters
 CLUSTER                     ROOT                                       IMAGE                    
 MyCluster                   /home/user/MyCluster                       exabase:6.0.beta3
```

## Initializing a cluster

After creating a cluster it has to be initialized. Mandatory parameters are:

- the docker image to be used for the containers
- the nr. of virtual nodes (i. e. containers) on the local host
- the type of EXAStorage devices (currently only 'file' is supported)
- the license file

```console
$ exadt init-cluster --image exabase:6.0.beta3 --num-nodes 2 --device-type file --license /home/user/my_license MyCluster
Successfully initialized configuration in '/home/user/MyCluster/EXAConf'.
Successfully initialized root directory '/home/user/MyCluster/'.
```

This command creates subdirectories for each virtual node in the root directory. These are mounted as docker volumes within each container (at `/exa') and contain all data, metadata and buckets.

It also creates the EXAConf file in the root directory. This file describes the whole cluster and currently has to be edited manually if a non-default setup is used.

## Adding EXAStorage devices

Next, we need to add devices to be used by EXAstorage. This can be done by executing:

```console
$ exadt create-file-devices --num 2 --size 20GiB MyCluster
Successfully created the following file devices:
Node 10 : ['/home/user/MyCluster/n10/data/storage/dev.1', '/home/user/MyCluster/n10/data/storage/dev.2']
Node 11 : ['/home/user/MyCluster/n11/data/storage/dev.1', '/home/user/MyCluster/n11/data/storage/dev.2']
```

This command creates two devices per container, but a single device is sufficient. As you can see, the file devices are created within the `data/storage` subdirectory of each node's docker root. They are created as *sparse files*, i. e. their size is stated as the given size but they actually have size 0 and grow as new data is being written.

## Starting a cluster

The cluster is started using the `exadt start-cluster` command. Before the containers are actually created, `exadt` checks if there is enough free space for the sparse files (if they grow to their max. size). If not, the startup will fail:

```console
$ exadt start-cluster MyCluster
Free space on '/' is only 22.2 GiB, but accumulated size of (sparse) file-devices is 80.0 GiB!
'ERROR::DockerHandler: Check for space usage failed! Aborting startup.'
```

If that's the case, you can replace the existing devices with smaller ones and (optionally) place them on an external partition:

```console
$  exadt create-file-devices --num 2 --size 5GiB MyCluster --replace --path /mnt/data/
Do you really want to replace all file-devices of cluster 'MyCluster'? (y/n): y
The following file devices have been removed:
Node 10 : ['/home/user/MyCluster/n10/data/storage/dev.1', '/home/user/MyCluster/n10/data/storage/dev.2']
Node 11 : ['/home/user/MyCluster/n11/data/storage/dev.1', '/home/user/MyCluster/n11/data/storage/dev.2']
Successfully created the following file devices:
Node 10 : ['/mnt/data/n10/dev.1', '/mnt/data/n10/dev.2']
Node 11 : ['/mnt/data/n11/dev.1', '/mnt/data/n11/dev.2']
```

The devices that are located outside of the root directory are mapped into the file system of the container (within `/exa/data/storage/`). They are often referenced as 'mapped devices'.

Now the cluster can be started:

```console
$ exadt start-cluster MyCluster
Copying EXAConf to all node volumes.
Creating private network 10.10.10.0/24 ('MyCluster_priv')... successful
No public network specified.
Creating container 'MyCluster_10'... successful
Creating container 'MyCluster_11'... successful
Starting container 'MyCluster_10'... successful
Starting container 'MyCluster_11'... successful
```

This command creates and starts all containers and networks. Each cluster uses one or two networks to connect the containers. These networks are not connected to other clusters. 

The containers are created every time the cluster is started and they are destroyed when it is deleted! All persistent data is stored within the root directory (and the mapped devices, if specified).

## Inspecting a cluster

You can list all containers of an existing cluster by executing:

```console
$ exadt ps MyCluster
 NODE ID      STATUS                          IMAGE                       HOSTNAME          CONTAINER ID   CONTAINER NAME         EXPOSED PORTS       
 11           Up 4 seconds                    exabase:6.0.beta3           n11               df1996713bc1   MyCluster_11           8899->8888,6594->6583
 10           Up 5 seconds                    exabase:6.0.beta3           n10               e9347c3e41ca   MyCluster_10           8898->8888,6593->6583
```

## Stopping a cluster

A cluster can be stopped by executing:

```console
$ exadt stop-cluster MyCluster
Stopping container 'MyCluster_11'... successful
Stopping container 'MyCluster_10'... successful
Removing container 'MyCluster_11'... successful
Removing container 'MyCluster_10'... successful
Removing network 'MyCluster_priv'... successful
```

As stated above, the containers are deleted when a cluster is stopped, but the root directory is preserved (as well as all mapped devices). Also the automatically created networks are removed. 

## Deleting a cluster

A cluster can be completely deleted by executing:

```console
$ exadt delete-cluster MyCluster
Do you really want to delete cluster 'MyCluster' (and all file-devices)?  (y/n): y
Deleting directory '/mnt/data/n10'.
Deleting directory '/mnt/data/n10'.
Deleting directory '/mnt/data/n11'.
Deleting directory '/mnt/data/n11'.
Deleting root directory '/home/user/MyCluster/'.
Successfully removed cluster 'MyCluster'.
```

Note that all file devices (even the mapped ones) and the root directory are deleted. You can use `--keep-root` and `--keep-mapped-devices` in order to prevent this.

A cluster has to be stopped before it can be deleted (even if all containers are down).
  
# Supported Docker versions

This image is developed and tested with Docker version 1.12.x. It may also work with earlier versions, but that is not guaranteed.

Please see [the Docker installation documentation](https://docs.docker.com/installation/) for details on how to upgrade your Docker daemon.
