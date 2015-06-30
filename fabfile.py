from __future__ import with_statement
import os

from fabric.api import *
from fabric.operations import *
from fabric.contrib import *
from fabric.context_managers import cd
from tempfile import NamedTemporaryFile
from distutils.version import LooseVersion


# your configuration
control_node = ['localhost']
compute_node_list = ['krha@cloudlet.krha.kr']


# constant
CLOUDLET_PROVISIONING_REPO = "https://github.com/cmusatyalab/elijah-provisioning.git"
NOVA_PACKAGE_PATH = "/usr/lib/python2.7/dist-packages/nova"
NOVA_CONF_PATH = "/etc/nova/nova.conf"
NOVA_COMPUTE_CONF_PATH = "/etc/nova/nova-compute.conf"
DASHBOARD_PROJECT_PATH = "/usr/share/openstack-dashboard/openstack_dashboard/dashboards/project"
DASHBOARD_SETTING_FILE = "/usr/share/openstack-dashboard/openstack_dashboard/dashboards/project/dashboard.py"


def _replace_configuration(filepath, option_key, option_value, insert_at=1):
    """ replace or insert new compute manager configuration
    Cannot use append method since compute_manager option does not effective
    at last line (probably nova configuration bug).
    """
    original_mode = oct(os.stat(filepath).st_mode)[-3:]
    original_uid = os.stat(filepath).st_uid
    original_gid = os.stat(filepath).st_gid
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
            new_config.append("%s=%s" % (option_key, option_value))

    temp_file_name = NamedTemporaryFile(prefix=os.path.basename(filepath)
            + "-cloudlet-tmp").name
    open(temp_file_name, "w+").write('\n'.join(new_config))
    files.upload_template(
        temp_file_name, filepath, use_sudo=True, mode=original_mode
    )
    os.remove(temp_file_name)
    sudo("chown %s:%s %s" % (original_uid, original_gid, filepath))


def deploy_cloudlet_api():
    global NOVA_PACKAGE_PATH

    ext_file = os.path.abspath("./api/cloudlet.py")
    api_file = os.path.abspath("./api/cloudlet_api.py")
    ext_lib_dir = os.path.join(NOVA_PACKAGE_PATH,
            "api/openstack/compute/contrib/")
    api_lib_dir = os.path.join(NOVA_PACKAGE_PATH, "compute/")

    deploy_files = [
            (ext_file, ext_lib_dir),
            (api_file, api_lib_dir),
            ]

    # deploy files
    for (src_file, target_dir) in deploy_files:
        dest_filepath = os.path.join(target_dir, os.path.basename(src_file))
        if put(src_file, dest_filepath, use_sudo=True, mode=0644).failed:
            abort("Cannot copy %s to %s" % (src_file, lib_dir))

    sudo("service nova-api restart", shell=False)


def deploy_compute_manager():
    global NOVA_PACKAGE_PATH
    global NOVA_CONF_PATH
    global NOVA_COMPUTE_CONF_PATH

    manager_file = os.path.abspath("./compute/cloudlet_manager.py")
    manager_lib_dir = os.path.join(NOVA_PACKAGE_PATH, "compute/")
    libvirt_driver = os.path.abspath("./compute/cloudlet_driver.py")
    libvirt_driver_dir = os.path.join(NOVA_PACKAGE_PATH, "virt/libvirt/")

    deploy_files = [
            (manager_file, manager_lib_dir),
            (libvirt_driver, libvirt_driver_dir),
            ]

    if files.exists(NOVA_CONF_PATH, use_sudo=True) is False:
        abort("Cannot find nova conf file at %s\n" % NOVA_CONF_PATH)
    if files.exists(NOVA_COMPUTE_CONF_PATH, use_sudo=True) is False:
        abort("Cannot find nova-compute conf file at %s\n" % NOVA_CONF_PATH)

    # use custom compute manager inherited from nova-compute manager
    _replace_configuration(NOVA_CONF_PATH, "compute_manager",\
            "nova.compute.cloudlet_manager.CloudletComputeManager")

    # use custom driver inherited from libvitDriver
    _replace_configuration(NOVA_CONF_PATH, "compute_driver",\
            "nova.virt.libvirt.cloudlet_driver.CloudletDriver")
    _replace_configuration(NOVA_COMPUTE_CONF_PATH, "compute_driver",\
            "nova.virt.libvirt.cloudlet_driver.CloudletDriver")

    # use specific CPU-mode
    _replace_configuration(NOVA_CONF_PATH, "libvirt_cpu_mode",\
            "custom", insert_at=-1)
    _replace_configuration(NOVA_CONF_PATH, "libvirt_cpu_model",\
            "core2due", insert_at=-1)

    # copy files
    for (src_file, target_dir) in deploy_files:
        dest_filepath = os.path.join(target_dir, os.path.basename(src_file))
        if put(src_file, dest_filepath, use_sudo=True, mode=0644).failed:
            abort("Cannot copy %s to %s" % (src_file, lib_dir))

    sudo("service nova-compute restart", shell=False)


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
    with hide("stderr"):
        output = sudo("nova-manage service list | grep %s" % hostname)
        if output.failed == True or output.find("XXX") != -1:
            msg = "OpenStack is not fully functioning.\n"
            msg += "Check the service with 'nova-manage service list' command.\n\n"
            msg += output
            abort(msg)


