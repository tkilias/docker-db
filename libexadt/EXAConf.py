import os, stat, ipaddr, configobj
from utils import units2bytes, bytes2units, gen_base64_passwd
from collections import OrderedDict as odict

#{{{ Class EXAConfError
class EXAConfError(Exception):
    """
    The EXAConf exception class.
    """
    def __init__(self, msg):
        self.msg = "ERROR::EXAConf: " + msg
    def __str__(self):
        return repr(self.msg)
#}}}

#{{{ Class config
class config(odict):
    __enabled = False
    def __init__(self, *args, **kw):
        odict.__init__(self, *args, **kw)
        self.__enabled = True
    def __repr__(self):
        return "<%s at %s: %s>" % (self.__class__.__name__, hex(id(self)), repr(self.items()))
    def __getattr__(self, name):
        if not self.__enabled:
            return self.__getattribute__(name)
        return self.__getitem__(name)
    def __setattr__(self, name, value):
        if not self.__enabled:
            self.__dict__[name] = value
        else: self.__setitem__(name, value)    
#}}}                   

class EXAConf:
    """ 
    Read, write and modify the EXAConf file. 
    
    This class depends on the 'configobj' module (https://configobj.readthedocs.io, https://github.com/DiffSK/configobj)
    """

#{{{ Init
    def __init__(self, root, initialized):
        """ 
        Creates a new EXAConf instance from the file 'EXAConf' within the given 
        root directory. If 'initialized' is true, the content of 'EXAConf'
        will be validated.
        """

        # Version numbers of the current cluster
        # NOTE : the version numbers are somewhat special. The COS
        # and DB version are overwritten by the ones in the EXAConf file
        # (present after initialization). The DB version may also be
        # overwritten during initialization (if provided on the CLI
        # or taken from the Docker image).
        # The 'version' parameter is static and denotes the version
        # of the EXAConf python module and EXAConf format
        self.version = "6.0.0"
        self.set_os_version(self.version)
        self.set_db_version(self.version)
        # static values
        self.max_reserved_node_id = 10 # IDs 0-10 are reserved
        self.container_root = "/exa"
        self.node_root_prefix = "n"
        self.dev_prefix = "dev."
        self.data_dev_suffix  = ".data"
        self.meta_dev_suffix  = ".meta"
        self.data_dir = "data"
        self.storage_dir = "data/storage"
        self.bucketfs_dir = "data/bucketfs"
        self.etc_dir = "etc"
        self.md_dir = "metadata"
        self.md_storage_dir = "metadata/storage"
        self.md_dwad_dir = "metadata/dwad"
        self.log_dir = "logs"
        self.logd_dir = "logs/logd"
        self.node_uuid = "etc/node_uuid"
        self.supported_platforms = ['Docker', 'VM']
        self.def_bucketfs = "bfsdefault"
        self.def_bucket = "default"
        self.def_db_port = 8888
        self.def_bucketfs_http_port = 6583
        self.def_bucketfs_https_port = 0
        # set root to container_root if omitted
        # --> only true when called from within the container
        if not root:
            self.root = os.path.join(self.container_root, self.etc_dir)
        else:
            self.root = root
        # check if root actually exists
        if not os.path.isdir(self.root):
            raise EXAConfError("root directory '%s' does not exist (or is a file)!" % self.root)
        self.conf_path = os.path.join(self.root, "EXAConf")
        # if initialized is true, the given file has to exist!
        if initialized and not os.path.exists(self.conf_path):
            raise EXAConfError("EXAConf file '%s' does not exist! Has the cluster been initialized?" % self.conf_path)
        # read / create configuration
        try:
            self.config = configobj.ConfigObj(self.conf_path,
                                              list_values = False,
                                              write_empty_values = True,
                                              indent_type = '    ')
        except configobj.ConfigObjError as e:
            raise EXAConfError("Failed to read '%s': %s" % (self.conf_path, e))
        
        # validate content if EXAConf is already initialized
        # also read current version numbers from config
        if initialized:
            self.validate()
            self.set_os_version(self.config["Global"]["OSVersion"])
            self.set_db_version(self.config["Global"]["DBVersion"])
#}}}

#{{{ Set OS version
    def set_os_version(self, os_version):
        """
        Stores the given OS (EXAClusterOS) version and builds the path to the OS installation 
        based on the OS version.
        """
        self.os_version = os_version.strip()
        self.os_major_version = self.os_version.split(".")[0].strip()
        self.os_dir = "/usr/opt/EXASuite-" + self.os_major_version + \
                      "/EXAClusterOS-" + self.os_version
#}}}

#{{{ Set db version
    def set_db_version(self, db_version):
        """
        Stores the given database (EXASolution) version and builds the path to the database installation 
        based on the db version.
        """
        self.db_version = db_version.strip()
        self.db_major_version = self.db_version.split(".")[0].strip()
        self.db_dir = "/usr/opt/EXASuite-" + self.db_major_version + \
                      "/EXASolution-" + self.db_version
#}}}

