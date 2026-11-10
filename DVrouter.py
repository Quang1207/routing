
import json
from router import Router
from packet import Packet

INFINITY = 16


class DVrouter(Router):

    def __init__(self, addr, heartbeat_time):
        Router.__init__(self, addr)
        self.heartbeat_time = heartbeat_time
        self.last_time = 0

        self.link_costs = {}
        self.port_to_addr = {}

        self.dv = {self.addr: 0}
        self.forwarding_table = {}
        self.neighbor_dvs = {}

    def handle_packet(self, port, packet):
        if packet.is_traceroute:
            dst = packet.dst_addr
            if dst in self.forwarding_table:
                out_port = self.forwarding_table[dst]
                if out_port is not None:
                    self.send(out_port, packet)
        else:
            sender = packet.src_addr
            received_dv = json.loads(packet.content)

            self.neighbor_dvs[sender] = received_dv

            if self._recompute():
                self._broadcast_dv()

    def handle_new_link(self, port, endpoint, cost):
        self.link_costs[port] = cost
        self.port_to_addr[port] = endpoint
        self.neighbor_dvs[endpoint] = {}

        if self._recompute():
            self._broadcast_dv()
        else:
            self._broadcast_dv()

    def handle_remove_link(self, port):
        if port in self.link_costs:
            endpoint = self.port_to_addr.pop(port, None)
            self.link_costs.pop(port, None)
            if endpoint in self.neighbor_dvs:
                self.neighbor_dvs.pop(endpoint, None)

            self._recompute()
            self._broadcast_dv()

    def handle_time(self, time_ms):
        if time_ms - self.last_time >= self.heartbeat_time:
            self.last_time = time_ms
            self._broadcast_dv()

    def _recompute(self):
        new_dv = {self.addr: 0}
        new_forwarding_table = {}

        all_dests = set()
        for neighbor in self.port_to_addr.values():
            all_dests.add(neighbor)
        for n_dv in self.neighbor_dvs.values():
            for d in n_dv.keys():
                all_dests.add(d)
        all_dests.discard(self.addr)

        for dst in all_dests:
            min_cost = INFINITY
            best_port = None

            for port, cost in self.link_costs.items():
                neighbor = self.port_to_addr[port]

                if neighbor == dst:
                    if cost < min_cost:
                        min_cost = cost
                        best_port = port

                cost_through_neighbor = self.neighbor_dvs.get(neighbor, {}).get(dst, INFINITY)
                total_cost = cost + cost_through_neighbor
                if total_cost < min_cost:
                    min_cost = total_cost
                    best_port = port

            if min_cost < INFINITY:
                new_dv[dst] = min_cost
                new_forwarding_table[dst] = best_port
            else:
                new_dv[dst] = INFINITY
                new_forwarding_table[dst] = None

        changed = False
        if new_dv != self.dv or new_forwarding_table != self.forwarding_table:
            changed = True

        self.dv = new_dv
        self.forwarding_table = new_forwarding_table
        return changed

    def _broadcast_dv(self):
        for port, neighbor in self.port_to_addr.items():
            poisoned_dv = {}
            for dst, cost in self.dv.items():
                if self.forwarding_table.get(dst) == port and dst != neighbor:
                    poisoned_dv[dst] = INFINITY
                else:
                    poisoned_dv[dst] = cost

            p = Packet(Packet.ROUTING, self.addr, neighbor, content=json.dumps(poisoned_dv))
            self.send(port, p)

    def __repr__(self):
        return f"DVrouter(addr={self.addr}, dv={self.dv}, routes={self.forwarding_table})"
