def template_access():
    from jinja2 import Environment, FileSystemLoader
    import os, errno
    ssh_config = os.path.expanduser("~/.ssh/config")
    if not os.path.exists(os.path.dirname(ssh_config)):
        try:
            os.makedirs(os.path.dirname(ssh_config))
        except OSError as exc:
            if exc.errno != errno.EEXIST:
                raise
    else:
        if os.path.exists(ssh_config):
            os.replace(ssh_config, f'{ssh_config}.OLD')
    os.chmod('.ssh/key', 0o600)
    user = 'upj'
    keyfile = os.getcwd()+'/.ssh/key'
    env = Environment(loader=FileSystemLoader('.ssh'), trim_blocks=True, lstrip_blocks=True)
    template = env.get_template('config')
    nodes = ['k8s-master','k8s-worker']
    output = template.render(user=user, nodes=nodes, jumphost='jump-host',keyfile=keyfile)
    with os.fdopen(os.open(ssh_config, os.O_WRONLY | os.O_CREAT, 0o400), 'w') as file:
        file.write(output)

template_access()