#{{{ Update db version
    def update_db_version(self, db_version):
        """
        Replaces all occurences of the database version number with the given one
        and commits the configuration (used to update the cluster).
        """

        db_version = db_version.strip()
        # get all databases with the current (old) version and replace with given one
        filters = {"Version" : self.db_version}
        db_configs = self.get_databases(filters=filters)
        for db in db_configs.iteritems():
            db_sec = self.config["DB : " + db[0]]
            db_sec["Version"] = db_version

        # change paths in all Buckets
        curr_suite_name = "EXASuite-" + self.db_major_version
        curr_db_name = "EXASolution-" + self.db_version
        new_suite_name = "EXASuite-" + db_version.split(".")[0].strip()
        new_db_name = "EXASolution-" + db_version
        bucketfs_conf = self.get_bucketfs_conf()
        for bfs in bucketfs_conf.fs.iteritems():
            for bucket in bfs[1].buckets.iteritems():
                bucket_sec = self.config['BucketFS : ' + bfs[0]]['Bucket : ' + bucket[0]]
                if "AdditionalFiles" in bucket_sec.scalars:
                    # replace the combo first (e. g. "EXASuite-5/EXASolution-5.0.1" with "EXASuite-6/EXASolution-6.0.0"
                    # in order to keep the old suite in the EXAClusterOS paths
                    bucket_sec["AdditionalFiles"] = bucket_sec["AdditionalFiles"].replace(curr_suite_name + "/" + curr_db_name,
                                                                                          new_suite_name + "/" + new_db_name)
                    bucket_sec["AdditionalFiles"] = bucket_sec["AdditionalFiles"].replace(curr_db_name, new_db_name)

        # replace global version
        self.config["Global"]["DBVersion"] = db_version
        self.set_db_version(db_version)
        self.commit()
#}}}
 
#{{{ Update os version
    def update_os_version(self, os_version):
        """
        Replaces all occurences of the OS version number with the given one
        and commits the configuration (used to update the cluster).
        """

        os_version = os_version.strip()
        # change paths in all Buckets
        curr_suite_name = "EXASuite-" + self.db_major_version
        curr_os_name = "EXAClusterOS-" + self.os_version
        new_suite_name = "EXASuite-" + os_version.split(".")[0].strip()
        new_os_name = "EXAClusterOS-" + os_version
        bucketfs_conf = self.get_bucketfs_conf()
        for bfs in bucketfs_conf.fs.iteritems():
            for bucket in bfs[1].buckets.iteritems():
                bucket_sec = self.config['BucketFS : ' + bfs[0]]['Bucket : ' + bucket[0]]
                if "AdditionalFiles" in bucket_sec.scalars:
                    # replace the combo first (e. g. "EXASuite-5/EXAClusterOS-5.0.1" with "EXASuite-6/EXAClusterOS-6.0.0"
                    # in order to keep the old suite in the EXASolution paths
                    bucket_sec["AdditionalFiles"] = bucket_sec["AdditionalFiles"].replace(curr_suite_name + "/" + curr_os_name,
                                                                                          new_suite_name + "/" + new_os_name)
                    bucket_sec["AdditionalFiles"] = bucket_sec["AdditionalFiles"].replace(curr_os_name, new_os_name)

        # replace global version
        self.config["Global"]["OSVersion"] = os_version
        self.set_os_version(os_version)
        self.commit()
#}}}
 
#{{{ Clear configuration
    def clear_config(self):
        """
        Clears all content of the 'EXAConf' file and this EXAConf instance.
        """
        self.config.reset()
        self.config.write()
        print "Cleared configuration in '%s'." % self.conf_path
#}}}

#{{{ Commit
    def commit(self):
        """ 
        Writes the configuration to disk (into '$RootDir/EXAConf')
        """
        self.config.write()
        # reload in order to force type conversion 
        # --> parameters added as lists during runtime are converted back to strings (as if they have been added manually)
        self.config.reload()
        # modify permissions
        try:
            os.chmod(self.conf_path, stat.S_IRUSR | stat.S_IWUSR)
        except OSError as e:
            raise EXAConfError("Failed to change permissions for '%s': %s" % (self.conf_path, e))
#}}}
 
#{{{ Platform supported
    def platform_supported(self, platform):
        """
        Checks if the given platform is in the list of supported platforms.
        """
        return platform in self.supported_platforms
#}}}
 
#{{{ Is initialized
    def initialized(self):
        """
        Checks if the current instance has already been initialized.
        """
        return "Global" in self.config.sections
#}}}

