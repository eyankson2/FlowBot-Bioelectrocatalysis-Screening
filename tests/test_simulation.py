"""Hardware-free regression tests: python -m unittest discover -s tests -v"""
import math
import threading
import time
import unittest
from dataclasses import replace

from biologic_runner import BioLogicConfig, BioLogicParallelRunner, TECHNIQUES
from fluidics import (
    GLOBAL_STOP, EventLogger, MediatorFluidicConfig, MediatorFluidicsHardware,
    OutputAssignment, RunParameters, RunState, SolenoidPurgeSystem,
    UmbrellaJob, UmbrellaScreeningController, FlowBotStopRequested,
)


class FlowbotTests(unittest.TestCase):
    def setUp(self):
        GLOBAL_STOP.clear()
        self.logs = []
        self.logger = EventLogger(self.logs.append)

    def tearDown(self):
        GLOBAL_STOP.clear()

    def make_controller(self, callback=None, *, cell_purge=True):
        # Speed up cleaning in tests only, without affecting real hardware defaults.
        cfg = replace(MediatorFluidicConfig(), final_drain_repeats=0,
                      final_rinse_repeats=0, final_extra_draw_ml=0,
                      condition_volume_ml=0, air_chase_volume_ml=0.25)
        hw = MediatorFluidicsHardware(cfg, self.logger, simulate=True)
        gas = SolenoidPurgeSystem('COM4', self.logger, simulate=True)
        a7 = OutputAssignment(7, 'Mediator + buffer', {2: 0.5, 11: 0.5}, 3.0,
                              'Stock P2 50% + stock P11 50%', 'CV', dict(TECHNIQUES['CV'].defaults),
                              [100.0, 50.0], [100.0], 3.0)
        a9 = OutputAssignment(9, 'Stock 3', {3: 1.0}, 2.5, '', 'SWV', dict(TECHNIQUES['SWV'].defaults))
        a10 = OutputAssignment(10, 'Stock 5', {5: 1.0}, 2.5, '', 'CA', dict(TECHNIQUES['CA'].defaults))
        job=UmbrellaJob(1, 'Test all outputs', [a7, a9, a10], cell_purge=cell_purge)
        runner=BioLogicParallelRunner(BioLogicConfig(simulate=True), {7:0,9:1,10:2}, self.logs.append)
        def echem(j):
            if callback: callback(j)
            return runner.run_umbrella_job(j, {7:'',9:'',10:''},
                inter_scan_purge_callback=lambda sec, jid, req: gas.purge(sec, f'Job {jid} inter-scan purge'))
        ctl = UmbrellaScreeningController([job], RunParameters(2,4,0,0,False), hw,self.logger,
                                           echem_job_callback=echem, substrate_port=5, gas=gas)
        return ctl

    def test_new_port_roles_are_all_unique(self):
        cfg=MediatorFluidicConfig()
        self.assertEqual(cfg.input_ports, (2,3,4,5,6,11))
        self.assertEqual(cfg.output_ports, (7,9,10))
        self.assertEqual(cfg.air_port, 8)
        self.assertEqual(len(set(cfg.input_ports+cfg.output_ports+(cfg.air_port,cfg.flush_port,cfg.waste_port))),12)
        MediatorFluidicsHardware(cfg,self.logger).validate_config()

    def test_whole_simulated_workflow_and_multi_scan(self):
        ctl=self.make_controller()
        ctl.start()
        deadline=time.monotonic()+20
        while ctl.running and time.monotonic()<deadline: time.sleep(0.05)
        self.assertFalse(ctl.running,'Controller failed to complete')
        self.assertFalse(ctl.failed,ctl.failure_message)
        self.assertEqual(ctl.run_state,RunState.COMPLETE)
        text='\n'.join(self.logs)
        self.assertIn('input 11 = 50.000%',text)
        self.assertIn('Air chase -> output 7',text)
        self.assertIn('Air chase -> output 9',text)
        self.assertIn('Air chase -> output 10',text)
        self.assertIn('Initial N2 saturation: solenoid OPEN',text)
        self.assertIn('Job 1 N2 cell purge: solenoid OPEN',text)
        self.assertIn('Job 1 inter-scan purge: solenoid OPEN',text)
        self.assertIn('SIM Echem stage 1/2:',text)
        self.assertIn('SIM Echem stage 2/2:',text)
        self.assertNotIn('splitter',text.lower())
        self.assertEqual(text.count('SIM route -> 8'),3,
            'Air valve port may ONLY be touched once per prepared output')
        # All three solutions must finish dispensing before the job gas purge.
        self.assertLess(text.index('Air chase -> output 10'),text.index('Job 1 N2 cell purge:'))

    def test_purge_duration_range(self):
        gas=SolenoidPurgeSystem('COM4',self.logger,simulate=True)
        for bad in [-1,601,float('nan'),float('inf')]:
            with self.assertRaises(ValueError): gas.validate_duration(bad)
        self.assertEqual(gas.validate_duration(0),0)
        self.assertEqual(gas.validate_duration(599.9),599.9)

    def test_stop_turns_off_real_solenoid(self):
        # Fake serial interface; no COM connection or 12V needed.
        on=threading.Event()
        class FakeClient:
            def __init__(self): self.events=[]
            def start_purge(self,seconds): self.events.append(('ON',seconds));on.set()
            def off(self): self.events.append(('OFF',))
            def disconnect(self): self.events.append(('CLOSE',))
        gas=SolenoidPurgeSystem('FAKE',self.logger,simulate=False)
        fake=FakeClient();gas.client=fake;gas.connected=True
        errors=[]
        def run():
            try: gas.purge(20,'STOP test')
            except Exception as e: errors.append(e)
        thread=threading.Thread(target=run)
        thread.start()
        self.assertTrue(on.wait(3))
        GLOBAL_STOP.set()
        gas.emergency_off()
        thread.join(3)
        self.assertFalse(thread.is_alive())
        self.assertTrue(any(isinstance(e,FlowBotStopRequested) for e in errors))
        self.assertEqual(fake.events[0],('ON',20))
        self.assertGreaterEqual(fake.events.count(('OFF',)),1)
        gas.close()

    def test_error_closes_gas(self):
        def fail(_job): raise RuntimeError('Intentional simulated potentiostat failure')
        ctl=self.make_controller(callback=fail)
        ctl.start()
        deadline=time.monotonic()+15
        while ctl.running and time.monotonic()<deadline: time.sleep(.05)
        self.assertFalse(ctl.running)
        self.assertTrue(ctl.failed)
        self.assertEqual(ctl.run_state,RunState.ERROR)
        self.assertFalse(ctl.gas.connected)

if __name__=='__main__':
    unittest.main()
