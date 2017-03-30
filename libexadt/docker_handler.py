import os,docker,EXAConf,pprint,shutil,device_handler
from docker.utils import kwargs_from_env

ip_types = { 4: 'ipv4_address', 6: 'ipv6_address' }
 
#{{{ Class DockerError
class DockerError(Exception):
    def __init__(self, msg):
        self.msg = "ERROR::DockerHandler: " + msg
    def __str__(self):
        return repr(self.msg)
#}}}
 
class docker_handler:
    """ Implements all docker commands. Depends on the 'docker' python module (https://github.com/docker/docker-py). """

#{{{ Init
    def __init__(self, verbose=False):
        """
        Creates a new docker_handler and a docker.APIClient (used for communication with the docker service).
        """
        self.client = docker.APIClient(timeout=20, **kwargs_from_env())
        self.verbose = verbose
        self.def_container_cmd = None 
#}}}

#{{{ Set EXAConf object for this instace of docker-handler
    def set_exaconf(self, exaconf):
        """
        Set EXAConf instance for this docker_handler instance.
        """
        self.exaconf = exaconf
        self.cluster_name = self.exaconf.get_cluster_name()
        self.image = self.exaconf.get_docker_image()
        self.def_container_cmd = os.path.join(self.exaconf.os_dir, "libexec/exainit.py")
#}}}

#{{{ Docker version (debug)
    def version(self):
        """
        Returns information about the docker version on the current node.
        """
        try:
            res = self.client.version()
        except docker.errors.APIError as e:
            raise DockerError("Failed to query docker version: %s" % (self.cluster_name, e))
        return res
#}}}

#{{{ Create networks
    def create_networks(self):
        """ 
        Creates private and public docker networks.
        """

        created_networks = []
        # private network
        have_priv_net = self.exaconf.has_priv_net()
        if have_priv_net:
            priv_net_name = self.exaconf.get_priv_net_name()
            try:
                priv_net = self.exaconf.get_priv_net()
            except EXAConf.EXAConfError as e:
                raise DockerError("Failed to read EXAConf: %s" % e)
            # create private network
            print "Creating private network %s ('%s')..." % (priv_net, priv_net_name),
            ipam_pool = docker.types.IPAMPool(subnet = priv_net)
            ipam_config = docker.types.IPAMConfig(pool_configs = [ipam_pool])
            try:
                net = self.client.create_network(priv_net_name, driver="bridge", ipam=ipam_config,
                                                 labels={"ClusterName":self.cluster_name,"Scope":"private"})
                # add name and type (for usage by create_containers())
                net['MyName'] = priv_net_name
                net['MyScope'] = 'private'
                created_networks.append(net)
                print "successful"
                if self.verbose:
                    print "Created the following network:"
                    pprint.pprint(net)
            except docker.errors.APIError as e:
                raise DockerError("Failed to create network: %s." % e)
        else:
            print "No private network specified"
   
        # public network
        have_pub_net = self.exaconf.has_pub_net()
        if have_pub_net:
            pub_net_name = self.exaconf.get_pub_net_name()
            try:
                pub_net = self.exaconf.get_pub_net()
            except EXAConf.EXAConfError as e:
                raise DockerError("Failed to read EXAConf: %s" % e)
            # create public network (if any)
            print "Creating public network %s ('%s')..." % (pub_net, pub_net_name),
            ipam_pool = docker.types.IPAMPool(subnet = pub_net)
            ipam_config = docker.types.IPAMConfig(pool_configs = [ipam_pool])
            try:
                net = self.client.create_network(pub_net_name, driver="bridge", ipam=ipam_config,
                                                 labels={"ClusterName":self.cluster_name, "Scope":"public"})
                # add name and type (for usage by create_containers())
                net['MyName'] = pub_net_name
                net['MyScope'] = 'public'
                created_networks.append(net)
                print "successful"
                if self.verbose:
                    print "Created the following network:"
                    pprint.pprint(net)
            except docker.errors.APIError as e:
                raise DockerError("Failed to create network: %s." % e)
        else:
            print "No public network specified."

        return created_networks
#}}}