#{{{ (Re-)initialize a configuration
    def initialize(self, name, image, num_nodes, device_type, force, platform, 
                   db_version=None, os_version=None, license=None):
        """
        Initializes the current EXAConf instance. If 'force' is true, it will be
        re-initialized and the current content will be cleared.
        """

        # check if EXAConf is already initialized
        if self.initialized():
            if not force:
                print "EXAConf file '%s' is already initialized!" % self.conf_path
                return
            else:
                self.clear_config()
        # sanity checks
        if not self.platform_supported(platform):
            raise EXAConfError("Platform '%s' is not supported!") % platform
        # set db and os version if given
        if db_version and db_version.strip() != "":
            self.set_db_version(db_version.strip())
        if os_version and os_version.strip() != "":
            self.set_os_version(os_version.strip())
        # Global section
        self.config["Global"] = {}
        glob_sec = self.config["Global"]
        glob_sec["ClusterName"] = name
        glob_sec["Platform"] = platform
        glob_sec["LicenseFile"] = license if license else ""
        glob_sec["CoredPort"] = "10001"
        glob_sec["Networks"] = "private"
        glob_sec["ConfVersion"] = self.version
        glob_sec["OSVersion"] = self.os_version
        glob_sec["DBVersion"] = self.db_version
        # comments
        glob_sec.comments["Networks"] = ["The type of networks for this cluster: 'public', 'private' or both."]

        # Docker section
        if platform == "Docker":
            self.config["Docker"] = {}
            docker_sec = self.config["Docker"]
            docker_sec["RootDir"] = self.root
            docker_sec["Image"] = image
            docker_sec["DeviceType"] = device_type
            # comments
            self.config.comments["Docker"] = ["\n","Docker related options"]
            docker_sec.comments["RootDir"] = ["The directory that contains all data related to this docker cluster","(except for mapped devices)"]
            docker_sec.comments["Image"] = ["The EXASOL docker image used for all containers of this cluster"]
            docker_sec.comments["DeviceType"] = ["The type of storage devices for this cluster: 'block' or 'file'"]

        # Node sections
        for node in range (1, num_nodes+1):
            node_id = self.max_reserved_node_id + node
            node_section =  "Node : " + str(node_id)     
            self.config[node_section] = {}
            node_sec = self.config[node_section]
            node_sec["PrivateNet"] = "10.10.10.%i/24" % node_id
            node_sec["PublicNet"] = ""
            node_sec["Hostname"] = "n" + str(node_id)
            # Docker specific options:
            if platform == "Docker":
                node_sec["DockerVolume"] = "n" + str(node_id)
                node_sec["ExposedPorts"] = str(self.def_db_port) + ":" + str(self.def_db_port + node_id)
                if self.def_bucketfs_http_port > 0:
                    node_sec["ExposedPorts"] +=  ", " + str(self.def_bucketfs_http_port) + ":" + str(self.def_bucketfs_http_port + node_id)
                if self.def_bucketfs_https_port > 0:
                    node_sec["ExposedPorts"] +=  ", " + str(self.def_bucketfs_https_port) + ":" + str(self.def_bucketfs_https_port + node_id)
                # Docker comments
                node_sec.comments["ExposedPorts"] = ["Ports to be exposed (container : host)"]
            # other platfrom options
            if platform == "VM":
                node_sec["PrivateInterface"] = "eth0"
                node_sec["PublicInterface"] = "eth1"
            #comments
            self.config.comments[node_section] = ["\n"]

        # EXAStorage sections
        # data volume
        self.config["EXAVolume : DataVolume1"] = {}
        data_vol_sec = self.config["EXAVolume : DataVolume1"]
        data_vol_sec["Type"] = "data"
        data_vol_sec["Nodes"] = [ str(n) for n in self.get_nodes_conf().keys() ] # list is correctly converted by ConfigObj
        data_vol_sec["Disk"] = ""
        data_vol_sec["Size"] = ""
        data_vol_sec["Redundancy"] = "1"
        data_vol_sec["Owner"] = str(os.getuid()) + " : " + str(os.getgid())
        data_vol_sec["Labels"] = ""
        #comments
        self.config.comments["EXAVolume : DataVolume1"] = ["\n", "An EXAStorage data volume"]
        data_vol_sec.comments["Type"] = ["Type of volume: 'data' | 'archive'"]
        data_vol_sec.comments["Nodes"] = ["Comma-separated list of node IDs to be used for this volume (incl. redundancy nodes)"]
        data_vol_sec.comments["Disk"] = ["Name of the disk to be used for this volume.","This disk must exist on all volume nodes."]
        data_vol_sec.comments["Size"] = ["Volume size (e. g. '1 TiB')"]
        data_vol_sec.comments["Redundancy"] = ["Desired redundancy for this volume"]
        data_vol_sec.comments["Owner"] = ["Volume owner (user and group ID)"]
        data_vol_sec.comments["Labels"] = ["OPTIONAL: a comma-separated list of labels for this volume"]
        # archive volume
        self.config["EXAVolume : ArchiveVolume1"] = {}
        archive_vol_sec = self.config["EXAVolume : ArchiveVolume1"]
        archive_vol_sec["Type"] = "archive"
        archive_vol_sec["Nodes"] = [ str(n) for n in self.get_nodes_conf().keys() ] # list is correctly converted by ConfigObj
        archive_vol_sec["Disk"] = ""
        archive_vol_sec["Size"] = ""
        archive_vol_sec["Redundancy"] = "1"
        archive_vol_sec["Owner"] = str(os.getuid()) + " : " + str(os.getgid())
        archive_vol_sec["Labels"] = ""
        #comments
        self.config.comments["EXAVolume : ArchiveVolume1"] = ["\n", "An EXAStorage archive volume"]
 
        # DB sections
        self.config["DB : DB1"] = {}
        db_sec = self.config["DB : DB1"] 
        db_sec["DataVolume"] = "DataVolume1"
        db_sec["ArchiveVolume"] = "ArchiveVolume1"
        db_sec["Version"] = str(self.db_version)
        db_sec["Owner"] = str(os.getuid()) + " : " + str(os.getgid())
        db_sec["MemSize"] = '2 GiB'
        db_sec["Port"] = str(self.def_db_port)
        db_sec["Nodes"] = [ str(n) for n in self.get_nodes_conf().keys() ] # list is correctly converted by ConfigObj
        db_sec["NumMasterNodes"] = str(len(self.get_nodes_conf().keys()))
        # comments
        self.config.comments["DB : DB1"] = ["\n", "An EXASOL database"]
        db_sec.comments["Version"] = ["The EXASOL version to be used for this database"]
        db_sec.comments["Owner"] = ["User and group ID that should own this database"]
        db_sec.comments["MemSize"] = ["Memory size over all nodes (e. g. '1 TiB')"]

        # BucketFS section
        self.config["BucketFS"] = {}
        glob_bfs_sec = self.config["BucketFS"]
        glob_bfs_sec["ServiceOwner"] = str(os.getuid()) + " : " + str(os.getgid())
        #comments
        self.config.comments["BucketFS"] = ["\n","Global BucketFS options"]
        glob_bfs_sec.comments["ServiceOwner"] = ["User and group ID of the BucketFS process."]

        # The default BucketFS
        self.config["BucketFS : %s" % self.def_bucketfs] = {}
        bfs_sec = self.config["BucketFS : %s" % self.def_bucketfs]
        bfs_sec["HttpPort"] = str(self.def_bucketfs_http_port)
        bfs_sec["HttpsPort"] = str(self.def_bucketfs_https_port)
        bfs_sec["SyncKey"] = gen_base64_passwd(32)
        bfs_sec["SyncPeriod"] = "30000"
        # comments
        self.config.comments["BucketFS : bfsdefault"] = ["\n","A Bucket filesystem"]
        bfs_sec.comments["HttpPort"] = ["HTTP port number (0 = disabled)"]
        bfs_sec.comments["HttpsPort"] = ["HTTPS port number (0 = disabled)"]
        bfs_sec.comments["Path"] = ["OPTIONAL: path to this BucketFS (default: %s)" % os.path.join(self.container_root, self.bucketfs_dir)]

        # Bucket sub-section
        bfs_sec["Bucket : %s" % self.def_bucket] = {}
        bucket_sec = bfs_sec["Bucket : %s" % self.def_bucket]
        bucket_sec["ReadPasswd"] = gen_base64_passwd(22)
        bucket_sec["WritePasswd"] = gen_base64_passwd(22)
        bucket_sec["Public"] = "True"
        bucket_sec["Name"] = "default"
        bucket_sec["AdditionalFiles"] = "EXAClusterOS:" + os.path.join(self.os_dir, "var/clients/packages/ScriptLanguages-*") + ", " + \
                                        "EXASolution-" + self.db_version + ":" + os.path.join(self.db_dir, "bin/udf/*")
        # comments
        bfs_sec.comments["Bucket : default"] = ["\n", "A bucket"]

        self.commit()
        print "Successfully initialized configuration in '%s'." % self.conf_path