def check_VM_synthesis_package():
    if run("cloudlet --version").failed:
        msg = "Cannot find cloudlet-provisioning module.\n"
        msg += "Install it from %s" % CLOUDLET_PROVISIONING_REPO
        abort(msg)

    # version checking
    cmd = "cloudlet --version | awk '{{print $3}}'"
    cloudlet_version = run(cmd)
    MIN_CLOUDLET_VERSION = "0.9.3"
    if LooseVersion(cloudlet_version) < LooseVersion(MIN_CLOUDLET_VERSION):
        msg = "Upgrade cloudlet module at %s (supporting since %s)." % (
            CLOUDLET_PROVISIONING_REPO, MIN_CLOUDLET_VERSION)
        abort(msg)

    else:
        msg = "Cloudlet library exists. Skip installing cloudlet library"
        sys.stdout.write(msg)


def set_kilo_version():
    """DevStack uses the latest version of OpenStack module,
    rather than the released version. Since the latest update can change
    internal API, we use a released version for nova module:
        https://github.com/openstack/nova/releases/tag/2015.1.0
    """
    global NOVA_PACKAGE_PATH

    with cd(NOVA_PACKAGE_PATH):
        result = run("git checkout 8397b6464af520903f546ce4c6d51a2eb5b4c8a8")


def deploy_dashboard():
    global DASHBOARD_PROJECT_PATH
    global DASHBOARD_SETTING_FILE

    # deploy files
    src_dir = os.path.abspath("./dashboard/*")
    dest_dir = os.path.join(DASHBOARD_PROJECT_PATH, "cloudlet")
    if files.exists(dest_dir, use_sudo=True) == False:
        sudo("mkdir -p %s" % dest_dir)
    if put(src_dir, dest_dir, use_sudo=True).failed:
        abort("Cannot copy from %s to %s" % (src_dir, link_dir))

    if sudo("grep cloudlet %s" % DASHBOARD_SETTING_FILE).failed:
        cmd = "sed -i '/instances/ s/$/ \"cloudlet\",/' %s" % DASHBOARD_SETTING_FILE
        if sudo(cmd).failed:
            msg = "Cannot update cloudlet panel at dashboard"
            msg += "check file at %s" % DASHBOARD_SETTING_FILE
            abort(msg)
    if sudo("service apache2 restart").failed:
        msg = "Failed to restart apache web server to restart Horizon"
        msg += "Since this is the last step, you can restart web server manually"
        abort(msg)


def qemu_security_mode():
    """set qemu security mode to None to allow custom QEMU
    """
    qemu_conf_file = os.path.join("/", "etc", "libvirt", "qemu.conf")
    if files.exists(qemu_conf_file, use_sudo=True) == False:
        msg = "The system doesn't have QEMU confi file at %s" % qemu_conf_file
        abort(msg)

    # replace "security_driver" to none
    _replace_configuration(
        qemu_conf_file, "security_driver", "\"none\"", insert_at=-1
    )
    # restart libvirtd to reflect changes
    sudo("/etc/init.d/libvirt-bin restart")

    # disable aa-complain /usr/sbin/libvirtd
    if sudo("aa-complain /usr/sbin/libvirtd").failed:
        abort("Cannot exclude /usr/sbin/libvirtd from apparmor")


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
def devstack_single_machine():
    global NOVA_PACKAGE_PATH
    global DASHBOARD_PROJECT_PATH
    global DASHBOARD_SETTING_FILE
    global NOVA_COMPUTE_CONF_PATH

    DASHBOARD_PROJECT_PATH = "/opt/stack/horizon/openstack_dashboard/dashboards/project"
    DASHBOARD_SETTING_FILE = "/opt/stack/horizon/openstack_dashboard/dashboards/project/dashboard.py"
    NOVA_PACKAGE_PATH = "/opt/stack/nova/nova/"
    NOVA_COMPUTE_CONF_PATH = NOVA_CONF_PATH

    check_VM_synthesis_package()
    check_system_requirement()
    with hide('stdout'):
        set_kilo_version()
        deploy_cloudlet_api()
        deploy_compute_manager()
        qemu_security_mode()
        deploy_dashboard()

    sys.stdout.write("[SUCCESS] Finished installation\n")
    sys.stdout.write("You should restart DevStack to activate changes!!\n")
    sys.stdout.write("  1. Terminate using unstack.sh\n")
    sys.stdout.write("  2. Restart using rejoin-stack.sh\n")

