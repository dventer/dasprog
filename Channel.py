import socket
import paramiko
import re
from time import sleep


class Channel(object):
    def __init__(self, hostname=None, username=None, password=None,
                 key=None, jumphost=None):

        self.hostname = hostname
        self.username = username
        self.password = password
        self.key = key
        self.jumphost = jumphost
        self.ssh_session = None
        self.open_channels = set()

    def disconnect(self):
        if self.jumphost is not None:
            self.ssh_session.close()

        for channel in list(self.open_channels):
            channel.close()

        if self.ssh_session is not None:
            self.ssh_session.close()

    def is_connected(self):
        return (False
                if self.get_ssh() is None or self.get_transport() is None
                else self.get_transport().is_active())

    def is_jumphost_connected(self):
        return (False
                if self.jumphost is None
                else self.jumphost.is_connected())

    def get_ssh(self):
        return self.ssh_session

    def get_transport(self):
        return (self.get_ssh().get_transport()
                if self.get_ssh() is not None
                else self.get_ssh())

    def connect(
            self, load_system_keys=False, auto_add_missing_host_keys=True,
            look_for_keys=True, allow_agent=True):
        k = paramiko.RSAKey.from_private_key_file(self.key)
        self.ssh_session = paramiko.SSHClient()

        if load_system_keys:
            self.ssh_session.load_system_host_keys()

        if auto_add_missing_host_keys:
            self.ssh_session.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        sock = None

        if self.jumphost is not None:
            if self.is_jumphost_connected() is False:
                if self.jumphost.connect()[0] is None:
                    raise RuntimeError("Failed to connect to jumphost: %s"
                                       % (self.jumphost.hostname))
            sock = self.jumphost.open_channel_to(self.hostname)

            if sock is None:
                raise RuntimeError("Failed to open channel on jumphost: %s"
                                   % (self.jumphost.hostname))

        try:
            if self.jumphost is None:
                print('Connecting to %s...' % self.hostname)
            else:
                print('[Bastion: %s] Connecting to %s...'
                      % (self.jumphost.hostname, self.hostname))

            self.ssh_session.connect(hostname=self.hostname,
                                     username=self.username,
                                     password=self.password,
                                     pkey= k,
                                     sock=sock,
                                     look_for_keys=look_for_keys,
                                     allow_agent=allow_agent)
            print('connected')

        except paramiko.BadHostKeyException as e:
            print("Server host key could not be validated.\n{0}\n" + format(e))
            return None
        except paramiko.AuthenticationException as e:
            print("Authentication Failed.\n{0}\n" + format(e))
            return None
        except paramiko.SSHException as e:
            print("Unkown Error with SSH Session.\n{0}\n" + format(e))
            return None
        except socket.error as e:
            print("Unknown Socket Error.\n{0}\n" + format(e))
            return None

        return self.ssh_session

    def open_channel_to(self, target_hostname, target_port=22, source_port=22):
        chan = self.get_transport().open_channel("direct-tcpip",
                                                 (target_hostname,
                                                  target_port),
                                                 (self.hostname, source_port))
        self.open_channels.add(chan)

        return chan

    def close_channel(self, chan):
        if chan in self.open_channels:
            self.open_channels.discard(chan)
            return True
        return False

    def cmd(self, command, pattern):

        # if self.jumphost:
        #     if self.is_jumphost_connected():
        #         self.connect()
        #     else:
        #         self.jumphost.connect()
        #         self.connect()


        shell = self.ssh_session.invoke_shell()
        shell.settimeout(20.0)

        if shell is None:
            raise RuntimeError("jumphost.invoke_shell(): returned NoneType")

        shell.settimeout(5.0)

        if isinstance(command, list):
            output = []
            for i in command:
                result = ''
                shell.send(i + '\n')
                while True:
                    while shell.recv_ready():
                        msg = shell.recv(1024)
                        result += msg.decode('utf-8')
                    if re.search(pattern, result.strip()):
                        break
                    else:
                        sleep(.5)
                output.append(result)
            return output
        else:
            shell.send(command + '\n')
            result = ''
            while True:
                try:
                    msg = shell.recv(1024)
                    result += msg.decode('utf-8')
                    #                    sleep(.5)
                    if re.search(pattern, result.strip()):
                        break
                except:
                    print('connection error on method', __name__)
                    break
            return result