# }}}
 
#{{{ Validate the configuration
    def validate(self):
        """ Validates the EXAConf configuration file. """
    
        # validation only makes sense after initalization
        if not self.initialized():
            raise EXAConfError("Configuration is not initialized! Use 'init-cluster' in order to initialize it.")
        # public network is optional
        have_priv_net = self.has_priv_net()
        have_pub_net = self.has_pub_net()
        if not have_priv_net and not have_pub_net:
            raise EXAConfError("Neither private nor public network are enabled!")

        # docker specific checks
        have_docker = (self.get_platform() == "Docker")
        if have_docker:
            if not "Docker" in self.config.sections:
                raise EXAConfError("Docker platform is specified but 'Docker' section is missing!")

        # check for duplicate entries in node sections 
        hostnames = []
        docker_volumes = []
        all_priv_nets = []
        all_pub_nets = []
        for section in self.config.sections:
            if self.is_node(section):
                node_sec = self.config[section]
                # hostname
                host = node_sec.get("Hostname")
                if not host or host == "":
                    raise EXAConfError("Hostname is missing in section '%s'!" % section)
                hostnames.append(host)
                # docker volume (only for Docker installations!)
                if have_docker:
                    volume = node_sec.get("DockerVolume")
                    if not volume or volume == "":
                        raise EXAConfError("Docker volume is missing in section '%s'!" % section)
                    docker_volumes.append(volume)
                # private network
                node_priv_net = node_sec.get("PrivateNet")
                if node_priv_net and node_priv_net != "":
                    if not self.net_is_valid(node_priv_net):
                        raise EXAConfError("Private network '%s' in section '%s' is invalid!" % (node_priv_net, section))
                    all_priv_nets.append(node_priv_net)
                elif have_priv_net:
                    raise EXAConfError("Private network is enabled but network is missing in section '%s'!" % section)
                # public network
                node_pub_net = node_sec.get("PublicNet")
                if node_pub_net and node_pub_net != "":
                    if not self.net_is_valid(node_pub_net):
                        raise EXAConfError("Public network '%s' in section '%s' is invalid!" % (node_pub_net, section))
                    all_pub_nets.append(node_pub_net)
                elif have_pub_net:
                    raise EXAConfError("Public network is enabled but network is missing in section '%s'!" % section)
                ### storage devices
                node_devices = []
                # extract disk name and devices
                for section in node_sec.sections:
                    if self.is_disk(section):
                        disk_sec = node_sec[section]
                        disk_name = self.get_section_id(section)
                        disk_devices = [ d.strip() for d in disk_sec["Devices"].split(",") if d.strip() != "" ]
                        if not disk_devices or len(disk_devices) == 0:
                            raise EXAConfError("No devices specified for disk '%s' in section '%s'!" % (disk_name, section))
                        # remember all disks and devices of the current node
                        node_devices += disk_devices
                # check for duplicate device names
                dup = self.get_duplicates(node_devices)
                if dup and len(dup) > 0:
                    raise EXAConfError("Detected duplicate devices in section '%s': %s" %(section, dup))
                # TODO : check specified type vs. actual device type
        # check for duplicates and list them
        dup = self.get_duplicates(hostnames)
        if dup and len(dup) > 0:
            raise EXAConfError("Detected duplicate hostnames: %s!" % dup)
        dup = self.get_duplicates(docker_volumes)
        if dup and len(dup) > 0:
            raise EXAConfError("Detected duplicate docker volumes: %s!" % dup)
        dup = self.get_duplicates(all_priv_nets)
        if dup and len(dup) > 0:
            raise EXAConfError("Detected duplicate private networks: %s!" % dup)
        dup = self.get_duplicates(all_pub_nets)
        if dup and len(dup) > 0:
            raise EXAConfError("Detected duplicate public networks: %s!" % dup)