#{{{ Delete networks            
    def delete_networks(self):
        """  
        Deletes private and public docker networks.
        """

        networks = []
        # get network names
        priv_net_name = self.exaconf.get_priv_net_name()
        pub_net_name = self.exaconf.get_pub_net_name()

        if pub_net_name and pub_net_name != "":
            networks.append(pub_net_name)
        if priv_net_name and priv_net_name != "":
            networks.append(priv_net_name)

        try:
            nets = self.client.networks(names=networks)
        except docker.errors.APIError as e:
            raise DockerError("Failed to query networks: %s." % e)
        if len(nets) == 0:
            print "No networks found for cluster '%s'." % self.cluster_name
        else:
            for net in nets:
                if self.verbose:
                    print "Going to remove the following network:"
                    pprint.pprint(net)
                try:
                    print "Removing network '%s'..." % net['Name'],
                    self.client.remove_network(net['Id'])
                    print "successful"
                except docker.errors.APIError as e:
                    print "Failed to remove network '%s' : %s" % (net['Name'], e)
#}}}
 
#{{{ Container name
    def container_name(self, container):
        """
        Extracts the name of a container.
        """
        return container['Names'][0].lstrip("/")
#}}}

#{{{ Get all containers
    def get_all_containers(self):
        """ 
        Returns a list of all containers of the current cluster (no matter what their status is). 
        They are identified using the 'ClusterName' label.
        """

        try:
            my_containers = self.client.containers(all=True, filters = {'label':'ClusterName=' + self.cluster_name})
        except docker.errors.APIError as e:
            raise DockerError("Failed to query containers for cluster '%s': %s" % (self.cluster_name, e))
        return my_containers
#}}}
 
#{{{ Get image conf
    def get_image_conf(self, image_name):
        """
        Returns a config containing information about the given image (e. g. all labels).
        """

        image_conf = EXAConf.config()
        try:
            image = self.client.inspect_image(image_name)
        except docker.errors.APIError as e:
            raise DockerError("Failed to query information about image '%s': %s" % (image_name, e))
        # add labels
        image_conf['labels'] =  EXAConf.config()
        for item in image['ContainerConfig']['Labels'].iteritems():
            image_conf['labels'][item[0]] = item[1]
        return image_conf
#}}}

