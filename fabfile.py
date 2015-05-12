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
HORIZON_API_PATH = "/usr/share/openstack-dashboard/openstack_dashboard/api"


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


def _replace_compute_manager(filepath, option_key, option_value, insert_at=1):
    """ replace or insert new compute manager configuration
    Cannot use append method since compute_manager option does not effective
    at last line (probably nova configuration bug).
    """
    conf_content = sudo("cat %s" % filepath)
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
        # insert the conf at the first line
        if insert_at == 1:
            new_config.insert(1, "%s=%s" % (option_key, option_value))
        else:
            new_config.insert(-1, "%s=%s" % (option_key, option_value))


    temp_file_name = NamedTemporaryFile(prefix=os.path.basename(filepath)
            + "-cloudlet-tmp").name
    open(temp_file_name, "w+").write('\n'.join(new_config))
    files.upload_template(temp_file_name, filepath, use_sudo=True)
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

    if files.exists(NOVA_CONF_PATH, use_sudo=True) is False:
        abort("Cannot find nova conf file at %s\n" % NOVA_CONF_PATH)
    if files.exists(NOVA_COMPUTE_CONF_PATH, use_sudo=True) is False:
        abort("Cannot find nova-compute conf file at %s\n" % NOVA_CONF_PATH)

    # use custom compute manager inherited from nova-compute manager
    _replace_compute_manager(NOVA_CONF_PATH, "compute_manager",\
            "nova.compute.cloudlet_manager.CloudletComputeManager")

    # use custom driver inherited from libvitDriver
    _replace_compute_manager(NOVA_CONF_PATH, "compute_driver",\
            "nova.virt.libvirt.cloudlet_driver.CloudletDriver")
    _replace_compute_manager(NOVA_COMPUTE_CONF_PATH, "compute_driver",\
            "nova.virt.libvirt.cloudlet_driver.CloudletDriver")

    # use specific CPU-mode
    _replace_compute_manager(NOVA_CONF_PATH, "libvirt_cpu_mode",\
            "custom", insert_at=-1)
    _replace_compute_manager(NOVA_CONF_PATH, "libvirt_cpu_model",\
            "core2due", insert_at=-1)

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
    msg = "Tested only Ubuntu 12.04/14.04 LTS\n"
    msg += "But the current distribution isn't"

    # OS distribution
    cmd = "cat /etc/lsb-release | grep DISTRIB_CODENAME | awk -F'=' '{print $2}'"
    with settings(hide('everything'), warn_only=True):
        result = run(cmd).lower()
        if result != "precise" and result != "trusty":
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
    global HORIZON_API_PATH

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
    if sudo("service apache2 restart").failed:
        msg = "Failed to restart apache web server to restart Horizon"
        msg += "Since this is the last step, you can restart web server manually"
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

    # disable aa-complain /usr/lib/libvirt/virt-aa-helper
    if sudo("aa-complain /usr/lib/libvirt/virt-aa-helper").failed:
        abort("Cannot exclude virt-aa-helper from apparmor")


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
        #check_system_requirement()
        deploy_cloudlet_api()
        deploy_compute_manager()
        deploy_svirt()
        #deploy_dashboard()
    sys.stdout.write("[SUCCESS] Finished installation\n")


@task
def provisioning_compute():
    check_VM_synthesis_package()
    with hide('stdout'):
        check_system_requirement()
        deploy_cloudlet_api()
        deploy_compute_manager()
        deploy_svirt()
    sys.stdout.write("[SUCCESS] Finished installation\n")


@task
def devstack_single_machine():
    global PYTHON_LIBRARY_ROOT
    global DASHBOARD_PROJECT_PATH
    global DASHBOARD_SETTING_FILE
    global HORIZON_API_PATH
    global NOVA_COMPUTE_CONF_PATH

    DASHBOARD_PROJECT_PATH = "/opt/stack/horizon/openstack_dashboard/dashboards/project"
    DASHBOARD_SETTING_FILE = "/opt/stack/horizon/openstack_dashboard/dashboards/project/dashboard.py"
    HORIZON_API_PATH = "/opt/stack/horizon/openstack_dashboard/api"
    PYTHON_LIBRARY_ROOT = "/opt/stack/nova/"
    NOVA_COMPUTE_CONF_PATH = NOVA_CONF_PATH

    #deploy_compute_manager()
    provisioning_control()
    sys.stdout.write("You should restart DevStack to activate changes!!\n")
    sys.stdout.write("  1. Terminate using unstack.sh\n")
    sys.stdout.write("  2. Restart using rejoin-stack.sh\n")