#}}}

#{{{ Check if section is a node
    def is_node(self, section):
        """
        Returns true if the given section is a node.
        """
        return section.split(":")[0].strip() == "Node"
#}}}
 
#{{{ Check if section is a volume
    def is_storage_volume(self, section):
        """
        Returns true if the given section is an EXAStorage volume.
        """
        return section.split(":")[0].strip() == "EXAVolume"
#}}}
  
#{{{ Check if section is a database
    def is_database(self, section):
        """
        Returns true if the given section is an EXASolution database.
        """
        return section.split(":")[0].strip() == "DB"
#}}}
   
#{{{ Check if section is a BucketFS
    def is_bucketfs(self, section):
        """
        Returns true if the given section is a BucketFS.
        """
        # don't try to split the global section!
        return section != "BucketFS" and section.split(":")[0].strip() == "BucketFS"
#}}}
                                                           
#{{{ Check if section is a bucket
    def is_bucket(self, section):
        """
        Returns true if the given section is a bucket.
        """
        return section.split(":")[0].strip() == "Bucket"
#}}}
                                                            
#{{{ Check if section is a disk
    def is_disk(self, section):
        """
        Returns true if the given section is a disk.
        """
        return section.split(":")[0].strip() == "Disk"
#}}}
 
#{{{ Check if IP is valid
    def ip_is_valid(self, ip):
        """
        Returns true if the given string is a valid IP address (v4 or v6).
        """
        try:
            ipaddr.IPAddress(ip)
            return True
        except ValueError:
            return False
#}}}
 
#{{{ Check if network is valid
    def net_is_valid(self, net):
        """
        Returns true if the given string is a valid IP network (v4 or v6).
        """
        try:
            ipaddr.IPNetwork(net)
            return True
        except ValueError:
            return False
#}}}

#{{{ IP type
    def ip_type(self, ip):
        """
        Returns 4 if the given string is a valid IPv4 address and 6 if it's
        a valid IPv6 address. Returns 0 if neither.
        """
        try:
            ipaddr.IPv4Address(ip)
            return 4
        except ipaddr.AddressValueError: pass
        try:
            ipaddr.IPv6Address(ip)
            return 6
        except ipaddr.AddressValueError: pass
        return 0
#}}}            
 
#{{{ Has private network
    def has_priv_net(self):
        """ 
        Returns true if a private network is enabled in EXAConf.
        """
        try:
            priv = "private" in [ n.strip() for n in self.config["Global"]["Networks"].split(",") ]
        except ValueError:
            return False
        return priv
#}}}

#{{{ Has public network
    def has_pub_net(self):
        """ 
        Returns true if a public network is enabled in EXAConf.
        """
        try:
            pub = "public" in [ n.strip() for n in self.config["Global"]["Networks"].split(",") ]
        except ValueError:
            return False
        return pub
#}}}
 
#{{{ Add node device
    def add_node_device(self, node_id, disk, device, path):
        """ 
        Adds the given device as a storage device to the given node.
        If 'path' is specified, a mapping is also added. 
        """

        node_section = "Node : " + str(node_id)
        if node_section not in self.config.sections:
            raise EXAConfError("Node %s does not exist in '%s'." % (node_id, self.conf_path))
        node_sec = self.config[node_section]
        disk_sec_name = "Disk : " + disk
        # get / create disk subsection
        disk_sec = odict()
        if disk_sec_name in node_sec.sections:
            disk_sec = node_sec[disk_sec_name]
        # add device
        if "Devices" in disk_sec.keys():
            disk_sec["Devices"] = disk_sec["Devices"] + ", " + device
        else:
            disk_sec["Devices"] = device
        # add mapping
        if path and path != "":
            if "Mapping" in disk_sec.keys():
                disk_sec["Mapping"] = disk_sec["Mapping"] + ", " + device + ":" + path
            else:
                disk_sec["Mapping"] = device + ":" + path
        #  set modified section / new dict
        node_sec[disk_sec_name] = disk_sec

        self.commit()
#}}}

