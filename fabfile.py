from __future__ import with_statement
import os

from fabric.api import *
from fabric.operations import *
from fabric.contrib import *
from fabric.context_managers import cd
from tempfile import NamedTemporaryFile


# your configuration
control_node = ['localhost']
compute_node_list = ['krha@cloudlet.krha.kr']


# constant
CLOUDLET_PROVISIONING_REPO = "https://github.com/cmusatyalab/elijah-provisioning.git"
CLOUDLET_DISCOVERY_REPO = "https://github.com/cmusatyalab/elijah-discovery.git"
PYTHON_LIBRARY_ROOT = "/usr/lib/python2.7/dist-packages"
NOVA_CONF_PATH = "/etc/nova/nova.conf"
NOVA_COMPUTE_CONF_PATH = "/etc/nova/nova-compute.conf"
DASHBOARD_PROJECT_PATH = "/usr/share/openstack-dashboard/openstack_dashboard/dashboards/project"
DASHBOARD_SETTING_FILE = "/usr/share/openstack-dashboard/openstack_dashboard/dashboards/project/dashboard.py"
HOROZIN_API_PATH = "/usr/share/openstack-dashboard/openstack_dashboard/api"


def deploy_cloudlet_api():
    ext_file = os.path.abspath("./api/cloudlet.py")
    api_file = os.path.abspath("./api/cloudlet_api.py")
    ext_lib_dir = os.path.join(PYTHON_LIBRARY_ROOT,
            "nova/api/openstack/compute/contrib/")
    api_lib_dir = os.path.join(PYTHON_LIBRARY_ROOT, "nova/compute/")

    deploy_files = [
            (ext_file, ext_lib_dir),
            (api_file, api_lib_dir),
            ]

    # deploy files
    # TODO: use python package installer.
    for (src_file, target_dir) in deploy_files:
        dest_filepath = os.path.join(target_dir, os.path.basename(src_file))
        if put(src_file, dest_filepath, use_sudo=True, mode=0644).failed:
            abort("Cannot copy %s to %s" % (src_file, lib_dir))

    sudo("service nova-api restart", shell=False)


def _replace_compute_manager(nova_conf_path, option_key, option_value):
    """ replace or insert new compute manager configuration
    Cannot use append method since compute_manager option does not effective
    at last line (probably nova configuration bug).
    """
    conf_content = sudo("cat %s" % nova_conf_path)
    new_config = list()

    # replace if option_key is exist
    is_replaced = False
    for oneline in conf_content.split("\n"):
        key = oneline.strip().split("=")[0].strip()
        if key == option_key:
            value = oneline.strip().split("=")[-1].strip()
            if value is not option_value:
                new_config.append("%s=%s" % (option_key, option_value))
                is_replaced = True
        else:
            new_config.append(oneline.replace("\r", ""))
    if is_replaced is False:
        # insert it at first line
        new_config.insert(1, "%s=%s" % (option_key, option_value))
    temp_file_name = NamedTemporaryFile(prefix=os.path.basename(nova_conf_path)
            + "-cloudlet-tmp").name
    open(temp_file_name, "w+").write('\n'.join(new_config))
    files.upload_template(temp_file_name, nova_conf_path, use_sudo=True)
    os.remove(temp_file_name)


