# FlowBot — Automated Bioelectrocatalysis Screening

**Research software for automated solution preparation and parallel electrochemical screening using a Bio-Logic potentiostat.**

FlowBot is a Python/Tkinter-controlled experimental platform developed for bioelectrocatalysis screening. It coordinates programmable syringe-pump/rotary-valve solution handling, a three-cell electrochemical workflow, and externally controlled nitrogen purging. The system prepares the assigned solutions in three electrochemical cells, can purge the connected cells through a shared gas manifold, and then runs the assigned Bio-Logic measurements concurrently before proceeding to the next group of experiments (an *umbrella job*).

> **Software origins and acknowledgement:** This FlowBot implementation was developed by adapting and extending software approaches from **[eLab API](https://github.com/jrlLAB/elabAPI)** (Michael Pence, Gavin Hazen, and Joaquín Rodríguez-López) and **[Easy-Biologic](https://github.com/bicarlsen/easy-biologic)** (Brian Carlsen). The fluidics interface uses the `elab` API, including an `SY01B` driver supplied by the laboratory environment. **Important distinction:** this release's Bio-Logic controller uses the **[biologic-com](https://github.com/jdhuang-csm/biologic-com)** `biocom` package and EC-Lab/OLECOM; it **does not directly import `easy_biologic`**. Easy-Biologic is acknowledged as a historical development foundation, not as a required runtime dependency of the enclosed files. See [Third-party acknowledgements and licensing](docs/ATTRIBUTION_AND_LICENSE.md).

This repository documents the *research-control software*, not a turnkey hardware product. Physical implementation requires compatible instruments, matching pump and solenoid firmware, an EC-Lab/COM installation, and laboratory-specific configuration.

## Key features

- **Bioelectrocatalysis screening:** configurable mediator/substrate/stock mixtures and per-output enzyme/electrode labels.
- **Concurrent three-cell experiments:** outputs **7, 9, and 10** are assigned to distinct Bio-Logic channel IDs; all assigned cells are prepared before the shared purge and electrochemical stages.
- **Automated fluidics:** four GUI-defined stock solutions can be mapped to four distinct ports chosen from six available input ports; user-defined fractional mixtures, line priming, syringe flushing, air chase, and cleaning.
- **Electrochemical methods:** CV, CVA, CA, CP, LSV, SWV, PEIS, and OCV. CV/CVA supports scan-rate series, synchronized stages, and optional inter-stage purging.
- **Gas control:** external Arduino-controlled, shared nitrogen solenoid. The air-chase port is separate and is **not** used to purge cells.
- **Screening campaigns:** editable umbrella-job queue, configuration save/load as JSON, experiment metadata CSV, EC-Lab `.mps`/`.mpr` output for live runs, and timestamped execution CSV logs.
- **Simulation and testing:** independent simulation switches for fluidics, Bio-Logic, and gas; automated no-hardware regression tests.

### Screening workflow

```text
Define stock solutions and output-to-channel mapping
                         |
                 Create umbrella jobs
                         |
           Prime/prepare Output 7, 9, 10
                         |
           Air chase each output line (P8)
                         |
         Optional shared N2 purge (solenoid)
                         |
     Run assigned Bio-Logic techniques in parallel
                         |
 Optional inter-stage purge between CV/CVA scans
                         |
        Clean used cells -> next umbrella job
                         |
               Logs and data records
```

**Concurrency means the measurement channels are started together after the three solutions are prepared.** A single syringe/rotary valve services fluidics sequentially. For a scan-rate series, each stage completes on all active channels before an optional common purge and next stage.

## Instrument configuration

| Valve port | Function |
| --- | --- |
| 1 | Flush solution |
| 2–6 | Available stock-solution inputs |
| 7 | Electrochemical output cell 1 |
| 8 | **Air chase only** |
| 9 | Electrochemical output cell 2 |
| 10 | Electrochemical output cell 3 |
| 11 | Additional stock-solution input |
| 12 | Waste |

The interface exposes **four** stock labels, assignable to any four different ports in `2, 3, 4, 5, 6, 11`. It does not simultaneously expose six separate stock recipes. The nitrogen solenoid sits **outside** the 12-port valve and supplies **all cells physically connected** to its manifold. There is no per-cell gas switching.

The provided code assumes a 5 mL syringe capacity and limits a single dispensed mixture to 5 mL. Verify the actual syringe size, tubing, pump orientation, and hardware configuration before a live run.

## Getting started

**Software:** Python 3 with Tkinter (tested here for syntax and no-hardware tests), Windows for instrument COM/OLE control, EC-Lab and its OLECOM registration for live Bio-Logic runs, the compatible `elab`/`SY01B` syringe driver, and the `biocom` package. The provided **Arduino firmware is not included**.

```powershell
# Run these commands from the extracted repository folder in PowerShell.
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-windows.txt
python -m unittest discover -s tests -v
python app.py
```

> **These pip requirements cover the general Python/Windows COM pieces, but NOT the specialized lab versions of `elab` or `biocom`.** Simulation mode works without those hardware libraries. For live experiments, follow [Windows installation and hardware commissioning](docs/SETUP_WINDOWS.md) and install the compatible instrument integrations into the *same* Python environment. If PowerShell blocks venv activation, use `.\.venv\Scripts\python.exe` instead of activating it.

**Start in simulation mode:** In the GUI confirm all three boxes — **Simulate fluidics**, **Simulate Bio-Logic**, and **Simulate gas solenoid** — are selected. They are independent; if the gas checkbox is disabled, **real gas hardware may actuate even when the other two are simulated**. Load the synthetic example in [`examples/simulated_screening.json`](examples/simulated_screening.json) using the GUI's Load command, then review its settings before starting. **The example is illustrative, not experimental data or a validated screening recipe.**

To use the template-based electrochemistry techniques in a live run, inspect and validate the supplied `.mps` templates for your EC-Lab setup and device firmware. Device configuration in the code uses the `VSP` model; compatibility with other Bio-Logic instruments is not established.

## Files

```text
app.py                        Tkinter application and JSON job editor
fluidics.py                   Valve/syringe operations and screening queue
biologic_runner.py            Bio-Logic multi-channel OLECOM controller
gas_control.py                Arduino serial solenoid protocol
test_gas_control.py           INTERACTIVE LIVE hardware commissioning script
START_FLOWBOT.bat             Windows launcher
templates/*.mps               EC-Lab technique templates
examples/simulated_screening.json  Safe synthetic sample (all simulation ON)
tests/                        Standard-library unittest suite
docs/SETUP_WINDOWS.md         Installation, configuration, safety and limitations
docs/UPLOAD_TO_GITHUB.md      Step-by-step GitHub publishing guide
docs/ATTRIBUTION_AND_LICENSE.md  Upstream acknowledgements and license notes
docs/MANUSCRIPT_CITATION.md   Suggested manuscript/software citations
CITATION.cff                  GitHub-generated software citation metadata
LICENSE                       GNU GPL v3 license text
```

**Logs and data:** On Windows the run-event CSV is normally written to `%LOCALAPPDATA%\FlowBot\Logs`. On disk-write failure the logger attempts a shorter fallback. Live Bio-Logic recordings and the `FlowBot_experiment_metadata.csv` are saved in the GUI-selected **Data directory**. Experimental data and private lab configurations are intentionally excluded from this source release.

## Reproducibility and verification

Run the supplied no-hardware tests:

```powershell
python -m unittest discover -s tests -v
```

The uploaded application has **nine existing regression tests** (fluidics/gas job execution in simulation, configuration, stop/error handling, and CSV recovery). No live instrument commissioning has been performed as part of preparing this repository. Simulation is not a validation of experimental measurements, pump calibration, purge effectiveness, or electrical safety. See [setup and commissioning](docs/SETUP_WINDOWS.md).

## Citing and acknowledging the software

When using this system in a manuscript, **cite FlowBot as the deposited software implementation** (GitHub release or an archived DOI when available), and credit the upstream projects separately. GitHub's **Cite this repository** menu reads [`CITATION.cff`](CITATION.cff). A ready-to-customize methods statement and software availability text are in [Manuscript citation guidance](docs/MANUSCRIPT_CITATION.md).

### Software acknowledgements

- **eLab API:** Michael Pence, Gavin Hazen, and Joaquín Rodríguez-López. [Repository](https://github.com/jrlLAB/elabAPI). Used/adapted for the fluidics-control layer; upstream code/license must be respected.
- **Easy-Biologic:** Brian Carlsen. [Repository](https://github.com/bicarlsen/easy-biologic). Acknowledged as an early basis for Bio-Logic automation concepts; this specific version does not import the package.
- **biologic-com:** [jdhuang-csm/biologic-com](https://github.com/jdhuang-csm/biologic-com). Actual Bio-Logic OLECOM interface imported by this version.

Please preserve acknowledgement of these upstream projects in derivatives and publications. Neither the original authors nor the instrument manufacturer are represented as endorsing this system.

## License and publication check

The source package is supplied with the **GNU General Public License v3** text, consistent with the upstream eLab GPLv3 license. **Before making the repository public, the software owner should verify who holds the copyright, which portions are adapted from third-party code, and the applicable licenses/permissions for any locally modified `elab` or other components.** Third-party libraries and vendor software are not redistributed in this repository. See [licensing notes](docs/ATTRIBUTION_AND_LICENSE.md).

The software controls physical laboratory equipment. Use only with approved hardware, supervision, and safety procedures; it is provided without warranty.