#{{{ Create containers
    def create_containers(self, networks, cmd=None):
        """ 
        Creates one container per node. Takes care of volumes, block-devices, environment, labels
        and additional container configuration.
        
        Returns a list of created containers.
        """

        created_containers = []
        try:
            nodes_conf = self.exaconf.get_nodes_conf()
            if self.verbose:
                print "Found the following node configurations:"
                pprint.pprint(nodes_conf)
            docker_conf = self.exaconf.get_docker_conf()
            if self.verbose:
                print "Found the following docker config:"
                pprint.pprint(docker_conf)
            bucketfs_conf = self.exaconf.get_bucketfs_conf()
            if self.verbose:
                print "Found the following BucketFS config:"
                pprint.pprint(bucketfs_conf)
        except EXAConf.EXAConfError as e:
            raise DockerError("Failed to read EXAConf: %s" % e)

        if self.verbose:
            print "Using image '%s' and cluster name '%s'" % (self.image, self.cluster_name)

        # separate  the first network from the remaing ones, so it can be given to
        # the container at creation time (necessary to avoid that the container 
        # is attached to the default network)
        first_net = networks.pop(0)
        for node_id in nodes_conf.keys():
            container_name = self.cluster_name + "_" + str(node_id)
            my_conf = nodes_conf[node_id]
            devices = []

            # 1.) configure devices, volumes, first network and host-options
            # a. default node volumes
            binds = [my_conf.docker_volume + ":" + self.exaconf.container_root + ":rw"]
            volumes = [self.exaconf.container_root]
            # b. mapped file-devices
            # --> each file-device needs to be mounted into the storage-directory within the container
            if docker_conf.device_type == 'file':
                for disk in my_conf.disks.itervalues():
                    if disk.has_key("mapped_devices"):
                        for dev_host, dev_container in disk.mapped_devices:
                            binds.append(dev_host + ":" + dev_container + ":rw")
                            volumes.append(dev_container)
            # c. block devices
            # --> only takes effect if "privileged == False" (otherwise all devices are accessible anyway)
            elif docker_conf.device_type == 'block':
                for disk in my_conf.disks.itervalues():
                    for dev, meta in disk.devices:
                        # FIXME : use mapping if given
                        dev_host = os.path.join(os.path.join(my_conf.docker_volume, self.exaconf.storage_dir), dev)
                        dev_container = os.path.join(os.path.join(self.exaconf.container_root, self.exaconf.storage_dir), dev)
                        meta_host = os.path.join(os.path.join(my_conf.docker_volume, self.exaconf.storage_dir), meta)
                        meta_container = os.path.join(os.path.join(self.exaconf.container_root, self.exaconf.storage_dir), meta)
                        devices.append(dev_host+":"+dev_container+":rwm")
                        devices.append(meta_host+":"+meta_container+":rwm")
            # d. BucketFS volumes
            for bfs_name in bucketfs_conf.fs.keys():
                bfs_conf = bucketfs_conf.fs[bfs_name]
                if bfs_conf.has_key("path") and bfs_conf.path != "":
                    bfs_host = os.path.join(bfs_conf.path, my_conf.hostname, bfs_name)
                    bfs_container = os.path.join(self.exaconf.container_root, self.exaconf.bucketfs_dir, bfs_name)
                    binds.append(bfs_host + ":" + bfs_container + ":rw")
                    volumes.append(bfs_container)

            # port bindings
            port_binds = {}
            if my_conf.has_key("exposed_ports"):
                port_binds = dict(my_conf.exposed_ports)
            # create host config
            hc = self.client.create_host_config(privileged = True,
                                                binds = binds,
                                                devices = devices,
                                                port_bindings = port_binds)
            # create config for the first network (see above)
            ip = ""
            if first_net['MyScope'] == 'private':
                ip = my_conf.private_ip
            elif first_net['MyScope'] == 'public':
                ip = my_conf.public_ip
            ep_conf = self.client.create_endpoint_config(**{ip_types[self.exaconf.ip_type(ip)]: ip}) 
            net_conf = self.client.create_networking_config({first_net['MyName']: ep_conf})

            # 2.) create container
            if cmd and cmd != "":
                print "Creating container '%s' with custom command '%s'..." % (container_name, cmd),
            else:
                cmd = self.def_container_cmd
                print "Creating container '%s'..." % container_name,
            try:
                container = self.client.create_container(self.image,
                                                         hostname = my_conf.hostname,
                                                         detach = True,
                                                         stdin_open = True,
                                                         tty = True,
                                                         name = container_name,
                                                         labels = {'ClusterName' : self.cluster_name,
                                                                   'NodeID' : node_id,
                                                                   'Hostname' : my_conf.hostname},
                                                         environment = {'EXA_NODE_ID' : node_id},
                                                         volumes = volumes,
                                                         host_config = hc,
                                                         networking_config = net_conf,
                                                         ports = port_binds.keys(),
                                                         command = cmd)
                created_containers.append(container)
                # add name (not part of the returned dict)
                container['MyName'] = container_name
                print "successful"
                if self.verbose:
                    print "Created the following container:"
                    pprint.pprint(container)
            except docker.errors.ImageNotFound as e:
                raise DockerError("Image '%s' not found: %s" % (self.image, e))
            except docker.errors.APIError as e:
                raise DockerError("Failed to create container: %s" % e)

            # 3.) attach container to the remaining network(s)
            for net in networks:
                ip = ""
                if net['MyScope'] == 'private':
                    ip = my_conf.private_ip
                elif net['MyScope'] == 'public':
                    ip = my_conf.public_ip
                print "Connecting container '%s' to network '%s' with IP '%s'..." % (container['MyName'], net['MyName'], ip),
                try:
                    self.client.connect_container_to_network(container = container['Id'],
                                                             net_id = net['Id'],
                                                             **{ip_types[self.exaconf.ip_type(ip)]: ip})
                    print "successful"
                except docker.errors.APIError as e:
                    raise DockerError("Failed to connect network: %s" % e)

        return created_containers  
#}}}

#{{{ Start containers
    def start_containers(self, containers):
        """ 
        Starts all given containers.
        """

        started_containers = []

        for container in containers:
            if self.verbose:
                print "Going to start the following container:"
                pprint.pprint(container)
            try:
                print "Starting container '%s'..." % container['MyName'],
                self.client.start(container=container['Id'])
                started_containers.append(container)
                print "successful"
            except docker.errors.APIError as e:
                raise DockerError("Failed to start container: %s" % e)
        return started_containers
