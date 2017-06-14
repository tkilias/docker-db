FROM centos:6.8

MAINTAINER EXASOL "service@exasol.com"

RUN http_proxy=http://repoproxy.core.exasol.com:3128 yum update -y
RUN http_proxy=http://repoproxy.core.exasol.com:3128 yum install -y java-1.8.0-openjdk-headless openssh-server openssh-clients which sudo vim tar rsync

LABEL name="EXASOL DB Docker Image"
LABEL version="6.0.1-d1"
LABEL dbversion="6.0.1"
LABEL osversion="6.0.1"
LABEL reversion="6.0.1"
LABEL license="Proprietary"
LABEL vendor="EXASOL AG"

ENV PATH=/usr/opt/EXASuite-6/EXAClusterOS-6.0.1/bin:/usr/opt/EXASuite-6/EXAClusterOS-6.0.1/sbin:/usr/opt/EXASuite-6/EXARuntime-6.0.1/bin:/usr/opt/EXASuite-6/EXARuntime-6.0.1/sbin:/usr/op/EXASuite-6/EXASolution-6.0.1/bin/Console:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin                                  
ADD EXAClusterOS-6.0.1_LS-DOCKER-CentOS-6.8_x86_64.tar.gz              /

CMD /usr/opt/EXASuite-6/EXAClusterOS-6.0.1/libexec/exainit.py
