from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import shutil
import threading
import time
import csv
import re
from typing import Dict, List

try:
    import pythoncom
except Exception:
    pythoncom = None

try:
    import comtypes
except Exception:
    comtypes = None

try:
    from biocom.mps.common import BLDeviceModel, SampleType
    from biocom.mps.config import set_defaults, set_versions
    from biocom.mps.techniques.ocv import OCVParameters
    from biocom.mps.techniques.sequence import TechniqueSequence
    from biocom.com.server import DeviceChannel, OLECOM
    BIOCOM_AVAILABLE = True
except Exception:
    BLDeviceModel = SampleType = OCVParameters = TechniqueSequence = OLECOM = None
    set_defaults = set_versions = None
    BIOCOM_AVAILABLE = False
    class DeviceChannel: pass

EC_LAB_VERSION = "11.50"

@dataclass
class TechniqueConfig:
    name: str
    use_template: bool = True
    defaults: Dict[str, str] = field(default_factory=dict)
    special_peis_load_path: bool = False

TECHNIQUES: Dict[str, TechniqueConfig] = {
    "CA": TechniqueConfig("CA", defaults={"Ei (V)":"0.5","ti (h:m:s)":"0:00:30.0000","dI":"5.000","dt (s)":"0.1000","dta (s)":"0.1000","E range min (V)":"-2.500","E range max (V)":"2.500","I Range":"Auto","Bandwidth":"5"}),
    "CP": TechniqueConfig("CP", defaults={"Is":"50.000","unit Is":"µA","ts (h:m:s)":"0:00:20.0000","dEs (mV)":"0.00","dts (s)":"0.1000","E range min (V)":"-2.500","E range max (V)":"2.500","I Range":"100 µA","Bandwidth":"5"}),
    "CV": TechniqueConfig("CV", defaults={"Ei (V)":"0.000","dE/dt":"100.000","dE/dt unit":"mV/s","E1 (V)":"0.000","Step percent":"50","N":"10","E range min (V)":"-2.500","E range max (V)":"2.500","I Range":"Auto","Bandwidth":"5","E2 (V)":"0.500","Reverse Scan":"1","Ef (V)":"0.000","nc cycles":"1"}),
    "CVA": TechniqueConfig("CVA", defaults={"Ei (V)":"0.000","ti (h:m:s)":"0:00:5.0000","dti (s)":"1.0000","dE/dt":"100.000","dE/dt unit":"mV/s","E1 (V)":"1.000","t1 (h:m:s)":"0:00:0.0000","dt1 (s)":"0.1000","Step percent":"50","N":"10","E range min (V)":"-2.500","E range max (V)":"2.500","I Range":"Auto","Bandwidth":"5","E2 (V)":"-1.000","t2 (h:m:s)":"0:00:0.0000","dt2 (s)":"0.1000","nr":"1","nc cycles":"1","Reverse Scan":"0","Ef (V)":"0.000","tf (h:m:s)":"0:00:0.0000","dtf (s)":"0.1000"}),
    "LSV": TechniqueConfig("LSV", defaults={"tR (h:m:s)":"0:00:10.0000","dER/dt (mV/h)":"0.0","dER (mV)":"0","dtR (s)":"0.0000","dE/dt":"100.000","dE/dt unit":"mV/s","Ei (V)":"0.000","EL (V)":"0.500","dI":"0.000","tI (s)":"0.0000","step percent":"50","N":"10","E range min (V)":"-2.500","E range max (V)":"2.500","I Range":"Auto","Bandwidth":"5"}),
    "OCV": TechniqueConfig("OCV", use_template=False, defaults={"duration_s":"30.0","sampling_period_s":"5.0"}),
    "PEIS": TechniqueConfig("PEIS", special_peis_load_path=True, defaults={"E (V)":"0.0000","tE (h:m:s)":"0:00:0.0000","fi":"100.000","unit fi":"kHz","ff":"50.000","unit ff":"Hz","Nd":"10","Va (mV)":"10.0","E range min (V)":"-10.000","E range max (V)":"10.000","I Range":"Auto","Bandwidth":"5"}),
    "SWV": TechniqueConfig("SWV", defaults={"Ei (V)":"-0.500","ti (h:m:s)":"0:00:20.0000","Ev (V)":"0.500","PH (mV)":"25.000","PW (ms)":"50.0","SH (mV)":"10.000","Step percent":"20","E range min (V)":"-2.000","E range max (V)":"2.000","I Range":"10 mA","Bandwidth":"5","Reverse Scan":"0","Ef (V)":"0.000"}),
}

