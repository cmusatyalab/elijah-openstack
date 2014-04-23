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

1. OpenStack installation: This work assumes that you already have working
   OpenStack.  For installation of OpenStack, you can follow the [official
   documentation](http://docs.openstack.org/grizzly/openstack-compute/install/apt/openstack-install-guide-apt-grizzly.pdf).
   Since OpenStack is a collection of multiple semi-independent project, its
   installation is not trivial if you don't have any experience. But once you
   have installed that, cloudlet patch would be simple. Please take a look at
   (my note) for the installation tip.


2. You need extra IP address to allocate IP to the synthesized VM. You can
   still execute VM synthesis using this extension, but can't use a mobile
   device to access to the synthesized VM.

3. The tested platform is Ubuntu 12.04 LTS 64 bits.

4. If you install this OpenStack extension for the purpose of testing Cloudlet
   (VM Synthesis), I would recommend you to play with stand-alone version of
   this work at
   [elijah-cloudlet](https://github.com/cmusatyalab/elijah-provisioning).  That
   is much easier to install and modify since OpenStack is a nontrivial piece
   of software.


Installation
------------

Here we provide a script to apply this extension to the existing OpenStack.
It will install cloudlet library and apply patches for the cloudlet extension.
This patch **does not change any existing source code**, but designed to be
purely pluggable extension, so you can revert back to original state by
reversing the installation steps. We instantiate our feature by specifying custom compute\_manager (and scheduler\_manager for cloudlet-discovery).

1. Install libraries for the fabric script.

	> $ sudo apt-get install git openssh-server fabric


2. Installation at a control node
  - Cloudlet provisioning (Rapid VM provisoning)
	> $ sudo fab localhost provisioning_control

  - Cloudlet discovery (under development. See at [elijah-discovery](https://github.com/cmusatyalab/elijah-discovery-basic))
  	> $ sudo fab localhost discovery_control


3. Installation at compute nodes:
   For Cloudlet provisioning, you need to install Cloudlet extension at every
   compute node.
   
   Change IP addresses of your OpenStack machine at the **fabric.py** file. 

		> (At fabric.py file)
		> compute_nodes = [
		> 		# ('ssh-account@domain name of compute node')
		> 		('krha@sleet.elijah.cs.cmu.edu')
		> 		..
		> 		]

   Then, run the script.

		> $ fab remote provisioning_compute


How to use
-----------

First, if the installation is successful, you should be able to see update
Dashboard as below.  ![OpenStack cloudlet extension
dashboard](https://github.com/cmusatyalab/elijah-openstack/blob/master/doc/screenshot/cloudlet_dashboard.png?raw=true)
Or you can check cloudlet extension by listing available OpenStack extension
using standard OpenStack API.

You can either use Web interface at Dashboard or take a look at
./client/nova_client.py to figure out how to use cloudlet extension API.  We're
currently working on documentation of this extension and will be updated soon
with examples.



Current Limitations
------------

* _Early start optimization_ is turned off

	Early start optimization start VM even before having the memory snapshot of
	the VM. Therefore, it might reject socket connection for the first several
	seconds. We'll update a workaround soon.


