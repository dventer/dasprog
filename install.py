from channel import Channel
from time import sleep
from multiprocessing import Process
import os

wr = open('output.txt', 'a')
user= 'upj'
masterIP= '172.16.21.170'
bastion = Channel('jump-host', username=user, key='.ssh/key')
master = Channel('k8s-master', username=user, key='.ssh/key', jumphost=bastion)
worker = Channel('k8s-worker', username=user, key='.ssh/key', jumphost=bastion)
pattern = f'{user}@\S+\$$'
def installPackageMaster():
    os.system('clear')
    msg = 'Please wait, while installing package at Master Node...\n\n'
    command = ['sudo apt-get update -y && sudo apt-get upgrade -y','sudo apt-get install docker.io -y',
        'echo "deb  http://apt.kubernetes.io/  kubernetes-xenial  main" | sudo tee /etc/apt/sources.list.d/kubernetes.list',
        'curl -s https://packages.cloud.google.com/apt/doc/apt-key.gpg | sudo apt-key add -','sudo apt-get update -y',
        'sudo apt-get install -y kubeadm=1.17.1-00 kubelet=1.17.1-00 kubectl=1.17.1-00',
        'sudo apt-mark hold kubelet kubeadm kubectl', 'sudo systemctl enable docker && sudo systemctl start docker',
        'sudo systemctl enable kubelet && sudo systemctl start kubelet']
    result = master.cmd(command, pattern=pattern, message=msg)
    for i in result:
        wr.write(i)

def installPackageWorker():
    os.system('clear')
    msg = 'Please wait, while installing package at Worker Node...\n\n'
    command = ['sudo apt-get update -y && sudo apt-get upgrade -y','sudo apt-get install docker.io -y',
        'echo "deb  http://apt.kubernetes.io/  kubernetes-xenial  main" | sudo tee /etc/apt/sources.list.d/kubernetes.list',
        'curl -s https://packages.cloud.google.com/apt/doc/apt-key.gpg | sudo apt-key add -','sudo apt-get update -y',
        'sudo apt-get install -y kubeadm=1.17.1-00 kubelet=1.17.1-00 kubectl=1.17.1-00',
        'sudo systemctl enable docker && sudo systemctl start docker',
        'sudo systemctl enable kubelet && sudo systemctl start kubelet', 'sudo apt-mark hold kubelet kubeadm kubectl']
    result = worker.cmd(command, pattern=pattern, message=msg)
    for i in result:
        wr.write(i)

def bootstrapMaster():
    os.system('clear')
    msg = 'Please wait, while bootstrap Master Node...\n\n'
    command= ['wget https://tinyurl.com/yb4xturm -O rbac-kdd.yaml', f'echo "{masterIP} k8s-master" | sudo tee -a /etc/hosts',
              'wget https://docs.projectcalico.org/manifests/calico.yaml',
              'curl https://raw.githubusercontent.com/dventer/dasprog/master/kubeadm/kubeadm-init.yaml | tee kubeadm-init.yaml',
              'sudo kubeadm init --config=kubeadm-init.yaml --upload-certs | tee kubeadm-init.out',
              'mkdir -p $HOME/.kube','sudo cp -i /etc/kubernetes/admin.conf $HOME/.kube/config',
              'sudo chown $(id -u):$(id -g) $HOME/.kube/config','kubectl apply -f rbac-kdd.yaml',
              'kubectl apply -f calico.yaml']
    result = master.cmd(command, pattern=pattern, message=msg)
    for i in result:
        wr.write(i)
    while True:
        state = master.cmd(["kubectl get node | grep master | awk '{print $2}'"], pattern=pattern)
        print('Wait until Master Node is Ready...')
        if state[0].splitlines()[-2].strip() == 'Ready':
            print(f'Master Node status is Ready Now...')
            break
        sleep(4)
        os.system('clear')
    bootstrapWorker()