@dataclass
class BioLogicConfig:
    device_id: int = 0
    data_dir: str = r"C:\BioLogic_OLE_Test"
    templates_dir: str = "templates"
    timeout_s: int = 3600
    min_wait_s: float = 10.0
    poll_interval_s: float = 5.0
    simulate: bool = False

@dataclass
class ChannelRun:
    output_port: int
    channel_id: int
    channel: DeviceChannel
    mps_file: Path
    mpr_file: Path
    mixture_label: str
    composition: str
    enzyme: str
    job_id: int
    technique: str
    started_at: datetime

class BioLogicParallelRunner:
    def __init__(self, config: BioLogicConfig, output_to_channel: Dict[int, int], logger=print):
        self.config = config
        self.output_to_channel = dict(output_to_channel)  # GUI uses zero-based OLE-COM IDs
        self.log = logger
        self._lock = threading.RLock()

    def _initialize_com_for_current_thread(self):
        """Initialize COM in the exact thread that creates the EC-Lab OLE server.

        Bio-Logic's OLE layer in this project is created through *comtypes*.
        COM initialization is thread-local on Windows, so initializing it on
        Tkinter's main thread does not initialize FlowBot-Run.  Prefer
        comtypes.CoInitialize() because that is the library performing
        CoCreateInstance; use pythoncom only as a fallback.
        """
        if comtypes is not None:
            comtypes.CoInitialize()
            self.log(f"COM initialized with comtypes on thread {threading.current_thread().name}.")
            return "comtypes"
        if pythoncom is not None:
            pythoncom.CoInitialize()
            self.log(f"COM initialized with pythoncom fallback on thread {threading.current_thread().name}.")
            return "pythoncom"
        raise RuntimeError(
            "No COM initialization library is available. Install comtypes (and pywin32) "
            "in the same Python environment used to launch FlowBot."
        )

    @staticmethod
    def _is_transient_com_error(exc):
        """Return True for EC-Lab/OLE COM failures that are commonly transient.

        -2147417851 (0x80010105 / RPC_E_SERVERFAULT) is the intermittent
        "server threw an exception" seen when EC-Lab's OLE server is not ready
        for the next command/session.
        """
        code = getattr(exc, "hresult", None)
        if code is None and getattr(exc, "args", None):
            try:
                code = int(exc.args[0])
            except Exception:
                code = None
        msg = str(exc).lower()
        return code in (-2147417851, -2147418111, -2147023174) or (
            "server threw an exception" in msg
            or "call was rejected by callee" in msg
            or "rpc server is unavailable" in msg
        )

    def _connect_server(self, attempts=4, base_delay_s=2.0):
        """Create a fresh OLE server and verify the Bio-Logic connection.

        EC-Lab can intermittently reject a new OLE session immediately after a
        previous multi-channel run.  Retry only those transient COM failures;
        configuration/programming errors still fail immediately.
        """
        last = None
        for attempt in range(1, attempts + 1):
            try:
                server = OLECOM()
                server.launch_server()
                # Give the OLE server a brief settling period before first RPC.
                time.sleep(0.75 if attempt == 1 else 1.25)
                c = server.server.ConnectDevice(self.config.device_id)
                self.log(f"ConnectDevice: {c}")
                t = server.server.TestConnection(self.config.device_id)
                self.log(f"TestConnection: {t}")
                if isinstance(c, int) and c < 0:
                    raise RuntimeError(f"Bio-Logic ConnectDevice returned COM error {c}")
                if isinstance(t, int) and t < 0:
                    raise RuntimeError(f"Bio-Logic TestConnection returned COM error {t}")
                return server
            except Exception as exc:
                last = exc
                if not self._is_transient_com_error(exc) and "returned COM error -2147417851" not in str(exc):
                    raise
                if attempt >= attempts:
                    break
                delay = base_delay_s * attempt
                self.log(
                    f"Bio-Logic OLE transient connection error on attempt {attempt}/{attempts}: {exc}. "
                    f"Reconnecting in {delay:.1f} s..."
                )
                time.sleep(delay)
        raise RuntimeError(
            f"Bio-Logic OLE server did not recover after {attempts} connection attempts: {last}"
        ) from last

    def _com_call_retry(self, description, func, attempts=4, base_delay_s=1.5):
        """Retry a single idempotent OLE setup call on transient server faults."""
        last = None
        for attempt in range(1, attempts + 1):
            try:
                return func()
            except Exception as exc:
                last = exc
                if not self._is_transient_com_error(exc) or attempt >= attempts:
                    raise
                delay = base_delay_s * attempt
                self.log(
                    f"Bio-Logic transient OLE error during {description} "
                    f"(attempt {attempt}/{attempts}): {exc}. Retrying in {delay:.1f} s..."
                )
                time.sleep(delay)
        raise last

    @staticmethod
    def _uninitialize_com(kind):
        try:
            if kind == "comtypes" and comtypes is not None:
                comtypes.CoUninitialize()
            elif kind == "pythoncom" and pythoncom is not None:
                pythoncom.CoUninitialize()
        except Exception:
            # Never hide the experiment result because COM teardown itself failed.
            pass

    @staticmethod
    def _patch_fixed(template_file: Path, output_file: Path, replacements: Dict[str, str]):
        text = template_file.read_text(encoding="latin-1")
        nl = "\r\n" if "\r\n" in text else "\n"
        lines = text.splitlines(); used=set(); lw=20; vw=20
        for i,line in enumerate(lines):
            if line.strip().startswith("Filename :"):
                lines[i] = f"Filename : {output_file}"; continue
            label=line[:lw].strip()
            if label in replacements:
                val=str(replacements[label]); tail=line[lw+vw:] if len(line)>lw+vw else ""
                lines[i]=f"{label:<{lw}}{val:<{vw}}{tail}"; used.add(label)
        missing=sorted(set(replacements)-used)
        if missing: raise ValueError("Template is missing parameter labels: " + ", ".join(missing))
        output_file.write_text(nl.join(lines)+nl, encoding="latin-1")

    @staticmethod
    def _patch_peis(template_file: Path, output_file: Path, replacements: Dict[str, str]):
        text=template_file.read_bytes().decode("latin-1"); nl="\r\n" if "\r\n" in text else "\n"
        lines=text.splitlines(); used=set(); items=sorted(replacements.items(), key=lambda kv: len(kv[0]), reverse=True)
        for i,line in enumerate(lines):
            if line.strip().startswith("Filename :"):
                lines[i]=f"Filename : {output_file}"; continue
            for key,val in items:
                if key in used or not line.startswith(key) or (len(line)>len(key) and not line[len(key)].isspace()): continue
                j=len(key)
                while j<len(line) and line[j].isspace(): j+=1
                lines[i]=line[:j]+str(val).ljust(max(len(line)-j,len(str(val)))); used.add(key); break
        missing=sorted(set(replacements)-used)
        if missing: raise ValueError("PEIS template is missing parameter labels: " + ", ".join(missing))
        output_file.write_bytes((nl.join(lines)+nl).encode("latin-1"))

    @staticmethod
    def _safe_token(value: object, fallback: str = "NA") -> str:
        text = str(value or "").strip()
        if not text:
            return fallback
        text = re.sub(r"[^A-Za-z0-9._-]+", "-", text)
        text = re.sub(r"-+", "-", text).strip("-._")
        return text[:80] or fallback

    def _write_metadata_row(self, run: ChannelRun):
        path = Path(self.config.data_dir).expanduser().resolve() / "FlowBot_experiment_metadata.csv"
        new_file = not path.exists()
        with path.open("a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if new_file:
                writer.writerow([
                    "job_id", "mixture_label", "mixture_composition", "enzyme",
                    "technique", "potentiostat_channel", "ole_com_channel_id",
                    "output_port", "date", "timestamp", "mpr_file", "mps_file"
                ])
            writer.writerow([
                run.job_id, run.mixture_label, run.composition, run.enzyme,
                run.technique, run.channel_id + 1, run.channel_id,
                run.output_port, run.started_at.strftime("%Y-%m-%d"),
                run.started_at.isoformat(timespec="milliseconds"),
                str(run.mpr_file), str(run.mps_file),
            ])

    def _start_one(
        self, server: OLECOM, output_port: int, channel_id: int,
        technique: str, params: Dict[str, str], *,
        job_id: int, mixture_label: str, composition: str, enzyme: str, run_suffix: str = ""
    ) -> ChannelRun:
        datadir = Path(self.config.data_dir).expanduser().resolve()
        datadir.mkdir(parents=True, exist_ok=True)
        templates = Path(self.config.templates_dir).expanduser().resolve()
        ch = DeviceChannel(
            self.config.device_id, channel_id, BLDeviceModel.VSP,
            name=f"VSP_Channel{channel_id+1}"
        )
        started_at = datetime.now()
        date_tag = started_at.strftime("%Y%m%d")
        time_tag = started_at.strftime("%H%M%S_%f")[:-3]
        safe_label = self._safe_token(mixture_label, "UnlabeledMixture")
        safe_enzyme = self._safe_token(enzyme, "NoEnzyme")
        tag = (
            f"J{job_id}_{safe_label}_{safe_enzyme}_"
            f"CH{channel_id+1}_O{output_port}{run_suffix}_{date_tag}_{time_tag}"
        )
        cfg = TECHNIQUES[technique]

        if not cfg.use_template:
            set_versions(EC_LAB_VERSION)
            seq = TechniqueSequence([
                OCVParameters(
                    float(params["duration_s"]),
                    float(params["sampling_period_s"])
                )
            ])
            mps = (datadir / f"OCV_{tag}.mps").resolve()
            mpr = (datadir / f"OCV_{tag}.mpr").resolve()
            defaults = set_defaults(ch.model, seq, SampleType.CORROSION)
            server.load_techniques(ch, seq, defaults, str(mps))
            server.run_channel(ch, str(mpr))
            run = ChannelRun(
                output_port, channel_id, ch, mps, mpr,
                mixture_label, composition, enzyme, job_id,
                technique, started_at
            )
            self._write_metadata_row(run)
            return run

        template = templates / f"{technique}.mps"
        if not template.exists():
            raise FileNotFoundError(f"Missing Bio-Logic template: {template}")
        mpr = (datadir / f"{technique}_{tag}.mpr").resolve()

        if cfg.special_peis_load_path:
            load_mps = (datadir / "PEIS.mps").resolve()
            self._patch_peis(template, load_mps, params)
            archive = (datadir / f"PEIS_{tag}.mps").resolve()
            shutil.copyfile(load_mps, archive)
            mps = archive
        else:
            load_mps = (datadir / f"{technique}_{tag}.mps").resolve()
            self._patch_fixed(template, load_mps, params)
            mps = load_mps

        self.log(
            f"Loading {technique} | Job={job_id} | Mixture={mixture_label} | "
            f"Enzyme={enzyme} | Output={output_port} | Bio-Logic CH{channel_id+1}"
        )
        self._com_call_retry(f"load settings for Output {output_port} / CH{channel_id+1}", lambda: server.load_settings(ch, str(load_mps)))
        self._com_call_retry(f"start Output {output_port} / CH{channel_id+1}", lambda: server.run_channel(ch, str(mpr)))
        run = ChannelRun(
            output_port, channel_id, ch, mps, mpr,
            mixture_label, composition, enzyme, job_id,
            technique, started_at
        )
        self._write_metadata_row(run)
        return run

    def run_batch(
        self,
        jobs,
        plans_by_output: Dict[int, dict],
        enzyme_by_output: Dict[int, str],
    ):
        """Start one Bio-Logic channel for each job in the prepared fluidics batch."""
        jobs = list(jobs)
        if not jobs:
            return

        outputs = [int(job.output_port) for job in jobs]
        if len(outputs) != len(set(outputs)):
            raise ValueError("A parallel batch cannot contain two jobs assigned to the same output.")

        if self.config.simulate:
            import time
            self.log(
                "SIM Bio-Logic batch: "
                + ", ".join(f"J{j.job_id} {j.label}->O{j.output_port}" for j in jobs)
            )
            time.sleep(0.25)
            return

        if not BIOCOM_AVAILABLE:
            raise RuntimeError(
                "The Bio-Logic `biocom` package is not installed in this Python "
                "environment. Launch FlowBot with the same Python installation "
                "used to run your working Bio-Logic script."
            )

        with self._lock:
            com_kind = self._initialize_com_for_current_thread()
            try:
                server = self._connect_server()

                started = []
                for job in jobs:
                    out = int(job.output_port)
                    if out not in self.output_to_channel:
                        raise ValueError(f"Output {out} has no Bio-Logic channel mapping.")
                    if out not in plans_by_output:
                        raise ValueError(f"No electrochemistry plan configured for output {out}.")
                    plan = plans_by_output[out]
                    started.append(
                        self._start_one(
                            server, out, self.output_to_channel[out],
                            plan["technique"], plan["params"],
                            job_id=job.job_id, mixture_label=job.label,
                            composition=getattr(job, "composition_text", ""),
                            enzyme=enzyme_by_output.get(out, ""),
                        )
                    )

                self.log(f"Parallel batch: all {len(started)} Bio-Logic channels started; monitoring completion.")
                for run in started:
                    result = server.wait_for_channel(
                        run.channel, min_wait=self.config.min_wait_s,
                        timeout=self.config.timeout_s, interval=self.config.poll_interval_s,
                    )
                    self.log(
                        f"Job {run.job_id} | Output {run.output_port} / CH{run.channel_id+1} "
                        f"complete: {result.name}; {run.mpr_file}"
                    )
            finally:
                self._uninitialize_com(com_kind)


    def run_umbrella_job(self, job, enzyme_by_output: Dict[int, str], inter_scan_purge_callback=None):
        """Run an umbrella job in synchronized stages.

        CV/CVA assignments may contain multiple scan rates. At each stage, every
        output that still has a pending scan rate starts in parallel. The stage
        is allowed to finish on all active channels before an optional N2 purge,
        so gas flow never starts while another channel is still measuring.

        The dedicated gas solenoid supplies the connected cell purge manifold.
        An inter-scan purge requested by any output activates the single solenoid.
        If several outputs request a purge at the same boundary, the longest
        requested duration is used.
        """
        assignments = list(job.assignments)
        if not assignments:
            return
        outputs = [int(a.output_port) for a in assignments]
        if len(outputs) != len(set(outputs)):
            raise ValueError("An umbrella job cannot contain the same output twice.")

        # Build per-output run sequences. Non-CV/CVA techniques remain one-stage.
        sequences = {}
        for a in assignments:
            if a.technique in ("CV", "CVA") and getattr(a, "scan_rates", None):
                rates = [float(x) for x in a.scan_rates]
                if not rates or any(x <= 0 for x in rates):
                    raise ValueError(f"Output {a.output_port}: scan rates must all be > 0 mV/s.")
                sequences[int(a.output_port)] = rates
            else:
                sequences[int(a.output_port)] = [None]

        max_stages = max(len(v) for v in sequences.values())
        if self.config.simulate:
            import time
            for stage in range(max_stages):
                active=[]
                for a in assignments:
                    seq=sequences[int(a.output_port)]
                    if stage < len(seq):
                        rate=seq[stage]
                        active.append(f"O{a.output_port} {a.technique}" + (f" @{rate:g} mV/s" if rate is not None else ""))
                self.log(f"SIM Echem stage {stage+1}/{max_stages}: " + ", ".join(active))
                time.sleep(0.10)
                purge_requests=[]
                for a in assignments:
                    seq=sequences[int(a.output_port)]
                    if stage >= len(seq)-1 or seq[stage] is None: continue
                    current=float(seq[stage])
                    selected=[float(x) for x in getattr(a,"purge_after_scan_rates",[]) or []]
                    if any(abs(current-x)<1e-9 for x in selected) and float(getattr(a,"inter_scan_purge_s",0) or 0)>0:
                        purge_requests.append((int(a.output_port),float(a.inter_scan_purge_s),current,float(seq[stage+1])))
                if purge_requests:
                    duration=max(x[1] for x in purge_requests)
                    self.log("SIM inter-scan purge requested: " + ", ".join(f"O{o} {r1:g}->{r2:g} mV/s" for o,_,r1,r2 in purge_requests) + f"; external-solenoid purge {duration:g} s")
                    if inter_scan_purge_callback: inter_scan_purge_callback(duration, job.job_id, purge_requests)
            return
        if not BIOCOM_AVAILABLE:
            raise RuntimeError("The Bio-Logic `biocom` package is not installed in this Python environment.")

        with self._lock:
            com_kind = self._initialize_com_for_current_thread()
            try:
                server = self._connect_server()
                for stage in range(max_stages):
                    started=[]
                    for a in assignments:
                        out=int(a.output_port); seq=sequences[out]
                        if stage >= len(seq):
                            continue
                        if out not in self.output_to_channel:
                            raise ValueError(f"Output {out} has no Bio-Logic channel mapping.")
                        params=dict(a.echem_params)
                        rate=seq[stage]
                        suffix=""
                        if rate is not None:
                            params["dE/dt"] = f"{rate:g}"
                            suffix=f"_SR{self._safe_token(f'{rate:g}', 'rate')}mVs"
                        started.append(self._start_one(
                            server,out,self.output_to_channel[out],a.technique,params,
                            job_id=job.job_id, mixture_label=a.label,
                            composition=a.composition_text, enzyme=enzyme_by_output.get(out,""),
                            run_suffix=suffix,
                        ))
                    self.log(f"Umbrella Job {job.job_id}: Echem stage {stage+1}/{max_stages}; {len(started)} channel(s) started.")
                    for run in started:
                        result=server.wait_for_channel(run.channel,min_wait=self.config.min_wait_s,timeout=self.config.timeout_s,interval=self.config.poll_interval_s)
                        self.log(f"Job {run.job_id} | Output {run.output_port} / CH{run.channel_id+1} complete: {result.name}; {run.mpr_file}")

                    # Only purge after all active channels in this stage are complete.
                    purge_requests=[]
                    for a in assignments:
                        out=int(a.output_port); seq=sequences[out]
                        if stage >= len(seq)-1 or seq[stage] is None:
                            continue
                        current=float(seq[stage])
                        selected=[float(x) for x in getattr(a,"purge_after_scan_rates",[]) or []]
                        if any(abs(current-x)<1e-9 for x in selected) and float(getattr(a,"inter_scan_purge_s",0) or 0)>0:
                            purge_requests.append((out,float(a.inter_scan_purge_s),current,float(seq[stage+1])))
                    if purge_requests:
                        duration=max(x[1] for x in purge_requests)
                        self.log("Inter-scan purge requested: " + ", ".join(f"O{o} {r1:g}->{r2:g} mV/s ({d:g} s requested)" for o,d,r1,r2 in purge_requests) + f". external N2 solenoid will purge connected cells for {duration:g} s.")
                        if inter_scan_purge_callback is None:
                            raise RuntimeError("Inter-scan purge is configured but no purge callback was provided.")
                        inter_scan_purge_callback(duration, job.job_id, purge_requests)
            finally:
                self._uninitialize_com(com_kind)

    def run_job(self, job, plans_by_output, enzyme_by_output):
        """Backward-compatible single-job wrapper."""
        return self.run_batch([job], plans_by_output, enzyme_by_output)