def deploy_compute_manager():
    global NOVA_CONF_PATH
    global NOVA_COMPUTE_CONF_PATH

    manager_file = os.path.abspath("./compute/cloudlet_manager.py")
    manager_lib_dir = os.path.join(PYTHON_LIBRARY_ROOT, "nova/compute/")
    libvirt_driver = os.path.abspath("./compute/cloudlet_driver.py")
    libvirt_driver_dir = os.path.join(PYTHON_LIBRARY_ROOT, "nova/virt/libvirt/")

    deploy_files = [
            (manager_file, manager_lib_dir),
            (libvirt_driver, libvirt_driver_dir),
            ]

    # use custom compute manager inherited from nova-compute manager
    if files.exists(NOVA_CONF_PATH, use_sudo=True) is False:
        abort("Cannot find nova-compute conf file at %s\n" % NOVA_CONF_PATH)

    option_key = "compute_manager"
    option_value = "nova.compute.cloudlet_manager.CloudletComputeManager"
    _replace_compute_manager(NOVA_CONF_PATH, option_key, option_value)

    # use custom driver inherited from libvitDriver
    command = "sed -i 's/compute_driver=libvirt.LibvirtDriver/compute_driver=libvirt.cloudlet_driver.CloudletDriver/g' %s"\
            % (NOVA_CONF_PATH)
    sudo(command)
    if files.exists(NOVA_COMPUTE_CONF_PATH, use_sudo=True) == True:
        command = "sed -i 's/compute_driver=libvirt.LibvirtDriver/compute_driver=libvirt.cloudlet_driver.CloudletDriver/g' %s"\
                % (NOVA_COMPUTE_CONF_PATH)
        sudo(command)

    # use specific CPU-mode
    CUSTOM_CPU = "custom"
    CUSTOM_CPU_MODEL = "core2duo"
    sudo("sed -i '/^libvirt_cpu_mode=/d' %s" % (NOVA_CONF_PATH))
    sudo("sed -i '$ a libvirt_cpu_mode=%s' %s" % (CUSTOM_CPU, NOVA_CONF_PATH)) 
    sudo("sed -i '/^libvirt_cpu_model=/d' %s" % (NOVA_CONF_PATH))
    sudo("sed -i '$ a libvirt_cpu_model=%s' %s" % (CUSTOM_CPU_MODEL, NOVA_CONF_PATH))

    # copy files
    for (src_file, target_dir) in deploy_files:
        dest_filepath = os.path.join(target_dir, os.path.basename(src_file))
        if put(src_file, dest_filepath, use_sudo=True, mode=0644).failed:
            abort("Cannot copy %s to %s" % (src_file, lib_dir))

    sudo("service nova-compute restart", shell=False)


def deploy_scheduler():
    global NOVA_CONF_PATH

    scheduler_file = os.path.abspath("./compute/cloudlet_manager.py")
    scheduler_lib_dir = os.path.join(PYTHON_LIBRARY_ROOT, "nova/scheduler/")

    deploy_files = [ 
            (scheduler_file, scheduler_lib_dir),
            ]

    # use custom scheduler manager inherited from nova-scheduler manager
    if files.exists(NOVA_CONF_PATH, use_sudo=True) == False:
        abort("Cannot find nova-conf file at %s\n" % NOVA_CONF_PATH)
    option_key = "scheduler_manager"
    option_value = "nova.scheduler.cloudlet_scheduler_manager.CloudletSchedulerManager"
    _replace_compute_manager(NOVA_CONF_PATH, option_key, option_value)


    # copy files
    for (src_file, target_dir) in deploy_files:
        dest_filepath = os.path.join(target_dir, os.path.basename(src_file))
        if put(src_file, dest_filepath, use_sudo=True, mode=0644).failed:
            abort("Cannot copy %s to %s" % (src_file, lib_dir))

    sudo("service nova-scheduler restart", shell=False)


def check_system_requirement():
    msg = "Tested only Ubuntu 12.04 LTS\n"
    msg += "But the current OS is not Ubuntu 12.04 LTS"
    
    # OS version test
    output = run('cat /etc/lsb-release')
    if output.failed == True:
        abort(msg)
    if str(output).find("DISTRIB_RELEASE=12.04") == -1:
        abort(msg)

    # OpenStack installation test
    hostname = sudo('hostname')
    output = sudo("nova-manage service list | grep %s" % hostname)
    if output.failed == True or output.find("XXX") != -1:
        msg = "OpenStack is not fully functioning.\n"
        msg += "Check the service with 'nova-manage service list' command.\n\n"
        msg += output
        abort(msg)


