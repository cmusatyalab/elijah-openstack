OpenStack extension for Cloudlet support
========================================================
A cloudlet is a new architectural element that arises from the convergence of
mobile computing and cloud computing. It represents the middle tier of a
3-tier hierarchy:  mobile device - cloudlet - cloud.   A cloudlet can be
viewed as a "data center in a box" whose  goal is to "bring the cloud closer".

Copyright (C) 2012-2014 Carnegie Mellon University This is a developing project
and some features might not be stable yet.  Please visit our website at [Elijah
page](http://elijah.cs.cmu.edu/).



License
----------

All source code, documentation, and related artifacts associated with the
cloudlet open source project are licensed under the [Apache License, Version
2.0](http://www.apache.org/licenses/LICENSE-2.0.html).



Prerequisites
-------------

1. cloudlet-provisioning library: This repository only has logics for OpenStack
binding with Cloudlet code. Therefore, you should first install cloudlet
related library.  For cloudlet-provisioning, you can install it at
[elijah-provisioning](https://github.com/cmusatyalab/elijah-provisioning).

2. OpenStack Icehouse: Please install OpenStack first, and test it's full
functionality. Since OpenStack installation itself requires significant
efforts, we strongly recommend
[DevStack](http://devstack.org/guides/single-machine.html) All-in-One (single
machine) for simple test purpose. DevStack will mostaly automatically prepare
OpenStack for you.

3. We have tested at Ubuntu 14.04 LTS 64 bits with OpenStack Icehouse.



Installation (Using DevStack)
-----------------------------

This repo is OpenStack extension for cloudlet. Therefore, you need to install
OpenStack and [cloudlet
libary](https://github.com/cmusatyalab/elijah-provisioning) before installing
this extension. Since installing OpenStack is not trivial, we recommend
[DevStack](http://devstack.org/), which provides a set of script to quickly
install and test OpenStack. And for cloudlet library, we provide [fabric
script](http://www.fabfile.org/en/latest/) to help you install. If you already
installed cloudlet library, please start from 3. Or if you already have running
OpenStack, please start with "Installation (on running OpenStack)".

1. Prepare [Ubuntu 14.04 64bit](http://releases.ubuntu.com/14.04/ubuntu-14.04.1-desktop-amd64.iso)

  For those we have Ubuntu 12.04 LTS, we provide [Grizzly
  version](https://github.com/cmusatyalab/elijah-openstack/tree/grizzly). But
  we strongly recommend using Ubuntu 14.04 LTS and Icehouse.


2. Install cloudlet library

    > $ cd ~  
    > $ sudo apt-get install git openssh-server fabric git  
    > $ git clone https://github.com/cmusatyalab/elijah-provisioning  
    > $ cd elijah-provisioning  
    > $ fab localhost install  
    > (Enter password of your account)  

    For more details and troubleshooting, please read [elijah-provisioning
    repo](https://github.com/cmusatyalab/elijah-provisioning).


3. Install OpenStack using DevStack (This instruction simply follows [DevStack
guidance](http://devstack.org/guides/single-machine.html)).

    > $ cd ~  
    > $ adduser stack  
    > $ git clone https://github.com/openstack-dev/devstack.git  
    > $ sudo echo "stack ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers  
    > $ cd devstack  
    > $ cp samples/local.conf local.conf  
    > (Modify configuration if you need. Details are at [here](http://devstack.org/guides/single-machine.html)).  
    > $ ./stack.sh  

    Please make sure that all the functions of OpenStack is working by
    connecting to OpenStack Web interface


4. Finally, install cloudlet OpenStack extension

    > $ cd ~  
    > $ git clone https://github.com/cmusatyalab/elijah-openstack  
    > $ cd elijah-openstack  
    > $ fab localhost devstack_single_machine  
    > (Enter password of your account)  

    After successful installation, please restart OpenStack to reflect changes.

    > (Restart you devstack)  
    > $ ./unstack  
    > $ ./rejoin-stack.sh  
    > (Sometime, you need to manually restart apache2 and keystone-all)  

    This fabric script will check cloudlet library version as well as OpenStack
    installation, and just place relevant files at right directories.  It
    **does not change any existing OpenStack code**, but designed to be purely
    pluggable extension, so you can revert back to original state by reversing
    the installation steps. We instantiate our feature by chaging nova
    configuration file at /etc/nova/nova.conf



Installation (on working Openstack)
-----------------------------------

If you have already running OpenStack, please follow this instruction.

1. At a control node

  - Cloudlet provisioning (Rapid VM provisoning)

        > $ sudo fab localhost provisioning_control  

  - (Optional) Cloudlet discovery (under development. See at
      [elijah-discovery](https://github.com/cmusatyalab/elijah-discovery-basic))

        > $ sudo fab localhost discovery_control  


2. At compute nodes: 

  For Cloudlet provisioning, you need to install Cloudlet library at every compute node.
  Change IP addresses of your OpenStack machine at the **fabric.py** file. 

    > (At fabric.py file)  
    > compute_nodes = [  
    >     # ('ssh-account@domain name of compute node')  
    >     ('krha@sleet.elijah.cs.cmu.edu')  
    >     ..  
    >     ]  

  Then, run the script.

    > $ fab remote provisioning_compute  



How to use
-----------

If the installation is successful, you will see a new panel at project tab as
below.  
![OpenStack cloudlet extension dashboard](https://github.com/cmusatyalab/elijah-openstack/blob/icehouse/doc/screenshot/cloudlet_dashboard_icehouse.png?raw=true)
Or you can check cloudlet extension by listing available OpenStack extension
using standard OpenStack REST API.

Then, you can import [Sample Base
VM](https://storage.cmusatyalab.org/cloudlet-vm/precise-baseVM.zip) using
"Import Base VM".  
![Import Base VM](https://github.com/cmusatyalab/elijah-openstack/blob/icehouse/doc/screenshot/import_basevm.png?raw=true)

To resume Base VM, please use "Resume Base VM" button at Images table, and use
"Create VM overlay" button when you ready to create VM overlay from the resumed
VM. Then it will create _VM overlay_ as belows: 
![Creating VM overlay](https://github.com/cmusatyalab/elijah-openstack/blob/icehouse/doc/screenshot/creating_vm_overlay.png?raw=true)
After finishing creating VM overlay (this process can take a long time), you
can download VM overlay using "Download VM overlay" button.

To perform VM synthesis, please use "Start VM Synthesis" button at Instance
table. You need to input URL of the VM overlay you just downloaded.
![Start Vm Synthesis](https://github.com/cmusatyalab/elijah-openstack/blob/icehouse/doc/screenshot/vm_synthesis.png?raw=true)


Alternatively, you can use command line client program at at
./client/nova_client.py 



TroubleShooting
-----------------

If you have any problem after installing Cloudlet extension, please follow
below steps to narrow the problem.


1. Restart Cloudlet related services one-by-one to make sure successful installation

  > $ sudo service nova-compute restart  
  > $ sudo service nova-api restart  
  > $ sudo service nova-scheduler restart  
  > $ sudo service apache2 restart  

2. Check status of OpenStack after restarting services

  > $ sudo nova-manage service list  
  > Binary           Host                                 Zone             Status     State Updated_At  
  > nova-conductor   krha-cloudlet                        internal         enabled    :-)   2014-05-04 15:32:54  
  > nova-network     krha-cloudlet                        internal         enabled    :-)   2014-05-04 15:32:54  
  > nova-consoleauth krha-cloudlet                        internal         enabled    :-)   2014-05-04 15:32:54  
  > nova-scheduler   krha-cloudlet                        internal         enabled    :-)   2014-05-04 15:32:44  
  > nova-cert        krha-cloudlet                        internal         enabled    :-)   2014-05-04 15:32:54  
  > nova-compute     krha-cloudlet                        nova             enabled    :-)   2014-05-04 15:32:54  
  > $

  If any service is not running, it's time to look at the detail
  error message in log file. Log files are located at ``/var/log/nova``.


3. If you still have problem in using Dashboard even though everything nova
   related service is successfully running, then it's mostly Dashboard problem. We can debug it by
   manually running dashboard in debug mode. In OpenStack Grizzly version,
   Dashboard's web service code (Django) is located at
   /usr/share/openstack-dashbaord

   You first need to turn on the debug configuration on Django

   > $ cd /usr/share/openstack-dashboard  
   > $ vi ./settings.py

   Change ``DEBUG = False`` to ``DEBUG = True``. Then, turn on the server using specific port

   > $ ./manage.py runserver 0.0.0.0:9090  
   > Validating models...  
   >
   > 0 errors found  
   > Django version 1.4.5, using settings 'openstack_dashboard.settings'  
   > Development server is running at http://0.0.0.0:9090/  
   > Quit the server with CONTROL-C.  
   >

   At this point, you check detail debug messages of Dashboard when you connect 
   __using the specified port (ex. port 9090)__




Current Limitations
------------

* _Early start optimization_ is turned off

  Early start optimization start VM even before having the memory snapshot of
  the VM. Therefore, it might reject socket connection for the first several
  seconds. We'll update a workaround soon.

