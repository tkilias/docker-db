FROM centos:6.8

MAINTAINER EXASOL "service@exasol.com"

RUN yum update -y --exclude=kernel* && \
    yum install -y \
    java-1.8.0-openjdk-headless \
    openssh-server \
    openssh-clients \
    which \
    sudo \
    vim \
    tar \
    man \
    rsync && \
    yum clean all

LABEL name="EXASOL DB Docker Image"  \
      version="6.0.8-d1" \
      dbversion="6.0.8" \
      osversion="6.0.8" \
      reversion="6.0.8" \
      license="Proprietary" \
      vendor="EXASOL AG"


COPY license/license.xml     /.license.xml
ADD EXAClusterOS-6.0.8_LS-DOCKER-CentOS-6.8_x86_64.tar.gz              /
ENV PATH=/usr/opt/EXASuite-6/EXAClusterOS-6.0.8/bin:/usr/opt/EXASuite-6/EXAClusterOS-6.0.8/sbin:/usr/opt/EXASuite-6/EXARuntime-6.0.8/bin:/usr/opt/EXASuite-6/EXARuntime-6.0.8/sbin:/usr/op/EXASuite-6/EXASolution-6.0.8/bin/Console:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
    MANPATH=/usr/opt/EXASuite-6/EXAClusterOS-6.0.8/man:/usr/local/share/man:/usr/share/man \
    EXA_IMG_VERSION="6.0.8-d1" \
    EXA_DB_VERSION="6.0.8" \
    EXA_OS_VERSION="6.0.8" \
    EXA_RE_VERSION="6.0.8" 

ENTRYPOINT ["/usr/opt/EXASuite-6/EXAClusterOS-6.0.8/devel/docker/exadt"]
CMD ["init-sc"]