#{{{ Remove node devices
    def remove_node_devices(self, node_id):
        """ 
        Removes ALL storage devices of the given node from EXAConf.
        """
 
        node_section = "Node : " + str(node_id)
        if node_section not in self.config.sections:
            raise EXAConfError("Node %s does not exist in '%s'." % (node_id, self.conf_path))
        # use slice for in-place modification
        for sect in tuple(self.config[node_section].sections):
            if self.is_disk(sect):
                del self.config[node_section][sect]
        self.commit()
#}}}
  
#{{{ Use disk for volumes
    def use_disk_for_volumes(self, disk, bytes_per_node, vol_type=None):
        """
        Adds the given disk to all volumes of the given type that don't have a disk assigned yet.         
        The given 'bytes_per_node' space is distributed equally across all suitable volumes.
        """

        # we only consider volumes without disks
        filters = {"disk": ""}
        if vol_type and vol_type != "":
            filters["type"] = vol_type
        volumes = self.get_storage_volumes(filters=filters)
        bytes_per_volume_node = bytes_per_node / len(volumes)

        for volume in volumes.iteritems():
            vol_sec = self.config["EXAVolume : " + volume[0]]
            vol_sec["Disk"] = disk
            vol_sec["Size"] = bytes2units(bytes_per_volume_node / volume[1].redundancy)

        self.commit()
#}}}

############################## GETTER #################################
 
#{{{ Get section ID 
    def get_section_id(self, section):
        """
        Extracts and returns the part behind the ':' from the given section.
        """
        return section.split(":")[1].strip()
#}}}
 
#{{{ Get conf path
    def get_conf_path(self):
        """
        Returns the path to '$RootDir/EXAConf'.
        """
        return self.conf_path
#}}}

#{{{ Get platform
    def get_platform(self):
        """
        Returns the platform of the current EXAConf.
        """
        return self.config["Global"]["Platform"]
#}}}    
  
#{{{ Get cluster name
    def get_cluster_name(self):
        """
        Returns the cluster name.
        """
        return self.config["Global"]["ClusterName"]
#}}}
  
#{{{ Get db version
    def get_db_version(self):
        """
        Returns the current DB version.
        """
        if self.initialized():
            return self.config["Global"]["DBVersion"]
        else:
            return self.db_version
#}}}
   
#{{{ Get os version
    def get_os_version(self):
        """
        Returns the current OS version.
        """
        if self.initialized():
            return self.config["Global"]["OSVersion"]
        else:
            return self.os_version
#}}}
 
#{{{ Get cored port
    def get_cored_port(self):
        """
        Returns the network port used by the 'Cored' daemon.
        """
        return self.config["Global"]["CoredPort"]
#}}}

#{{{ Get license file
    def get_license_file(self):
        """
        Returns the path to the license file.
        """
        return self.config["Global"]["LicenseFile"]
#}}}

#{{{ Get private network name
    def get_priv_net_name(self):
        """ 
        Returns the NAME of the private network.
        """
        priv_net_name = self.get_cluster_name() + "_priv"
        return priv_net_name
#}}}
 
#{{{ Get public network name
    def get_pub_net_name(self):
        """ 
        Returns the NAME of the public network.
        """
        pub_net_name = self.get_cluster_name() + "_pub"
        return pub_net_name
#}}}
 
#{{{ Get duplicates
    def get_duplicates(self, seq):
        """
        Returns a list off all duplicates in the given sequence.
        """
        if len(seq) == 0:
            return None
        seen = set()
        seen_twice = set(x for x in seq if x in seen or seen.add(x))
        return list(seen_twice)
#}}}

#{{{ Get network
    def get_network(self, net_type):
        """ 
        Returns a network (as a string) that includes the private/public IPs of all nodes in the config.
        Raises an EXAConfError if an invalid IP is found or the IP of at least one node is not part
        of the network defined by the first node section.

        This function assumes that all nodes have an entry for the requested network type. The calling 
        function has to check if the network type is actually present (private / public).
        """

        network = "" 
        for section in self.config.sections:
            if self.is_node(section):
                node_sec = self.config[section]
                node_network = node_sec.get(net_type)
                if not node_network or node_network == "":
                    raise EXAConfError("Network type '%s' is missing in section '%s'!" % (net_type, section))
                node_ip = node_network.split("/")[0].strip()
                # check if the extracted IP is valid
                if not self.ip_is_valid(node_ip):
                    raise EXAConfError("IP %s in section '%s' is invalid!" % (node_ip, section))

                # first node : choose the private net as the cluster network (and make it a 'real' network)
                if network == "":
                    subnet = ipaddr.IPNetwork(node_network)
                    network = "%s/%s" % (str(subnet.network), str(subnet.prefixlen))
                # other nodes : check if their IP is part of the chosen net
                elif ipaddr.IPAddress(node_ip) not in ipaddr.IPNetwork(network):
                    raise EXAConfError("IP %s is not part of network %s!" % (node_ip, network))

        return network
#}}}

#{{{ Get private network
    def get_priv_net(self):
        """
        Get a valid IP network containing the private IPs of all nodes (see get_network()).
        """
        return self.get_network("PrivateNet")
#}}}

#{{{ Get public network
    def get_pub_net(self):
        """
        Get a valid IP network containing the public IPs of all nodes (see get_network()).
        """
        return self.get_network("PublicNet")
#}}}

