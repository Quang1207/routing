####################################################
# LSrouter.py
# Name: Nguyen Van Quang
# HUID: 24020622
#####################################################

import json
import networkx as nx
from router import Router
from packet import Packet


class LSrouter(Router):
    """Link state routing protocol implementation.

    Add your own class fields and initialization code (e.g. to create forwarding table
    data structures). See the `Router` base class for docstrings of the methods to
    override.
    """

    def __init__(self, addr, heartbeat_time):
        Router.__init__(self, addr)  # Initialize base class - DO NOT REMOVE
        self.heartbeat_time = heartbeat_time
        self.last_time = 0
        
        self.seq_num = 0
        self.link_costs = {}      # {port: cost}
        self.port_to_addr = {}    # {port: neighbor_addr}
        self.addr_to_port = {}    # {neighbor_addr: port}
        self.forwarding_table = {}

        # Bản đồ topology mạng: {node: {'seq': int, 'links': {neighbor: cost}}}
        self.topology = {}

    def handle_packet(self, port, packet):
        """Process incoming packet."""
        if packet.is_traceroute:
            dst = packet.dst_addr
            if dst in self.forwarding_table:
                out_port = self.forwarding_table[dst]
                if out_port is not None:
                    self.send(out_port, packet)
        else:
            lsp_data = json.loads(packet.content)
            src_node = lsp_data['node']
            seq = lsp_data['seq']
            links = lsp_data['links']

            # Chỉ xử lý và flood tiếp nếu LSP có seq lớn hơn thông tin hiện có
            if src_node not in self.topology or seq > self.topology[src_node]['seq']:
                self.topology[src_node] = {'seq': seq, 'links': links}
                
                # Flood gói tin ra tất cả các cổng ngoại trừ cổng vừa nhận được
                for p, neighbor in self.port_to_addr.items():
                    if p != port:
                        self.send(p, Packet(Packet.ROUTING, self.addr, neighbor, content=packet.content))

                self._run_dijkstra()

    def handle_new_link(self, port, endpoint, cost):
        """Handle new link."""
        self.link_costs[port] = cost
        self.port_to_addr[port] = endpoint
        self.addr_to_port[endpoint] = port

        self._broadcast_lsp()
        self._run_dijkstra()

    def handle_remove_link(self, port):
        """Handle removed link."""
        if port in self.link_costs:
            endpoint = self.port_to_addr.pop(port, None)
            self.link_costs.pop(port, None)
            if endpoint in self.addr_to_port:
                self.addr_to_port.pop(endpoint, None)

            self._broadcast_lsp()
            self._run_dijkstra()

    def handle_time(self, time_ms):
        """Handle current time."""
        if time_ms - self.last_time >= self.heartbeat_time:
            self.last_time = time_ms
            self._broadcast_lsp()

    def _broadcast_lsp(self):
        """Tạo Link State Packet của router này và gửi tới tất cả các nút hàng xóm."""
        self.seq_num += 1

        my_links = {}
        for port, cost in self.link_costs.items():
            neighbor = self.port_to_addr[port]
            my_links[neighbor] = cost

        self.topology[self.addr] = {'seq': self.seq_num, 'links': my_links}

        payload = json.dumps({'node': self.addr, 'seq': self.seq_num, 'links': my_links})
        for port, neighbor in self.port_to_addr.items():
            self.send(port, Packet(Packet.ROUTING, self.addr, neighbor, content=payload))

    def _run_dijkstra(self):
        """Dựng đồ thị toàn mạng và tính toán lại bảng chuyển tiếp (Forwarding Table)."""
        G = nx.Graph()

        for node, info in self.topology.items():
            for neighbor, cost in info['links'].items():
                G.add_edge(node, neighbor, weight=cost)

        new_table = {}

        if self.addr in G:
            for target in G.nodes():
                if target == self.addr:
                    continue
                try:
                    path = nx.shortest_path(G, source=self.addr, target=target, weight='weight')
                    if len(path) > 1:
                        next_hop = path[1]
                        if next_hop in self.addr_to_port:
                            new_table[target] = self.addr_to_port[next_hop]
                except nx.NetworkXNoPath:
                    pass

        self.forwarding_table = new_table

    def __repr__(self):
        """Representation for debugging in the network visualizer."""
        return f"LSrouter(addr={self.addr}, routes={self.forwarding_table})"
