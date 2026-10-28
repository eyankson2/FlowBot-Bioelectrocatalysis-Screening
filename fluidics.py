from __future__ import annotations
import csv, math, os, tempfile, threading, time, traceback
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, Tuple, List

GLOBAL_STOP = threading.Event()
class RunState(str, Enum):
    IDLE='IDLE'; INITIAL_PURGE='INITIAL PURGE'; JOB_PREP='UMBRELLA PREP'; JOB_PURGE='CELL PURGE'; JOB_ECHEM='ECHEM'; JOB_CLEAN='CELL CLEAN'; OVERNIGHT_FILL='OVERNIGHT FILL'; COMPLETE='COMPLETE'; STOPPED='STOPPED'; ERROR='ERROR'
class JobState(str, Enum):
    QUEUED='QUEUED'; PREPARING='PREPARING'; READY='READY'; ECHEM='ECHEM'; CLEANING='CLEANING'; COMPLETE='COMPLETE'; ERROR='ERROR'
@dataclass(frozen=True)
class MediatorFluidicConfig:
    com_port:str='COM7'; syringe_capacity_ml:float=5.; n_ports:int=12
    input_ports:Tuple[int,...]=(2,3,4,5,6,11); flush_port:int=1; air_port:int=8
    output_ports:Tuple[int,...]=(7,9,10); waste_port:int=12
    condition_volume_ml:float=.5; air_chase_volume_ml:float=5.
    final_drain_volume_ml:float=5.; final_drain_repeats:int=2; final_rinse_volume_ml:float=5.; final_rinse_repeats:int=3; final_rinse_wait_s:float=2.; final_extra_draw_ml:float=5.
    overnight_fill_ml:float=4.; route_settle_s:float=.4; action_settle_s:float=.4
    @property
    def echem_output_ports(self): return self.output_ports
@dataclass
class OutputAssignment:
    output_port:int; label:str; fractions:Dict[int,float]; volume_ml:float; composition_text:str=''; technique:str='CV'; echem_params:Dict[str,str]=field(default_factory=dict); scan_rates:List[float]=field(default_factory=list); purge_after_scan_rates:List[float]=field(default_factory=list); inter_scan_purge_s:float=0.0
@dataclass
class UmbrellaJob:
    job_id:int; label:str; assignments:List[OutputAssignment]=field(default_factory=list); cell_purge:bool=True; state:JobState=JobState.QUEUED; message:str=''
@dataclass
class RunParameters:
    initial_n2_saturation_s:float; cell_purge_s:float; line_prime_volume_ml:float; syringe_flush_repeats:int; overnight_run:bool
class FlowBotStopRequested(RuntimeError): pass
def run_log_directory():
    """Keep Windows run logs outside deeply nested OneDrive/project directories.

    A run's CSV can be written in LOCALAPPDATA without Windows MAX_PATH issues;
    use the user's temporary folder on other platforms or if LOCALAPPDATA is unset.
    """
    base = os.environ.get('LOCALAPPDATA')
    return (Path(base) if base else Path(tempfile.gettempdir())) / 'FlowBot' / 'Logs'