#{{{ Get nodes conf
    def get_nodes_conf(self):
        """ 
        Returns a config containing all nodes and their options within the config file.
        Options with empty values are omitted.
        """
        node_configs = config()
        for section in self.config.sections:
            if self.is_node(section):
                node_sec = self.config[section]
                nid = self.get_section_id(section)
                node_conf = config()
                node_conf.id = nid
                node_conf.hostname = node_sec["Hostname"]
                node_conf.private_net = node_sec["PrivateNet"]
                node_conf.private_ip = node_conf.private_net.split("/")[0]
                node_conf.public_net = node_sec["PublicNet"]
                node_conf.public_ip = node_conf.public_net.split("/")[0]
                # storage disks
                node_conf.disks = config()
                for subsec in node_sec.sections:
                    if self.is_disk(subsec):
                        disk_sec = node_sec[subsec]
                        disk_conf = config()
                        disk_conf.name = self.get_section_id(subsec)
                        devices = [ dev.strip() for dev in disk_sec["Devices"].split(",") if dev.strip() != "" ]
                        disk_conf.devices = [ (dev+self.data_dev_suffix, dev+self.meta_dev_suffix) for dev in devices ]
                        # optional disk values
                        if "Mapping" in disk_sec.scalars:
                            # the device-mapping entries, as they are found in the EXAConf file
                            disk_conf.mapping = [ (m.split(":")[0].strip(), m.split(":")[1].strip()) for m in disk_sec["Mapping"].split(",") if m.strip() != "" ]
                            # list of tuples that map an external device-file to a container-path
                            # --> converted to absolute paths, so they can be directly used by the docker-handler 
                            disk_conf.mapped_devices = []
                            for dev, path in disk_conf.mapping:
                                meta_dev_host = os.path.join(path, dev) + self.meta_dev_suffix
                                meta_dev_container = os.path.join(self.container_root, self.storage_dir, dev + self.meta_dev_suffix)
                                disk_conf.mapped_devices.append((meta_dev_host, meta_dev_container))
                                data_dev_host = os.path.join(path, dev) + self.data_dev_suffix
                                data_dev_container = os.path.join(self.container_root, self.storage_dir, dev + self.data_dev_suffix)
                                disk_conf.mapped_devices.append((data_dev_host, data_dev_container))
                        node_conf.disks[disk_conf.name] = disk_conf
                # optional node values
                if "DockerVolume" in node_sec.scalars:
                    node_conf.docker_volume = os.path.join(self.config["Docker"]["RootDir"], node_sec["DockerVolume"])
                if "ExposedPorts" in node_sec.scalars:
                    node_conf.exposed_ports =  [ p.split(":") for p in node_sec["ExposedPorts"].split(",") ]
                    node_conf.exposed_ports[:] = [ (int(p[0].strip()), int(p[1].strip())) for p in node_conf.exposed_ports ]
                if "PrivateInterface" in node_sec.scalars:
                    node_conf.private_interface = node_sec["PrivateInterface"]
                if "PublicInterface" in node_sec.scalars:
                    node_conf.public_interface = node_sec["PublicInterface"]
                node_configs[nid] = node_conf
        return node_configs
#}}}

#{{{ Get num nodes
    def get_num_nodes(self):
        """
        Returns the nr. of nodes in the current EXAConf.
        """
        return len([sec for sec in self.config.sections if self.is_node(sec)])
#}}}

#{{{ Get storage volumes
    def get_storage_volumes(self, filters=None):
        """
        Returns a config describing all existing EXAStorage volumes.
        """
        volume_configs = config()
        for section in self.config.sections:
            if self.is_storage_volume(section):
                vol_sec = self.config[section]
                # copy values to config
                vol_name = self.get_section_id(section)
                conf = config()
                conf.name = vol_name
                conf.type = vol_sec["Type"].strip()
                conf.disk = vol_sec["Disk"].strip()
                conf.redundancy = vol_sec.as_int("Redundancy")
                conf.nodes = [ int(n.strip()) for n in vol_sec["Nodes"].split(",") if n.strip() != "" ]
                conf.size = units2bytes(vol_sec["Size"]) if vol_sec["Size"].strip() != "" else -1
                conf.owner = tuple([ int(x.strip()) for x in vol_sec["Owner"].split(":") if x.strip() != "" ])
                # optional values
                if "NumMasterNodes" in vol_sec.scalars:
                    conf.num_master_nodes = vol_sec["NumMasterNodes"]
                else:
                    conf.num_master_nodes = len(conf.nodes)
                if "Labels" in vol_sec.scalars:
                    conf.labels = [ l.strip() for l in vol_sec["Labels"].split(",") if l.strip() != "" ]
                # HIDDEN optional values:
                if "BlockSize" in vol_sec.scalars:
                    conf.block_size = units2bytes(vol_sec["BlockSize"])
                elif conf.type == "data":
                    conf.block_size = 4096
                elif conf.type == "archive":
                    conf.block_size = 65536
                if "StripeSize" in vol_sec.scalars:
                    conf.stripe_size = units2bytes(vol_sec["StripeSize"])
                else:
                    conf.stripe_size = conf.block_size * 64
                volume_configs[vol_name] = conf
        return self.filter_configs(volume_configs, filters)
#}}}
 