#}}}

#{{{ Stop containers
    def stop_containers(self, timeout):
        """ 
        Stops all running containers from the current cluster. If they don't terminate within the given timeout, 
        they are killed.
        """

        containers = self.get_all_containers()
        if len(containers) == 0:
            print "No containers found for cluster '%s'." % self.cluster_name
            return False

        # stop them
        num_running = 0
        num_stopped = 0
        err = False
        for container in containers:
            if self.verbose:
                print "Found the following container:"
                pprint.pprint(container)
            state = container['State']
            if state == 'running' or state == 'paused' or state == 'restarting':
                num_running += 1
                try:
                    print "Stopping container '%s'..." % self.container_name(container),
                    self.client.stop(container['Id'], int(timeout))
                    num_stopped += 1
                    print "successful"
                except docker.errors.APIError as e:
                    print "Failed to stop container '%s': %s" % (self.container_name(container), e)
                    err = True
            else:
                num_stopped += 1

        if num_running == 0:
            print "No running containers found for cluster '%s'." % self.cluster_name
        elif self.verbose and not err:
            print "Successfully stopped %i containers." % num_running

        return num_stopped > 0
#}}}

#{{{ Remove containers
    def remove_containers(self):
        """ 
        Removes all exited containers (they have to be stopped before calling this function).
        """

        containers = self.get_all_containers()
        if len(containers) == 0:
            print "No containers found for cluster '%s'." % self.cluster_name
            return False

        for container in containers:
            state = container['State']
            if state == 'exited' or state == 'created':
                print "Removing container '%s'..." % self.container_name(container),
                try:
                    self.client.remove_container(container['Id'])
                    print "successful"
                except docker.errors.APIError as e:
                    print "Failed to remove container '%s': %s" % (self.container_name(container), e)

        return True
#}}}
 
#{{{ Cluster started
    def cluster_started(self):
        """ 
        Checks if containers of this cluster exist, i. e. the cluster has been started 
        and not stopped (there may be crashed containers, though).
        """

        containers = self.get_all_containers()
        if containers and len(containers) > 0:
            return True
        else:
            return False
#}}}
 
#{{{ Start cluster
    def start_cluster(self, cmd=None):
        """
        Starts the given cluster by:
            - checking the available free space (in case of file-devices)
            - copying EXAConf to the docker-volume of all nodes (into 'etc/')
            - creating docker networks
            - creating docker containers for all cluster-nodes
            - starting docker containers
        """
        if self.cluster_started():
            raise DockerError("Cluster '%s' has already been started! Use 'stop-cluster' if you want to stop it." % self.cluster_name)
        # 1. check free space in case of file-devices
        if self.exaconf.get_docker_device_type() == "file":
            dh = device_handler.device_handler(self.exaconf)
            if dh.check_free_space() == False:
                raise DockerError("Check for space usage failed! Aborting startup.")
        # 2. copy EXAConf to all node volumes
        conf_path = self.exaconf.get_conf_path()
        node_volumes = self.exaconf.get_docker_node_volumes()
        print "Copying EXAConf to all node volumes."
        for n,volume in node_volumes.iteritems():
            shutil.copy(conf_path, os.path.join(volume, "etc"))
        # 3. create networks
        try:
            networks = self.create_networks()
        except DockerError as e:
            print "Error during startup! Cleaning up..."
            self.stop_cluster(30)   
            raise e
        # 4. create containers
        try:
            containers = self.create_containers(networks, cmd=cmd)
        except DockerError as e:
            print "Error during startup! Cleaning up..."
            self.stop_cluster(30)            
            raise e
        # 5. start containers
        try:
            self.start_containers(containers)
        except DockerError as e:
            print "Error during startup! Cleaning up..."
            self.stop_cluster(30)            
            raise e
#}}}

#{{{ Stop cluster
    def stop_cluster(self, timeout):
        """
        Stops the given cluster by:
            - stopping all running docker containers
            - removing all stopped docker containers
            - removing all docker networks
        """
        if self.stop_containers(timeout):
            self.remove_containers()
        self.delete_networks()
#}}}
