#!/usr/bin/env python3
"""Tests for LLDP interface resolution and reciprocal link reconciliation."""

import unittest
from balenolib.topology.models import Device, Interface, LldpNeighbor
from balenolib.topology.engine import TopologyEngine, normalize_port


class TestLldpInterfaceResolution(unittest.TestCase):

    def test_normalize_port_aliases(self):
        self.assertEqual(normalize_port('XGigabitEthernet0/0/3'), 'xge003')
        self.assertEqual(normalize_port('xge0/0/3'), 'xge003')
        self.assertEqual(normalize_port('GigabitEthernet0/0/1'), 'gi001')
        self.assertEqual(normalize_port('gi0/0/1'), 'gi001')
        self.assertEqual(normalize_port('TwentyFiveGigE0/0/1'), '25ge001')
        self.assertEqual(normalize_port('HundredGigE0/0/1'), '100ge001')

    def test_reciprocal_reconciliation_real_camg_prodemge_scenario(self):
        """Simulates the real case: CORE_CAMG (chassis port 35) and CORE_PRODEMGE (XGE0/0/3)."""
        d_camg = Device(id='camg', hostname='CORE_CAMG', ip='10.43.170.6')
        d_camg.lldp_neighbors.append(LldpNeighbor(
            local_port_num=35,
            local_port_name='35',
            remote_sys_name='CORE_PRODEMGE',
            remote_port_id='XGigabitEthernet0/0/3',
            remote_mgmt_addr='10.43.170.3',
        ))

        d_prodemge = Device(id='prodemge', hostname='CORE_PRODEMGE', ip='10.43.170.3')
        d_prodemge.lldp_neighbors.append(LldpNeighbor(
            local_port_num=3,
            local_port_name='XGigabitEthernet0/0/3',
            remote_sys_name='CORE_CAMG',
            remote_port_id='XGigabitEthernet0/0/3',
            remote_mgmt_addr='10.43.170.6',
        ))

        engine = TopologyEngine()
        graph = engine.build([d_camg, d_prodemge])

        self.assertEqual(len(graph.links), 1, "Should produce exactly 1 physical link, not duplicates")
        link = graph.links[0]
        self.assertFalse(link.lag, "Single physical link must not be flagged as a LAG")
        self.assertEqual(len(graph.lags), 0, "No LAG bundles should be registered")
        self.assertEqual(link.source_port, 'XGigabitEthernet0/0/3', "Source port '35' should reconcile to canonical name")
        self.assertEqual(link.target_port, 'XGigabitEthernet0/0/3', "Target port should be canonical")

    def test_reciprocal_reconciliation_remote_reported_chassis_index(self):
        """Simulates when remote peer recorded local chassis port index 35 in remote_port_id."""
        d_camg = Device(id='camg', hostname='CORE_CAMG', ip='10.43.170.6')
        d_camg.lldp_neighbors.append(LldpNeighbor(
            local_port_num=35,
            local_port_name='XGigabitEthernet0/0/3',
            remote_sys_name='CORE_PRODEMGE',
            remote_port_id='XGigabitEthernet0/0/3',
            remote_mgmt_addr='10.43.170.3',
        ))

        d_prodemge = Device(id='prodemge', hostname='CORE_PRODEMGE', ip='10.43.170.3')
        d_prodemge.lldp_neighbors.append(LldpNeighbor(
            local_port_num=3,
            local_port_name='XGigabitEthernet0/0/3',
            remote_sys_name='CORE_CAMG',
            remote_port_id='35',
            remote_mgmt_addr='10.43.170.6',
        ))

        engine = TopologyEngine()
        graph = engine.build([d_camg, d_prodemge])

        self.assertEqual(len(graph.links), 1)
        link = graph.links[0]
        self.assertFalse(link.lag)
        self.assertEqual(link.source_port, 'XGigabitEthernet0/0/3')
        self.assertEqual(link.target_port, 'XGigabitEthernet0/0/3')

    def test_multi_link_lag_preservation(self):
        """Ensure genuine multiple links between switches are still detected as a LAG bundle."""
        d1 = Device(id='sw1', hostname='SW1', ip='10.0.0.1')
        d1.lldp_neighbors.append(LldpNeighbor(
            local_port_num=1, local_port_name='GigabitEthernet0/0/1',
            remote_sys_name='SW2', remote_port_id='GigabitEthernet0/0/1',
            remote_mgmt_addr='10.0.0.2',
        ))
        d1.lldp_neighbors.append(LldpNeighbor(
            local_port_num=2, local_port_name='GigabitEthernet0/0/2',
            remote_sys_name='SW2', remote_port_id='GigabitEthernet0/0/2',
            remote_mgmt_addr='10.0.0.2',
        ))

        d2 = Device(id='sw2', hostname='SW2', ip='10.0.0.2')
        d2.lldp_neighbors.append(LldpNeighbor(
            local_port_num=1, local_port_name='GigabitEthernet0/0/1',
            remote_sys_name='SW1', remote_port_id='GigabitEthernet0/0/1',
            remote_mgmt_addr='10.0.0.1',
        ))
        d2.lldp_neighbors.append(LldpNeighbor(
            local_port_num=2, local_port_name='GigabitEthernet0/0/2',
            remote_sys_name='SW1', remote_port_id='GigabitEthernet0/0/2',
            remote_mgmt_addr='10.0.0.1',
        ))

        engine = TopologyEngine()
        graph = engine.build([d1, d2])

        self.assertEqual(len(graph.links), 2, "Genuine multiple links must both be preserved")
        self.assertTrue(all(l.lag for l in graph.links), "Both links should have lag=True")
        self.assertEqual(len(graph.lags), 1, "Should have 1 LAG bundle")


if __name__ == '__main__':
    unittest.main()
