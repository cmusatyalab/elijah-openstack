class CreationError(ValueError):

    def __init__(self, node, msg=None):
        if msg is None:
            # Set some default useful error message
            msg = "Failed to create node {}".format(node)
        super(CreationError, self).__init__(msg)
        self.node = node


class UnknownFormatError(ValueError):

    def __init__(self, msg=None):
        if msg is None:
            msg = "Unknown Format Error"
        super(ValueError, self).__init__(msg)


class VMStackCreationError(ValueError):

    def __init__(self, stack_name, msg=None):
        if msg is None:
            # Set some default useful error message
            msg = "Failed to create VM stack {}".format(stack_name)
        super(ValueError, self).__init__(msg)


class OpenStackError(ValueError):

    def __init__(self, msg):
        super(ValueError, self).__init__(msg)


class DockerContainerError(ValueError):

    def __init__(self, msg):
        super(ValueError, self).__init__(msg)


class InstanceNotFoundError(ValueError):

    def __init__(self, msg):
        super(ValueError, self).__init__(msg)