def bootstrapWorker():
    msg = 'Please wait, while bootstrap Worker Node...\n\n'
    ret = ["sudo kubeadm token list | grep authentication | awk '{print $1}'",
       "openssl x509 -pubkey -in /etc/kubernetes/pki/ca.crt | \
       openssl rsa -pubin -outform der 2>/dev/null | openssl dgst -sha256 -hex | sed 's/^.* //'"]
    token_cert = master.cmd(ret, pattern=pattern, message=msg)
    TOKEN = token_cert[0].splitlines()[-2]
    CERT = token_cert[1].splitlines()[-2]
    command = [f'echo "{masterIP} k8s-master" | sudo tee -a /etc/hosts',
               f'sudo kubeadm join k8s-master:6443 --token {TOKEN} --discovery-token-ca-cert-hash sha256:{CERT}']
    result = worker.cmd(command, pattern=pattern, message=msg)
    for i in result:
        wr.write(i)
    os.system('clear')
    while True:
        state = master.cmd(["kubectl get node | grep worker | awk '{print $2}'"], pattern=pattern)
        print('Wait until Worker Node is Ready...')
        if state[0].splitlines()[-2].strip() == 'Ready':
            print('Worker Node status is Ready Now...')
            break
        sleep(4)
        os.system('clear')
    ingressInstall()

def ingressInstall():
    msg = 'Please wait, while installing Loadbalancer and Ingress Controller...\n\n'
    command = ['wget https://get.helm.sh/helm-v3.2.0-linux-amd64.tar.gz',
               'tar -zxvf helm-v3.2.0-linux-amd64.tar.gz',
               'sudo mv linux-amd64/helm /usr/local/bin/helm',
               'helm repo add stable https://kubernetes-charts.storage.googleapis.com',
               'helm repo update', 'helm install metallb stable/metallb --namespace kube-system \
  --set configInline.address-pools[0].name=default \
  --set configInline.address-pools[0].protocol=layer2 \
  --set configInline.address-pools[0].addresses[0]=172.16.21.174-172.16.21.174',
               'helm install nginx-ingress stable/nginx-ingress --namespace kube-system']
    result = master.cmd(command,pattern, message=msg)
    os.system('clear')
    checkLB = ["kubectl get deployment metallb-controller -n kube-system | awk '{print $4}'"]
    checkIngress = ["kubectl -n kube-system get deployment nginx-ingress-controller | awk '{print $4}'"]
    while True:
        resultLB = master.cmd(checkLB,pattern=pattern)[0].splitlines()[-2]
        resultIngress = master.cmd(checkIngress,pattern=pattern)[0].splitlines()[-2]
        print('Check Ingress Controller Deployment...')
        if resultLB.strip() == '1' and resultIngress.strip() == '1':
            print('Ingress Controller Deployment Finish...')
            break
        sleep(2)
        os.system('clear')
    for i in result:
        wr.write(i)
    Deployment()

def Deployment():
    print('Please wait, while deploying our application...\n\n')
    command = ['kubectl create -f https://raw.githubusercontent.com/dventer/dasprog/master/deployment/ingress.yaml',
               'kubectl create -f https://raw.githubusercontent.com/dventer/dasprog/master/deployment/service.yaml',
               'kubectl create -f https://raw.githubusercontent.com/dventer/dasprog/master/deployment/deployment.yaml']
    result = master.cmd(command, pattern=pattern)
    os.system('clear')
    checkDeployment = ["kubectl get deployment | awk '{print $4}'"]
    while True:
        Deployment = master.cmd(checkDeployment, pattern=pattern)[0].splitlines()
        print('Deploy web app for http://tugas.jefri & http://tugas.adventer')
        if Deployment[-2] == '2' and Deployment[-3] == '2':
            os.system('clear')
            print('''
            http://tugas.jefri & http://tugas.adventer Sudah bisa diakses
            Silahkan tambahkan ini di konfigurasi hosts anda
            103.78.209.133  tugas.jefri
            103.78.209.133  tugas.adventer
            ''')
            break
        sleep(2)
        os.system('clear')
    for i in result:
        wr.write(i)


if __name__ == '__main__':
    p1 = Process(target=installPackageMaster())
    p1.start()
    p2 = Process(target=installPackageWorker())
    p2.start()
    bootstrapMaster()