class EventLogger:
    """GUI/console logging remains functional even when CSV storage fails.

    On an I/O error, try short local log directories.  If all fail, disable
    only the optional CSV output, not the experiment control thread.
    """

    def __init__(self, callback=print, csv_path=None):
        self.callback = callback
        self.csv_path = Path(csv_path) if csv_path else None
        self.lock = threading.Lock()
        self.csv_disabled_reason = None

    @staticmethod
    def _append_csv(path, message):
        path.parent.mkdir(parents=True, exist_ok=True)
        new = not path.is_file() or path.stat().st_size == 0
        with path.open('a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            if new:
                writer.writerow(['timestamp', 'thread', 'event'])
            writer.writerow([datetime.now().isoformat(timespec='seconds'),
                             threading.current_thread().name, message])

    def log(self, message):
        line = (f"[{datetime.now().strftime('%H:%M:%S')}] "
                f"[{threading.current_thread().name}] {message}")
        with self.lock:
            self.callback(line)
            if self.csv_path is None:
                return
            try:
                self._append_csv(self.csv_path, message)
                return
            except OSError as first_error:
                original = self.csv_path
                first_error_text = str(first_error)

            # Saving in a nested OneDrive path can fail on Windows (MAX_PATH),
            # even when the directory exists.  Recover to LOCALAPPDATA or TEMP.
            candidates = [run_log_directory() / original.name,
                          Path(tempfile.gettempdir()) / 'FlowBot' / 'Logs' / original.name]
            for candidate in candidates:
                if candidate == original:
                    continue
                try:
                    self._append_csv(candidate, message)
                    self.csv_path = candidate
                    warning = (f'WARNING: CSV logging at {original} failed: {first_error_text}. '
                               f'Run log redirected to {candidate}')
                    self.callback(f'[FlowBot logging] {warning}')
                    # The first failed event has already been written above.
                    try:
                        self._append_csv(candidate, warning)
                    except OSError:
                        pass
                    return
                except OSError:
                    continue

            self.csv_path = None
            self.csv_disabled_reason = first_error_text
            self.callback(f'[FlowBot logging] WARNING: CSV logging disabled '
                          f'(could not write {original}: {first_error_text}). '
                          'On-screen experiment logging remains active.')


class MediatorFluidicsHardware:
    def __init__(self,cfg,logger,simulate=True): self.config=cfg; self.log=logger.log; self.simulate=simulate; self.connected=False; self.pumpvalve=None; self.hardware_lock=threading.RLock()
    def check_stop(self):
        if GLOBAL_STOP.is_set(): raise FlowBotStopRequested('Stop requested')
    def sleep(self,s):
        # Interruptible sleep. Recalculate the remaining delay once per loop and
        # clamp it before calling time.sleep(). The clock can advance between a
        # loop-condition check and the sleep call, which previously allowed a
        # tiny negative value to reach time.sleep() intermittently.
        duration=max(0.0,float(s))
        end=time.monotonic()+duration
        while True:
            self.check_stop()
            remaining=end-time.monotonic()
            if remaining<=0:
                break
            time.sleep(max(0.0,min(0.05,remaining)))
    def validate_config(self):
        c=self.config; roles=list(c.input_ports)+[c.flush_port,c.air_port]+list(c.output_ports)+[c.waste_port]
        if len(roles)!=len(set(roles)) or sorted(roles)!=list(range(1,13)): raise ValueError('Port roles must uniquely cover ports 1-12.')
        if set(c.echem_output_ports)!={7,9,10} or set(c.input_ports)!={2,3,4,5,6,11} or c.air_port!=8 or c.flush_port!=1 or c.waste_port!=12:
            raise ValueError('Expected ports: flush 1, stocks 2-6 and 11, cells 7/9/10, air chase 8, waste 12.')
    def connect(self):
        self.validate_config()
        if self.simulate:self.connected=True; self.log('SIMULATION: fluidics connected.'); return
        import elab
        self.pumpvalve=elab.SY01B(self.config.com_port); self.pumpvalve.total_volume=self.config.syringe_capacity_ml; self.pumpvalve.unit='mL'; self.pumpvalve.ports=self.config.n_ports
        self.pumpvalve.compile_cmd('set_start_speed',parameter1=100); self.pumpvalve.compile_cmd('set_acceleration',parameter1=300); self.connected=True; self.route(self.config.waste_port); self.log('Fluidics connected.')
    def close(self):
        if self.connected and not self.simulate and self.pumpvalve:
            try:self.route(self.config.waste_port)
            except:pass
            self.pumpvalve.close()
        self.connected=False
    def route(self,p): self.check_stop(); self.log(f"{'SIM ' if self.simulate else ''}route -> {p}"); self.sleep(.01 if self.simulate else self.config.route_settle_s) if self.simulate else (self.pumpvalve.port(int(p)),self.sleep(self.config.route_settle_s))
    def aspirate(self,v): self.check_stop(); self.log(f"{'SIM ' if self.simulate else ''}aspirate {v:g} mL"); self.sleep(.01) if self.simulate else (self.pumpvalve.aspirate(float(v)),self.sleep(self.config.action_settle_s))
    def discharge(self,v): self.check_stop(); self.log(f"{'SIM ' if self.simulate else ''}discharge {v:g} mL"); self.sleep(.01) if self.simulate else (self.pumpvalve.discharge(float(v)),self.sleep(self.config.action_settle_s))
    def transfer(self,src,dst,total,label):
        rem=float(total)
        with self.hardware_lock:
            while rem>1e-9:
                chunk=min(self.config.syringe_capacity_ml,rem); self.log(f'{label}: {chunk:g} mL'); self.route(src); self.aspirate(chunk); self.route(dst); self.discharge(chunk); rem-=chunk
    def prime_input(self,p,v):
        if v>0:self.transfer(p,self.config.waste_port,v,f'Prime input {p}')
    def condition_syringe(self,p): self.transfer(p,self.config.waste_port,self.config.condition_volume_ml,f'Condition input {p}')
    def flush_syringe_to_waste(self,n):
        for _ in range(int(n)): self.transfer(self.config.flush_port,self.config.waste_port,self.config.syringe_capacity_ml,'Syringe flush')
    def prepare_mixture_to_output(self,fractions,out,total,label):
        total=float(total); parts=[(int(p),float(f)) for p,f in fractions.items() if float(f)>0]
        if not parts:raise ValueError('Solution has no component.')
        if total<=0 or total>self.config.syringe_capacity_ml+1e-9:raise ValueError('Solution volume must be >0 and <= syringe capacity.')
        with self.hardware_lock:
            self.log(f'{label}: preparing {total:g} mL -> output {out}'); drawn=0
            for i,(p,f) in enumerate(parts):
                v=total-drawn if i==len(parts)-1 else total*f; drawn+=0 if i==len(parts)-1 else v
                self.log(f'{label}: input {p} = {f*100:.3f}% ({v:g} mL)'); self.route(p); self.aspirate(v)
            self.route(out); self.discharge(total)
    def air_chase_output(self,out): self.transfer(self.config.air_port,out,self.config.air_chase_volume_ml,f'Air chase -> output {out}')
    def final_clean_output(self,out):
        c=self.config
        for _ in range(c.final_drain_repeats):self.transfer(out,c.waste_port,c.final_drain_volume_ml,f'Drain output {out}')
        for _ in range(c.final_rinse_repeats):self.transfer(c.flush_port,out,c.final_rinse_volume_ml,f'Rinse fill {out}'); self.sleep(.01 if self.simulate else c.final_rinse_wait_s); self.transfer(out,c.waste_port,c.final_rinse_volume_ml,f'Rinse drain {out}')
        self.transfer(out,c.waste_port,c.final_extra_draw_ml,f'Final draw {out}')
    def overnight_fill_output(self,out):self.transfer(self.config.flush_port,out,self.config.overnight_fill_ml,f'Overnight fill {out}')
    def park_safe(self):
        try:
            if self.connected:self.route(self.config.waste_port)
        except:pass
class SolenoidPurgeSystem:
    """Dedicated Arduino solenoid gas purging, entirely outside the syringe valve.

    Firmware protocol: <PURGE:seconds> / OK:ON, <OFF> / OK:OFF.
    The Arduino also implements its own independent 1-600 s timeout.
    The solenoid gas outlet must be physically connected to the intended cell(s).
    """
    MAX_PURGE_S = 600.0

    def __init__(self, port, logger, simulate=True):
        self.port = str(port).strip()
        self.log = logger.log
        self.simulate = bool(simulate)
        self.connected = False
        self.client = None
        self._lock = threading.RLock()

    @classmethod
    def validate_duration(cls, seconds, label='Purge'):
        duration = float(seconds)
        if not math.isfinite(duration) or duration < 0 or duration > cls.MAX_PURGE_S:
            raise ValueError(f'{label} must be between 0 and {cls.MAX_PURGE_S:g} seconds.')
        return duration

    def connect(self):
        if self.connected:
            return
        if self.simulate:
            self.connected = True
            self.log('SIMULATION: dedicated gas solenoid connected; no real gas will flow.')
            return
        if not self.port:
            raise ValueError('Specify a serial COM port for the Arduino gas controller.')
        try:
            from gas_control import GasControl  # pyserial required only for LIVE gas
        except ImportError as exc:
            raise RuntimeError('Live gas control requires pyserial: pip install pyserial') from exc
        client = GasControl(port=self.port)
        try:
            client.connect()          # Arduino resets; command OFF on startup
        except Exception:
            try:
                client.disconnect()
            except Exception:
                pass
            raise
        with self._lock:
            self.client = client
            self.connected = True
        self.log(f'Gas controller on {self.port} connected; solenoid commanded OFF.')

    def emergency_off(self):
        """Safe to call from STOP button while the worker is waiting for a purge."""
        with self._lock:
            if self.connected and not self.simulate and self.client is not None:
                self.client.off()

    def purge(self, seconds, label='Cell purge'):
        duration = self.validate_duration(seconds, label)
        if duration == 0:
            self.log(f'{label}: 0 s; gas valve remains closed.')
            return
        if GLOBAL_STOP.is_set():
            raise FlowBotStopRequested('Stop requested before gas purge.')
        if not self.connected:
            raise RuntimeError('Gas controller is not connected.')
        # The Arduino protocol uses integer seconds; round UP the firmware
        # safety timeout and stop at the precise requested host-side duration.
        firmware_duration = int(math.ceil(duration))
        self.log(f'{"SIM " if self.simulate else ""}{label}: solenoid OPEN for {duration:g} s (Arduino timeout {firmware_duration} s).')
        if self.simulate:
            # No hardware delay during end-to-end simulation.
            if GLOBAL_STOP.wait(min(duration, 0.02)):
                raise FlowBotStopRequested('Stopped during simulated gas purge.')
            self.log(f'SIM {label}: solenoid CLOSED.')
            return
        with self._lock:
            if GLOBAL_STOP.is_set():
                raise FlowBotStopRequested('Stop requested before gas valve opening.')
            self.client.start_purge(firmware_duration)
        try:
            if GLOBAL_STOP.wait(duration):
                raise FlowBotStopRequested('Stopped during gas purge.')
        finally:
            # The hardware firmware also auto-closes at the timeout, but the
            # host always sends OFF on normal completion, STOP, or errors.
            with self._lock:
                self.client.off()
            self.log(f'{label}: solenoid CLOSED.')

    def close(self):
        with self._lock:
            if not self.connected:
                return
            try:
                if not self.simulate and self.client is not None:
                    self.client.disconnect()  # OFF, then serial close
            finally:
                self.connected = False
                self.client = None

class UmbrellaScreeningController:
    def __init__(self,jobs,params,hardware,logger,state_callback=None,echem_job_callback=None,substrate_port=None,gas=None):
        self.jobs=list(jobs); self.params=params; self.hardware=hardware; self.gas=gas; self.log=logger.log; self.state_callback=state_callback; self.echem_job_callback=echem_job_callback; self.substrate_port=int(substrate_port) if substrate_port else None; self.running=False; self.failed=False; self.failure_message=''; self.run_state=RunState.IDLE; self.used_outputs_during_run=set()
    def _notify(self):
        if self.state_callback:
            try:self.state_callback()
            except:pass
    def _set_run_state(self,s):self.run_state=s; self.log(f'RUN STATE -> {s.value}'); self._notify()
    def _set_job_state(self,j,s,msg=''):j.state=s;j.message=msg;self.log(f'Umbrella Job {j.job_id} [{j.label}]: {s.value}');self._notify()
    def validate(self):
        self.hardware.validate_config(); avail=set(self.hardware.config.input_ports)
        if self.gas is None: raise ValueError('Configure a dedicated solenoid gas controller.')
        self.gas.validate_duration(self.params.initial_n2_saturation_s,'Initial N2 saturation')
        self.gas.validate_duration(self.params.cell_purge_s,'Cell purge')
        if self.params.line_prime_volume_ml < 0 or self.params.syringe_flush_repeats < 0: raise ValueError('Prime and flush must be nonnegative.')
        if not self.jobs:raise ValueError('Add at least one umbrella job.')
        for i,j in enumerate(self.jobs,1):
            j.job_id=i
            if not j.label.strip():raise ValueError(f'Job {i}: label required.')
            if not j.assignments:raise ValueError(f'Job {i}: add at least one output solution.')
            outs=[int(a.output_port) for a in j.assignments]
            if len(outs)!=len(set(outs)):raise ValueError(f'Job {i}: each output can appear only once.')
            for a in j.assignments:
                if a.output_port not in self.hardware.config.echem_output_ports:raise ValueError(f'Job {i}: invalid output {a.output_port}.')
                clean={int(p):float(f) for p,f in a.fractions.items() if float(f)>0}; bad=set(clean)-avail
                if not clean or bad or abs(sum(clean.values())-1)>1e-6:raise ValueError(f'Job {i}, O{a.output_port}: invalid composition/fractions.')
                if a.volume_ml<=0 or a.volume_ml>self.hardware.config.syringe_capacity_ml:raise ValueError(f'Job {i}, O{a.output_port}: volume must be >0 and <=5 mL.')
                a.fractions=clean
                self.gas.validate_duration(a.inter_scan_purge_s, f'Job {i}, O{a.output_port} inter-scan purge')
    def start(self):self.validate();GLOBAL_STOP.clear();self.running=True;threading.Thread(target=self._run,name='FlowBot-Run',daemon=True).start()
    def stop(self):
        GLOBAL_STOP.set();self.log('STOP requested. Closing gas solenoid.')
        if self.gas:
            try: self.gas.emergency_off()
            except Exception as exc: self.log(f'WARNING: gas valve OFF command failed: {exc}')
    def _prime(self,a):
        for p in a.fractions:self.hardware.prime_input(p,self.params.line_prime_volume_ml);self.hardware.condition_syringe(p)
    def _needs_flush(self,prev,current):
        if prev is None:return False,''
        # Flush whenever the complete recipe changes. This includes mediator changes and
        # substrate -> buffer transitions, preventing substrate carryover.
        def sig(a):return tuple(sorted((int(p),round(float(f),12)) for p,f in a.fractions.items() if float(f)>0))
        if sig(prev)!=sig(current):
            if self.substrate_port and float(prev.fractions.get(self.substrate_port,0))>0 and float(current.fractions.get(self.substrate_port,0))<=0:return True,'substrate-containing solution -> substrate-free solution'
            return True,'solution composition changed'
        return False,''
    def _run(self):
        try:
            self.log('Connecting dedicated gas controller...');self.gas.connect()
            self.log('Connecting fluidics hardware...');self.hardware.connect()
            self._set_run_state(RunState.INITIAL_PURGE);self.gas.purge(self.params.initial_n2_saturation_s,'Initial N2 saturation')
            previous=None
            for j in self.jobs:
                self._set_run_state(RunState.JOB_PREP);self._set_job_state(j,JobState.PREPARING)
                # Critical umbrella behavior: prepare ALL assigned outputs before purge/echem.
                for a in j.assignments:
                    flush,reason=self._needs_flush(previous,a)
                    if flush:self.log(f'Before Job {j.job_id} O{a.output_port}: {reason}; activating syringe flush.');self.hardware.flush_syringe_to_waste(self.params.syringe_flush_repeats)
                    elif previous is None:self.log('First solution: no pre-solution syringe flush required.')
                    self._prime(a);self.hardware.prepare_mixture_to_output(a.fractions,a.output_port,a.volume_ml,f'J{j.job_id} {a.label}');self.hardware.air_chase_output(a.output_port);self.used_outputs_during_run.add(a.output_port);previous=a
                self._set_job_state(j,JobState.READY)
                if j.cell_purge:
                    self._set_run_state(RunState.JOB_PURGE)
                    self.log(f'Umbrella Job {j.job_id}: cell purge ENABLED ({self.params.cell_purge_s:g} s).')
                    self.gas.purge(self.params.cell_purge_s,f'Job {j.job_id} N2 cell purge')
                else:
                    self.log(f'Umbrella Job {j.job_id}: cell purge DISABLED; proceeding directly to electrochemistry.')
                self._set_run_state(RunState.JOB_ECHEM);self._set_job_state(j,JobState.ECHEM)
                if not self.echem_job_callback:raise RuntimeError('No electrochemistry callback configured.')
                self.echem_job_callback(j)
                self._set_run_state(RunState.JOB_CLEAN);self._set_job_state(j,JobState.CLEANING)
                for out in sorted(a.output_port for a in j.assignments):self.hardware.final_clean_output(out)
                self._set_job_state(j,JobState.COMPLETE)
            if self.params.overnight_run:
                self._set_run_state(RunState.OVERNIGHT_FILL)
                for out in sorted(self.used_outputs_during_run):self.hardware.overnight_fill_output(out)
            self._set_run_state(RunState.COMPLETE)
        except FlowBotStopRequested:self._set_run_state(RunState.STOPPED)
        except Exception as e:
            self.failed=True;self.failure_message=str(e);self._set_run_state(RunState.ERROR);self.log(f'ERROR: {e}');self.log(traceback.format_exc())
        finally:
            # OFF takes priority, including on errors/STOP. Never leave the
            # solenoid energized while fluidics clean-up is being attempted.
            try:
                if self.gas: self.gas.close()
            except Exception as exc: self.log(f'WARNING: gas disconnect/OFF failed: {exc}')
            try:
                self.hardware.park_safe();self.hardware.close()
            except Exception as exc: self.log(f'WARNING: fluidics disconnect failed: {exc}')
            self.running=False;self._notify()
