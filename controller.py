from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet
from ryu.lib.packet import ether_types
import threading
import time

class SimpleSwitch13(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]
    def __init__(self, *args, **kwargs):
        super(SimpleSwitch13, self).__init__(*args, **kwargs)
        self.mac_to_port = {}

        self.datapaths = {}
        self.port_stats = {}
        self.threshold = 2000000 # soglia di throughput (bit/secondo)

        self.thread = threading.Thread(target=self._monitor, args=(self.datapaths))
        self.thread.start()

    # funzione per il monitoraggio
    def _monitor(self, datap):
        while True:
            for dp in datap.values():
                self._requests_stats(dp)
            time.sleep(10)

    # Questa funzione serve per richiedere le statistiche ad ogni switch attivo.
    def _request_stats(self, datapath): # *****
        self.logger.debug('Richiesta statistiche per lo switch: %016x', datapath.id)
        ofproto= datapath.ofproto #ofproto recuper la specifiche del protocollo OpenFlow associate al datapath
        parser= datapath.ofproto_parser

        req = parser.OFPPortStatsRequest(datapath, 0, ofproto.OFPP_ANY) #datapath Ã¨ lo switch a cui Ã¨ inviata la richiesta, 0 Ã¨ un flag non utilizzato, OFPP_ANY indica che si richiedono le statistiche per ogni porta dello swich datapath
        datapath.send_msg(req)


    # *****
    # Questa funzione serve a gestire le risposte ricevute dagli switch
    @set_ev_cls(ofp_event.EventOFPPortStatsReply,MAIN_DISPATCHER) #decorator: serve ad associare la funzione all'evento EventOFPPortStatsReply, cioÃ¨ la ricezione delle statistiche da uno switch
    def _port_stats_reply_handler(self,ev): #ev Ã¨ l'oggetto evento che contiene il messaggio di risposta. Questo parametro viene passato automaticamente dal framework ryu quando si verifica l'evento. ****Vedi Nota 1 su notion per la documentazione****.

        # Estrazione dei dati:
        body= ev.msg.body 		# lista di statistiche per ogni porta dello switch
        datapath= ev.msg.datapath	# lo switch da cui viene la risposta
        dpid= datapath.id		# id dello switch (datapath) a cui si riferiscono le statistiche

        self.port_stats.setdefault(dpid,{})	# se non esiste giÃ  una voce per dpid nel dizionario self.port_stats, viene creata una nuova voce associata a un dizionario vuoto. questo dizionario verrÃ  utilizzato per memorizzare le statistiche delle porte per quel particolare switch

        # Elaborazione delle statistiche per ciascuna porta
        for stat in body:
            port_no = stat.port_no # Ã¨ il numero della porta a cui si riferisce la statistica attuale

            # Verifica se le statistiche per la porta port_no sono giÃ  state memorizzate. Se no, vengono inizializzate.
            if port_no not in self.port_stats[dpid]:
                self.port_stats[dpid][port_no] ={  # Memorizziamo:
                    'rx_bytes': stat.rx_bytes, # - numero di byte ricevuti
                    'tx_bytes': stat.tx_bytes, # - numero di byte trasmessi
                    'timestamp': time.time()   # - timestamp che indica il tempo attuale: servirÃ  per calcolare il throughput in future iterazioni
                    }
            else:
                prev_stats= self.port_stats[dpid][port_no] # statistiche precedentemente salvate per quella porta.
                curr_time=time.time() #tempo attuale
                time_diff=curr_time - prev_stats['timestamp'] #differenza tra tempo attuale e timestamp precedente
                # Calcolo del throughput:
                rx_throughput = (stat.rx - prev_stats['rx_bytes'])
                tx_throughput = (stat.tx_bytes - prev_stats['tx_bytes'])

                self.logger.info('Switch %s, Porta %s - RX Throughput_ %f bytes/sec, TX Throughput: %f bytes/sec', dpid, port_no, rx_throughput, tx_throughput)
                # Verifica delle soglie (ancora dobbiamo scegliere la soglia)
                if rx_throughput> self.threshold or tx_throughput>self.threshold:
                    self.logger.warning('Allarme! Switch %s, Porta %s ha superato la soglia con throughput: RX=%f, TX=%f',dpid,port_no,rx_throughput,tx_throughput)
                # Aggiornamento delle statistiche per la prossima iterazione:
                self.port_stats[dpid][port_no]['rx_bytes']=stat.rx_bytes
                self.port_stats[dpid][port_no]['tx_bytes']=stat.tx_bytes
                self.port_stats[dpid][port_no]['timestamp']=curr_time

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # install table-miss flow entry
        #
        # We specify NO BUFFER to max_len of the output action due to
        # OVS bug. At this moment, if we specify a lesser number, e.g.,
        # 128, OVS will send Packet-In with invalid buffer_id and
        # truncated packet data. In that case, we cannot output packets
        # correctly.  The bug has been fixed in OVS v2.1.0.
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                        ofproto.OFPCML_NO_BUFFER)]
        self.add_flow(datapath, 0, match, actions)

    def add_flow(self, datapath, priority, match, actions, buffer_id=None):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS,
                                            actions)]
        if buffer_id:
            mod = parser.OFPFlowMod(datapath=datapath, buffer_id=buffer_id,
                                    priority=priority, match=match,
                                    instructions=inst)
        else:
            mod = parser.OFPFlowMod(datapath=datapath, priority=priority,
                                    match=match, instructions=inst)
        datapath.send_msg(mod)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        # If you hit this you might want to increase
        # the "miss_send_length" of your switch
        if ev.msg.msg_len < ev.msg.total_len:
            self.logger.debug("packet truncated: only %s of %s bytes",
                            ev.msg.msg_len, ev.msg.total_len)
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match['in_port']

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]

        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            # ignore lldp packet
            return
        dst = eth.dst
        src = eth.src

        dpid = datapath.id
        self.mac_to_port.setdefault(dpid, {})

        self.logger.info("packet in %s %s %s %s", dpid, src, dst, in_port)

        # learn a mac address to avoid FLOOD next time.
        self.mac_to_port[dpid][src] = in_port

        if dst in self.mac_to_port[dpid]:
            out_port = self.mac_to_port[dpid][dst]
        else:
            out_port = ofproto.OFPP_FLOOD

        actions = [parser.OFPActionOutput(out_port)]

        # install a flow to avoid packet_in next time
        if out_port != ofproto.OFPP_FLOOD:
            match = parser.OFPMatch(in_port=in_port, eth_dst=dst, eth_src=src)
            # verify if we have a valid buffer_id, if yes avoid to send both
            # flow_mod & packet_out
            if msg.buffer_id != ofproto.OFP_NO_BUFFER:
                self.add_flow(datapath, 1, match, actions, msg.buffer_id)
                return
            else:
                self.add_flow(datapath, 1, match, actions)
        data = None
        if msg.buffer_id == ofproto.OFP_NO_BUFFER:
            data = msg.data

        out = parser.OFPPacketOut(datapath=datapath, buffer_id=msg.buffer_id,
                                in_port=in_port, actions=actions, data=data)
        datapath.send_msg(out)