#{{{ Get databases
    def get_databases(self, filters=None):
        """
        Returns a config describing all existing EXASolution databases.
        """
        db_configs = config()
        for section in self.config.sections:
            if self.is_database(section):
                db_sec = self.config[section]
                db_name = self.get_section_id(section)
                conf = config()
                conf.name = db_name
                conf.version = db_sec["Version"]
                conf.data_volume = db_sec["DataVolume"]
                conf.archive_volume = db_sec["ArchiveVolume"]
                conf.mem_size =  int(int(units2bytes(db_sec["MemSize"])) / 1048576)
                conf.port = db_sec.as_int("Port")
                conf.nodes = [ int(n.strip()) for n in db_sec["Nodes"].split(",") if n.strip() != "" ]
                conf.num_master_nodes = db_sec.as_int("NumMasterNodes")
                conf.owner = tuple([ int(x.strip()) for x in db_sec["Owner"].split(":") if x.strip() != "" ])
                # optional values:
                if "Params" in db_sec.scalars:
                    conf.params = db_sec["Params"]
                db_configs[db_name] = conf
        return self.filter_configs(db_configs, filters)
#}}}
      
#{{{ Get bucketfs conf
    def get_bucketfs_conf(self):
        """
        Returns a config containing global options and config objects for all bucket filesystem and their buckets in 'fs'.
        """
        bfs_config = config()
        bfs_config.service_owner = tuple([ int(x.strip()) for x in self.config["BucketFS"]["ServiceOwner"].split(":") if x.strip() != "" ])
        bfs_config.fs = config()
        for section in self.config.sections:
            if self.is_bucketfs(section):
                bfs_sec = self.config[section]
                bfs_conf = config()
                bfs_conf.bfs_name = self.get_section_id(section)
                bfs_conf.http_port = bfs_sec.as_int("HttpPort")
                bfs_conf.https_port = bfs_sec.as_int("HttpsPort")
                bfs_conf.sync_key = bfs_sec["SyncKey"]
                bfs_conf.sync_period = bfs_sec["SyncPeriod"]
                # optional values
                if "Path" in bfs_sec.scalars:
                    bfs_conf.path = bfs_sec["Path"]
                # buckets
                bfs_conf.buckets = config()
                for subsec in bfs_sec.sections:
                    if self.is_bucket(subsec):
                        b_sec = bfs_sec[subsec]
                        b_conf = config()
                        b_conf.id = self.get_section_id(subsec)
                        b_conf.read_passwd = b_sec["ReadPasswd"]
                        b_conf.write_passwd = b_sec["WritePasswd"]
                        b_conf.public = b_sec.as_bool("Public")
                        if "AdditionalFiles" in b_sec.scalars:
                            b_conf.additional_files = [ f.strip() for f in b_sec["AdditionalFiles"].split(",") if f.strip() != "" ]
                        if "Name" in b_sec.scalars:
                            b_conf.name = b_sec["Name"]
                        bfs_conf.buckets[b_conf.id] = b_conf
                bfs_config.fs[bfs_conf.bfs_name] = bfs_conf
        return bfs_config
#}}}

#{{{ Filter configs
    def filter_configs(self, configs, filters):
        """
        Applies the given filters (a dict) to the given config object by removing all items that
        don't match the filter criteria. It assumes that 'configs' contains is in fact a dict
        with config objects as values (e. g. some volumes or database configurations).
        """
        if not filters:
            return configs
        for item in configs.items(): # use a copy!
            for f in filters.iteritems():
                if f[0] in item[1].iterkeys() and f[1] != item[1][f[0]]:
                    del configs[item[0]]
                    break
        return configs
#}}}

##############################  DOCKER EXCLUSIVE STUFF ##################################

#{{{ Get docker image
    def get_docker_image(self):
        """
        Returns the name of the docker image used for this cluster.
        """
        return self.config["Docker"]["Image"]
#}}}

#{{{ Update docker image
    def update_docker_image(self, image):
        """
        Replaces the docker image for all containers of this cluster with the given one. 
        The cluster has to be restarted in order to create new containers from the
        new image.
        """
        self.config["Docker"]["Image"] = image
        self.commit()
#}}}

#{{{ Get docker device type
    def get_docker_device_type(self):
        """
        Returns the device-type used for this cluster (file | block).
        """
        return self.config["Docker"]["DeviceType"]
#}}}

#{{{ Get docker root directory
    def get_docker_root_dir(self):
        """
        Returns the docker root-directory of this cluster.
        """
        return self.config["Docker"]["RootDir"]
#}}}

#{{{ Get docker node volumes
    def get_docker_node_volumes(self):
        """ 
        Returns a config containing the absolute path to the docker-volume of all nodes. 
        """

        node_volumes = config()
        for section in self.config.sections:
            if self.is_node(section):
                node_volumes[self.get_section_id(section)] = os.path.join(self.root, self.config[section]["DockerVolume"])
        return node_volumes
#}}}
 
#{{{ Get docker conf
    def get_docker_conf(self):
        """ 
        Returns a config object containing all entries from the 'Docker' section. 
        """

        if self.get_platform() != "Docker":
            raise EXAConfError("This function is only supported for the 'Docker' platform!")
        conf = config()
        docker_sec = self.config["Docker"]
        conf.root_dir = docker_sec["RootDir"]
        conf.image = docker_sec["Image"]
        conf.device_type = docker_sec["DeviceType"]
        return conf
#}}}