def check_VM_synthesis_package():
    if run("cloudlet --version").failed:
        # install cloudlet library
        temp_repo = '/tmp/cloudlet_repo_temp'
        sudo("rm -rf %s" % temp_repo)
        run("git clone %s %s" % (CLOUDLET_PROVISIONING_REPO, temp_repo))
        with cd(temp_repo):
            if run("fab localhost install").failed:
                msg = "Cannot install cloudlet package.\n"
                msg += "Manually install it downloading from %s" % CLOUDLET_PROVISIONING_REPO
                abort(msg)

        # double check installation
        if run("cloudlet --version").failed:
            abort("Cannot find cloudlet-provisioning package.\nInstall from %s" % CLOUDLET_PROVISIONING_REPO)
    else:
        msg = "Cloudlet library exists. Skip installing cloudlet library"
        sys.stdout.write(msg)
        return


def check_discovery_package():
    if run("cloudlet-discovery --version").failed:
        # install cloudlet library
        temp_repo = '/tmp/cloudlet_discovery_repo_temp'
        sudo("rm -rf %s" % temp_repo)
        run("git clone %s %s" % (CLOUDLET_DISCOVERY_REPO, temp_repo))
        with cd(temp_repo):
            if run("fab localhost install").failed:
                msg = "Cannot install cloudlet-discovery package.\n"
                msg += "Manually install it downloading from %s" % CLOUDLET_DISCOVERY_REPO
                abort(msg)

        # double check installation
        if run("cloudlet --version").failed:
            abort("Cannot find cloudlet-discovery package.\nInstall from %s" % CLOUDLET_DISCOVERY_REPO)
    else:
        msg = "Cloudlet discovery library exists. Skip installing cloudlet discovery library"
        sys.stdout.write(msg)
        return


def deploy_dashboard():
    global DASHBOARD_PROJECT_PATH 
    global DASHBOARD_SETTING_FILE
    global HOROZIN_API_PATH

    # deploy files
    src_dir = os.path.abspath("./dashboard/*")
    dest_dir = os.path.join(DASHBOARD_PROJECT_PATH, "cloudlet")
    if files.exists(dest_dir, use_sudo=True) == False:
        sudo("mkdir -p %s" % dest_dir)
    if put(src_dir, dest_dir, use_sudo=True).failed:
        abort("Cannot copy from %s to %s" % (src_dir, link_dir))

    if sudo("cat %s | grep cloudlet" % DASHBOARD_SETTING_FILE).failed:
        cmd = "sed -i '/instances/ s/$/ \"cloudlet\",/' %s" % DASHBOARD_SETTING_FILE
        if sudo(cmd).failed:
            msg = "Cannot update cloudlet panel at dashboard"
            msg += "check file at %s" % DASHBOARD_SETTING_FILE
            abort(msg)



def deploy_svirt():
    # check apparmor file
    libvirt_svirt_file = "/etc/apparmor.d/abstractions/libvirt-qemu"
    if files.exists(libvirt_svirt_file, use_sudo=True) == False:
        abort("This system does not have libvirt profile for svirt")

    # append additional files that cloudlet uses
    security_rule = open("./svirt-profile", "r").read()
    if files.append(libvirt_svirt_file, security_rule, use_sudo=True) == False:
        abort("Cannot add security profile to libvirt-qemu")


@task
def localhost():
    env.run = local
    env.warn_only = True
    env.hosts = control_node


@task
def remote():
    env.run = run
    env.warn_only = True
    env.hosts = compute_node_list


@task
def discovery_control():
    check_discovery_package()
    with hide('stdout'):
        deploy_scheduler()


@task
def provisioning_control():
    check_VM_synthesis_package()
    with hide('stdout'):
        check_system_requirement()
        deploy_cloudlet_api()
        deploy_compute_manager()
        deploy_svirt()
        deploy_dashboard()

    sys.stdout.write("[SUCCESS] Finished installation")


@task
def provisioning_compute():
    check_VM_synthesis_package()
    with hide('stdout'):
        check_system_requirement()
        deploy_cloudlet_api()
        deploy_compute_manager()
        deploy_svirt()

    sys.stdout.write("[SUCCESS] Finished installation")

