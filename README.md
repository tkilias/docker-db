# EXASOL Docker version

EXASOL is a high-performance, in-memory, MPP database specifically designed for analytics. 
This repository contains a dockerized version of the EXASOL DB for testing purpose.

###### Please note that this is an open source project which is *not officially supported* by EXASOL. We will try to help you as much as possible, but can't guarantee anything since this is not an official EXASOL product.

Currently supported features:
- create / start / stop a database in a virtual cluster
- use the UDF framework
- expose ports from containers on the local host
- update the virtual cluster
- create backups on archive volumes

# Table of contents
[Requirements](#requirements)

[Using the EXASOL Docker tool (`exadt`)](#using-the-exasol-docker-tool)

[Creating a stand-alone EXASOL container (`docker run`)](#creating-a-stand-alone-exasol-container)

[Creating a multi-host EXASOL cluster (by connecting multiple containers)](#creating-a-multi-host-exasol-cluster)

[Enlarging an EXAStorage device](#enlarging-an-exastorage-device)

[Installing custom JDBC drivers](#installing-custom-jdbc-drivers)

[Installing Oracle drivers](#installing-oracle-drivers)

[Connecting to the database](#connecting-to-the-database)

[Troubleshooting](#troubleshooting)

[Reporting bugs](#reporting-bugs)


# Requirements
 
## Docker

`exadt` and the EXASOL Docker image have been developed and tested with Docker 18.03.1-ce (API 1.37) and Python module `docker` (formerly known as `docker-py`) 3.2.1 on Fedora 27. It may also work with earlier versions, but that is not guaranteed.
 
Please see [the Docker installation documentation](https://docs.docker.com/installation/) for details on how to upgrade your Docker daemon.
 
## Host OS

`exadt` currently only supports Docker on Linux. If you are using a Windows host you'd have to create a Linux VM.

The host OS must support O_DIRECT access for the EXASOL containers, which may not be the case for Docker on Mac (see [Troubleshooting](#troubleshooting)).

## Host environment

If you like to use our `exadt` tool, you'll need to install `git` and `pipenv`. `pipenv` is used to create virtual environments for Python projects (see [https://docs.pipenv.org/](https://docs.pipenv.org/)). Using `pipenv` makes it easy to install the required versions of all `exadt` dependencies without affecting your host environment. You can install `pipenv` using `pip` or your favorite package management system.                 

Each database instance needs **2 GiB RAM**. We recommend that the host reserves at least **4 GiB RAM** for each running EXASOL container.


# Using the EXASOL Docker Tool

The `exadt` command-line tool is used to create, initialize, start, stop, update and delete a Docker based EXASOL cluster.

**NOTE: exadt currently only supports single-host-clusters. See [Creating a multi-host EXASOL cluster](#creating-a-multi-host-exasol-cluster) for how to create a multi-host-cluster (with one container per host).**
 
## 0. Preliminaries

The installation steps below assume that you have `pipenv` installed on your Docker host system.

**NOTE: there are multiple major versions of Exasol in the Github and Docker repositories, therefore it's better to use the desired version nr. instead of the `latest` tag with all `git` and `docker` commands.** 

- Pull the image to your Docker host:
  ```console
  $ docker pull exasol/docker-db:<version>
  ```
- Install `exadt`:
  ```console
  $ git clone https://github.com/EXASOL/docker-db.git <version>
  $ cd docker-db
  ```
- Install the `exadt` dependencies:
  ```console
  $ pipenv install -r exadt_requirements.txt
  ```
- Activate the `pipenv` environment
  ```console
  $ pipenv shell
  ```
- Create and configure your virtual EXASOL cluster by using the commands described in the `exadt` documentation below.

**IMPORTANT** : all `exadt` commands listed below have to be executed within the shell spawned by the `pipenv shell` command! Alternatively, you can use `pipenv run ./exadt`.
 
## 1. Creating a cluster

Select a root directory for your EXASOl cluster. It will be used to store the data, metadata and buckets of all local containers and should therefore be located on a filesystem with sufficient free space (min. 10 GiB are recommended).

**NOTE: this example creates only one node. You can easily create mutliple (virtual) nodes by using the --num-nodes option.**

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
$ ./exadt init-cluster --image exasol/docker-db:<version> --license ./license/license.xml --auto-storage MyCluster
Successfully initialized configuration in '/home/user/MyCluster/EXAConf'.
Successfully initialized root directory '/home/user/MyCluster/'.
```

This command creates subdirectories for each virtual node in the root directory. These are mounted as Docker volumes within each container (at '/exa') and contain all data, metadata and buckets.

It also creates the file `EXAConf` in the root directory, which contains the configuration for the whole cluster and currently has to be edited manually if a non-default setup is used.

### Automatically creating and assigning file devices

The example above uses the `--auto-storage` option which tells `exadt` to automatically create file-devices for all virtual nodes (within the root directory). These devices are assigned to the EXAStorage volumes, that are also automatically created. The devices need at least 10GiB of free space and use up to 100GiB of it (all devices combined). 

If `--auto-storage` is used, you can skip the next step entirely (and *continue with section 4*).

## 3. Adding EXAStorage devices

**NOTE:  This step can be skipped if `--auto-storage` has been used during initialization.**

Next, devices for EXAStorage need to be added. This can be done by executing:

```console
$ ./exadt create-file-devices --size 80GiB MyCluster
Successfully created the following file devices:
Node 11 : ['/home/user/MyCluster/n11/data/storage/dev.1']
```

As you can see, the file devices are created within the `data/storage` subdirectory of each node's Docker root. They are created as *sparse files*, i. e. their size is stated as the given size but they actually have size 0 and grow as new data is being written.

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
 NODE ID      STATUS          IMAGE                       NAME   CONTAINER ID   CONTAINER NAME    EXPOSED PORTS       
 11           Up 5 seconds    exasol/docker-db:6.0.0-d1   n11    e9347c3e41ca   MyCluster_11      8899->8888,6594->6583
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

A cluster can be updated by exchanging the EXASOL Docker image (but it has to be stopped first):

```console
$ git pull
$ docker pull exasol/docker-db:<version>
$ pipenv install -r exadt_requirements.txt
$ ./exadt update-cluster --image exasol/docker-db:<version> MyCluster
Cluster 'MyCluster' has been successfully updated!
- Image :  exasol/docker-db:6.0.0-d1 --> exasol/docker-db:6.0.0-d2
- DB    :  6.0.0                     --> 6.0.1
- OS    :  6.0.0                     --> 6.0.0
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


# Creating a stand-alone EXASOL container

Starting with version 6.0.2-d1, there is no more separate "self-contained" image version. You can simply create an EXASOL container from the EXASOL docker image using the following command:

```console
$ docker run --name exasoldb -p 127.0.0.1:8899:8888 --detach --privileged --stop-timeout 120  exasol/docker-db:<version>
```

In this example port 8888 (within the container) is exposed on the local port 8899. Use this port to connect to the DB.

All data is stored within the container and lost when the container is removed. In order to make it persistent, you'd have to mount a volume into the container at `/exa`, for example:

```console
$ docker run --name exasoldb  -p 127.0.0.1:8899:8888 --detach --privileged --stop-timeout 120 -v exa_volume:/exa exasol/docker-db:<version>
```

See [the Docker volumes documentation](https://docs.docker.com/engine/tutorials/dockervolumes/) for more examples on how to create and manage persistent volumes.

**NOTE: Make sure the database has been shut down correctly before stopping the container!**

A high stop-timeout (see example above) increases the chance that the DB can be shut down gracefully before the container is stopped, but it's not guaranteed. However, it can be stopped manually by executing the following command within the container (after attaching to it):

```console
$ dwad_client stop-wait DB1
```

Or from outside the container:

```console
$ docker exec -ti exasoldb dwad_client stop-wait DB1
```

## Updating the persistent volume of a stand-alone EXASOL container

Starting with version 6.0.3-d1, an existing persistent volume can be updated (for use with a later version of an EXASOL image) by calling the following command with the *new* image:

```console
$ docker run --rm -v exa_volume:/exa exasol/docker-db:6.0.3-d1 update-sc
```

If everything works correctly, you should see output similar to this:

```console
Updating EXAConf '/exa/etc/EXAConf' from version '6.0.2' to '6.0.3'
Container has been successfully updated!
- Image ver. :  6.0.2-d1 --> 6.0.3-d1
- DB ver.    :  6.0.2 --> 6.0.3
- OS ver.    :  6.0.2 --> 6.0.3
```

After that, a new container can be created (from the new image) using the old / updated volume.


# Creating a multi-host EXASOL cluster

Starting with version 6.0.7-d1, it's possible to create multiple containers on different hosts and connect them to a cluster (one container per host). 

## 1. Create the configuration 

First you have to create the configuration for the cluster. There are two possible ways to do so:
 
### a. Create an /exa/ directory template (RECOMMENDED):

Execute the following command (`--num-nodes` is the number of containers in the cluster):

```console
$ docker run -v $HOME/exa_template:/exa --rm -i exasol/docker-db:<version> init-sc --template --num-nodes 3
```

After the command has finished, the directory `$HOME/exa_template` contains all subdirectories as well as an EXAConf template (in `/etc`). The EXAConf is also printed to stdout.

**NOTE: you man need to add `--privileged` if the host directory belongs to root.
 
### b. Create an EXAConf template

You can create a template file and redirect it to wherever you want by executing: 

```console
$ docker run --rm -i exasol/docker-db:<version> init-sc --template --num-nodes 3 > ~/MyExaConf
```

**NOTE: we recommend to create an /exa/ template directory and the following steps assume that you did so. If you choose to only create the EXAConf file, you have to build a new Docker image with it and create the EXAStorage devices files within that image.**

## 2. Complete the configuration

The EXAConf template has to be completed before the cluster can be started. You have to provide:

#### The private network of all nodes:
```console
[Node : 11]
    PrivateNet = 10.10.10.11/24 # <-- replace with the real network
```

#### The EXAStorage devices on all nodes:
```console
[[Disk : default]]
        Devices = dev.1    #'dev.1' must be located in '/exa/data/storage'
```

**NOTE: You can leave this entry as it is if you create the devices as described below.**

#### The EXAVolume sizes:
```console
[EXAVolume : DataVolume1]
    Type = data
    Nodes = 11, 12, 13
    Disk = default
    # Volume size (e. g. '1 TiB')
    Size =  # <-- enter volume size here
```
  
#### The network port numbers (optional)

If you are using the host network mode (see "Start the cluster" below), you may have to adjust the port numbers used by the EXASOL services. The one that's most likely to collide is the SSH daemon, which is using the well-known port 22. You can change it in EXAConf:
```console
[Global]
    SSHPort = 22  # <-- replace with any unused port number
```

The other EXASOL services (e. g. Cored, BucketFS and the DB itself) are using port numbers above 1024. However, you can change them all by editing EXAConf.
 
#### The nameservers (optional):
```console
[Global]
    ...
    # Comma-separated list of nameservers for this cluster.
    NameServers =
```
 
## 3. Copy the configuration to all nodes

Copy the `$HOME/exa_template/` directory to all cluster nodes (the exact path is not relevant, but should be identical on all nodes).

## 4. Create the EXAStorage device files

You can create the EXAStorage device files by executing (on each node):

```console
$ truncate -s 1G $HOME/exa_template/data/storage/dev.1
```
or (alternatively):
```console
$ dd if=/dev/zero of=$HOME/exa_template/data/storage/dev.1 bs=1M count=1 seek=999
```

This will create a sparse file of 1GB (1000 blocks of 1 MB) that holds the data. Adjust the size of the data file to your needs. Repeat this step to create multiple file devices.

**NOTE: Alternatively you can use an existing block-device by creating a special device file with the corresponding major and minor number (using `mknod`) named `dev.1` in the same directory.**

**NOTE: The data file (or device) should be slightly bigger (~1%) than the required space for the volume, because a part of it will be reserved for metadata and checksums.**
 
## 5. Start the cluster

The cluster is started by creating all containers individually and passing each of them its ID from the EXAConf. For `n11` the command would be:

```console
$ docker run --detach --network=host --privileged -v $HOME/exa_template:/exa exasol/docker-db:<version> init-sc --node-id 11
```

**NOTE: this example uses the host network stack, i. e. the containers are directly accessing a host interface to connect to each other. There is no need to expose ports in this mode: they are all accessible on the host.**

# Enlarging an EXAStorage device

If you need to enlarge the device file of an existing EXASOL container, you can use the following commands to do so:

### 1. Open a terminal in the container:

$ docker exec -ti <containername> /bin/bash

### 2. Enlarge the device file physically (e. g. by 10GB):

$ truncate --size=+10GB /exa/data/storage/dev.1.data

**NOTE: the path may also be `/exa/data/storage/dev.1` (i. e. without the `data` suffix) in versions > 6.0.12**

### 3. Enlarge the device logically (i. e. tell EXAStorage about the new size):

$ cshdd --enlarge -n 11 -h /exa/data/storage/dev.1[.data]

**NOTE: `-n` is the node ID**

### 4. Repeat these steps for all devices and containers

# Installing custom JDBC drivers

Starting with version 6.0.7-d1, custom JDBC drivers can be added by uploading them into a bucket. The bucket and path for the drivers can be configured in each database section of EXAConf. The default configuration is:

```console
[DB : DB1]
    ...
    # OPTIONAL: JDBC driver configuration
    [[JDBC]]
        BucketFS = bfsdefault
        Bucket = default
        # Directory within the bucket that contains the drivers
        Dir = drivers/jdbc
```

In order for the database to find the driver, you need to upload it into a subdirectory of `drivers/jdbc` of the default bucket (which is automatically created if you don't modify EXAConf). See the section `Installing Oracle drivers` for help on how to upload files to BucketFS.

In addition to the driver file(s), you also have to create and upload a file called `settings.cfg` , that looks like this:

```console
DRIVERNAME=MY_JDBC_DRIVER
JAR=my_jdbc_driver.jar
DRIVERMAIN=com.mydriver.jdbc.Driver
PREFIX=jdbc:mydriver:
FETCHSIZE=100000
INSERTSIZE=-1
```

Change the variables DRIVERNAME, JAR, DRIVERMAIN and PREFIX according to your driver and upload the file (into the **same directory** as the driver itself).

**IMPORTANT: Do not modify the last two lines!**

If you use the default bucket and the default path, you can add multiple JDBC drivers during runtime. The DB will find them without having to restart it (as long as they're located in a subfolder of the default path). Otherwise, a container restart is required. 
 

# Installing Oracle drivers

Starting with version 6.0.7-d1, Oracle drivers can be added by uploading them into a bucket. The bucket and path for the drivers can be configured in each database section of EXAConf. The default configuration is:

```console
[DB : DB1]
    ...
    # OPTIONAL: Oracle driver configuration
    [[ORACLE]]
        BucketFS = bfsdefault
        Bucket = default
        # Directory within the bucket that contains the drivers
        Dir = drivers/oracle
```

In order for the database to find the driver, you have to upload it to `drivers/oracle` of the default bucket (which is automatically created if you don't modify EXAConf).

You can use `curl` for uploading, e. g.:

```
$ curl -v -X PUT -T instantclient-basic-linux.x64-12.1.0.2.0.zip http://w:PASSWORD@10.10.10.11:6583/default/drivers/oracle/instantclient-basic-linux.x64-12.1.0.2.0.zip
```

Replace `PASSWORD` with the `WritePasswd` for the bucket. You can find it in the EXAConf. It's base64 encoded and can be decoded like this:

```
$ awk '/WritePasswd/{ print $3; }' EXAConf | base64 -d
```

**NOTE: The only currently supported driver version is 12.1.0.2.0. Please download the package `instantclient-basic-linux.x64-12.1.0.2.0.zip` from oracle.com and upload it as described above.**
 
# Connecting to the database

Connecting to the default Exasol DB inside a Docker container is not different from the "normal" version. You can use any supported client and authenticate with username `sys` and password `exasol`. 

Please refer to the [offical manual](https://www.exasol.com/portal/display/DOC/Database+User+Manual) for further information.

# Troubleshooting

### Error after modifying EXAConf

> ERROR::EXAConf: Integrity check failed! The stored checksum 'a2f605126a2ca6052b5477619975664f' does not match the actual checksum 'f9b9df0b9247b4696135c135ea066580'. Set checksum to 'COMMIT' if you made intentional changes.

If you see a message similar to the one above, you probably modified an EXAConf that has already been used by an EXASOL container or `exadt`. It is issued by the EXAConf integrity check (introduced in version 6.0.7-d1) that protects EXAConf from accidental changes and detects file corruption.

In order to solve the problem you have to set the checksum within EXAConf to 'COMMIT'. It can be found in the 'Global' section, near the top of the file:

```console
[Global]
...
Checksum = COMMIT
...
```
### Error during container start because of missing O_DIRECT support

> WORKER::ERROR: Failed to open device '/exa/data/storage/dev.1.data'!
> WORKER:: errno = Invalid argument

If the container does not start up properly and you see an error like this in the logfiles below `/exa/logs/cored/`, your filesystem probably does not support `O_DIRECT ` I/O mode. This is the case with Docker for Mac.

We strongly recommend to use only Linux for the EXASOL Docker image. If you are already using Linux, but can't enable O_DIRECT for specific reasons, you can disable O_DIRECT mode by adding a line to each disk in EXAConf:

```console
[Node : 11]
    ...
    [[Disk : default]]
        DirectIO = False
```

**This feature is experimental and may cause significantly higher memory usage and fluctuating I/O throughput!**

### Error when starting the database

> Could not start database: system does not have enough active nodes or DWAd was not able to create startup parameters for system

If all containers started successfully but the database did not and you see a message similar to this in the output of `docker logs`, you may not have enough memory in your host(s). The DB needs at least 2 GiB RAM per node (that's also the default value in EXAConf).


# Reporting bugs

Please read the [Contribution guidelines for this project](CONTRIBUTING.md) before submitting a bug report or pull request!
