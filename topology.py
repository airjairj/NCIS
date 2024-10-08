#!/usr/bin/python
import threading
import random
import time
from mininet.log import setLogLevel, info
from mininet.topo import Topo
from mininet.net import Mininet, CLI
from mininet.node import OVSKernelSwitch, Host
from mininet.link import TCLink, Link
from mininet.node import RemoteController #Controller

class Environment(object):
    def __init__(self):
        "Create a network."
        self.net = Mininet(controller=RemoteController, link=TCLink) #controllore REMOTO
        info("*** Starting controller\n")
        c1 = self.net.addController( 'c1', controller=RemoteController) #Controller aggiunto alla topologia
        
        c1.start()
        info("*** Adding hosts and switches\n")
        self.h1 = self.net.addHost('h1', mac ='00:00:00:00:00:01', ip= '10.0.0.1') #indirizzo MAC e Ip sono opzionali 
        self.h2 = self.net.addHost('h2', mac ='00:00:00:00:00:02', ip= '10.0.0.2')
        self.h3 = self.net.addHost('h3', mac ='00:00:00:00:00:03', ip= '10.0.0.3')

        # OPZIONALE
        self.h4 = self.net.addHost('h4', mac ='00:00:00:00:00:04', ip= '10.0.0.4')
        
        self.cpe1 = self.net.addSwitch('s1', cls=OVSKernelSwitch, protocols='OpenFlow13') #gli switch devono essere di tipo openflow
        self.cpe2 = self.net.addSwitch('s2', cls=OVSKernelSwitch, protocols='OpenFlow13')
        self.cpe3 = self.net.addSwitch('s3', cls=OVSKernelSwitch, protocols='OpenFlow13')
        self.cpe4 = self.net.addSwitch('s4', cls=OVSKernelSwitch, protocols='OpenFlow13')
        info("*** Adding links\n")  
        self.net.addLink(self.h1, self.cpe1, bw=6, delay='0.0025ms') #vanno bene queste bw e questi delay? sono obbligatori?
        self.net.addLink(self.h2, self.cpe2, bw=6, delay='0.0025ms')  
        self.net.addLink(self.cpe1, self.cpe3, bw=3, delay='25ms')
        self.net.addLink(self.cpe2, self.cpe3, bw=3, delay='25ms')
        self.net.addLink(self.cpe3, self.cpe4, bw=3, delay='25ms')
        self.net.addLink(self.cpe4, self.h3, bw=6, delay='0.0025ms')

        # OPZIONALE
        self.net.addLink(self.h4, self.cpe1, bw=6, delay='0.0025ms')


        info("*** Starting network\n")
        self.net.build()
        self.net.start()
        #la topologia del progetto ha:
        #	h1 collegato a s1
        #	s1 collegato al s3
        #	h2 collegato a s2
        #	s2 collegato ad s3
        #	s3 collegato ad s4
        #	h3 collegato ad s4
        
        # OPZIONALE
        #   h4 collegato a s1

...
if __name__ == '__main__':

    setLogLevel('info')
    info('starting the environment\n')
    env = Environment()

    info("*** Running CLI\n")
    CLI(env.net)
