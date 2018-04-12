FROM registry.cmusatyalab.org/junjuew/gabriel-container-registry:base
MAINTAINER Junjue Wang, junjuew@cs.cmu.edu

RUN apt-get update \
    && apt-get install -y \
    python-opencv \
    build-essential \
    cmake \
    libboost-all-dev \
    && apt-get autoremove \
    && apt-get clean

RUN pip install dlib

RUN apt-get install -y \
    python-matplotlib \
    libblas-dev \
    liblapack-dev \
    libatlas-base-dev \
    gfortran \
    && apt-get autoremove \
    && apt-get clean

RUN pip install scikit-image

RUN apt-get update \
    && apt-get install -y \
    redis-tools \
    && apt-get autoremove \
    && apt-get clean

ADD gabriel-apps /gabriel-apps
ADD run.sh /run.sh

WORKDIR /

EXPOSE 9098 9101

CMD ["/run.sh"]