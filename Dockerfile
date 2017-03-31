FROM centos:6

MAINTAINER EXASOL "service@exasol.com"

RUN yum update -y
RUN yum install -y java-1.8.0-openjdk-headless openssh-server openssh-clients which sudo vim tar rsync

LABEL name="EXASOL DB Docker Image"
LABEL version="6.0.0-d1"
LABEL dbversion="6.0.0"
LABEL osversion="6.0.0"
LABEL license="Proprietary"
LABEL vendor="EXASOL AG"
                                  
ENV PATH=/usr/opt/EXASuite-6/EXAClusterOS-6.0.0/bin:/usr/opt/EXASuite-6/EXAClusterOS-6.0.0/sbin:/usr/opt/EXASuite-6/EXARuntime-6.0.0/bin:/usr/opt/EXASuite-6/EXARuntime-6.0.0/bin:/usr/opt/EXASuite-6/EXASolution-6.0.0/bin/Console:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
ADD EXAClusterOS-6.0.0_LS-6.0.0-CentOS-6.8_x86_64.tar.gz              /

CMD /usr/opt/EXASuite-6/EXAClusterOS-6.0.0/libexec/exainit.py
