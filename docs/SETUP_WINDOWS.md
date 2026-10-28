# Windows setup and commissioning

The following instructions describe running the supplied code **without hardware first**, then prerequisites for the existing live instrument interfaces. Do **not** begin by connecting a live experiment.

## 1. Install and open the application

1. Install a compatible 64-bit Windows Python 3 distribution with **Tkinter** and the required native COM architecture for your EC-Lab installation. The exact Python/EC-Lab version pairing used in the original laboratory setup was not provided; test compatibility rather than assuming a specific version.
2. Extract the GitHub package and open PowerShell in its root folder (the one containing `app.py`).
3. Create a virtual environment and install the general Python dependencies:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r requirements-windows.txt
   .\.venv\Scripts\python.exe -m unittest discover -s tests -v
   .\.venv\Scripts\python.exe app.py
   ```

4. In the GUI, make sure **all three simulation checkboxes are ON**. The app defaults to simulated fluidics, simulated Bio-Logic and simulated gas.
5. Load `examples/simulated_screening.json` using the GUI's load command. Confirm all three simulation boxes remain selected and review the job compositions and outputs. (The file contains synthetic labels, not authentic chemistry data.)
6. Select an output data folder where the user has write permission; the default `C:\BioLogic_OLE_Test` is only a configurable example, not a required fixed installation path. Use a short local path to reduce Windows path-length failures.
7. Execute the example only in the fully simulated configuration. Inspect the Run Log and confirm that the three assigned cells are prepared before the common purge/measurement stage.

## 2. Hardware prerequisites for live operation

**Liquid handler:** A 12-port valve/syringe instrument supported by the *laboratory-compatible* `elab.SY01B` implementation. The source release imports `elab` dynamically, so normal simulation mode does not require installing that package. The upstream [jrlLAB/elabAPI](https://github.com/jrlLAB/elabAPI) API is a reference, but its stock implementation may not expose exactly the same `SY01B` methods or custom modifications. Install the working, appropriately licensed lab version into the active virtual environment, or adapt and validate the hardware integration explicitly.

**Bio-Logic:** An EC-Lab installation with an appropriately registered OLECOM server, a compatible Bio-Logic potentiostat configured as the code's `BLDeviceModel.VSP`, and the Python module `biocom` from [biologic-com](https://github.com/jdhuang-csm/biologic-com), plus its dependencies. Its upstream README describes installation and OLECOM registration. Run `python -c "import biocom; print(biocom.__file__)"` in the environment and verify the OLECOM server is registered and the device is accessible before disabling *Simulate Bio-Logic*. The current application **does not call Easy-Biologic directly**.

**Arduino solenoid:** A serial-controllable Arduino with the *matching separate* sketch/firmware implementing `<PURGE:N>`, `<OFF>` and `<STATUS>` commands and `OK:ON`/`OK:OFF` acknowledgements. Protocol `N` is an integer **1–600 seconds**. The Arduino sketch and circuit are **not distributed** in this repo. Ensure a fail-closed electrical design, independent firmware watchdog/timeout, pressure regulation, a correctly sized exhaust/vent, and any required gas sensors/regulatory approvals. Never use software STOP as the sole safeguard against gas flow.

**First energization test:** With the gas supply **OFF** and the setup under authorized supervision, edit the port constant in `test_gas_control.py` to the correct COM port, and only then consider the interactive command test with the solenoid drive under an approved safety plan. **`test_gas_control.py` is NOT a no-hardware unit test**: it opens a real Arduino serial connection and sends a 10-second gas-on command. Do not run it casually or in CI.

## 3. Set the ports and channels

| Physical port | Use |
| --- | --- |
| 1 | Flush |
| 2, 3, 4, 5, 6, 11 | Available stock inputs (choose four distinct ports in GUI) |
| 7 | Cell output 1 |
| 8 | Air chase *only* |
| 9 | Cell output 2 |
| 10 | Cell output 3 |
| 12 | Waste |

The shared nitrogen solenoid is not routed through the rotary valve. Its manifold must physically reach every cell intended for purging. The software cannot selectively purge one output through this valve.

In **Hardware + Stocks**, set the pump COM port and gas controller COM port, Bio-Logic device ID, data and template directories, the four stock solutions, the output-to-channel mapping and electrode/enzyme labels. The OLECOM channel IDs entered in the GUI are **zero-based** (e.g., 0, 1, 2). They must be unique for the three outputs.

Use experimental recipes with fractions from 0 to 1 that sum to 1.000. Keep solution volume at or below 5 mL for the configured syringe. Double-check the port-to-chemical mapping and compatibility with the actual installed plumbing.

## 4. Screening sequence

1. Define the stocks and outputs, then create an **umbrella job** with a mixture and electrochemical technique for each selected output.
2. Optionally configure initial saturation time and cell-purge time. Each umbrella job independently enables/disables its shared gas purge.
3. For CV/CVA, select scan rates and, optionally, the scan-rate boundaries at which common gas purging should occur. The purge is executed between measurement stages, after all active measurement channels in that stage have finished.
4. On execution, the controller connects gas and fluidics hardware, optionally starts an initial purge, prepares each output sequentially, performs an air chase on port 8, optionally purges all manifold-connected cells, and performs the Bio-Logic measurements concurrently by channel.
5. It logs and cleans between jobs and can perform optional overnight fill. Use STOP to request cancellation; carefully inspect instrument state afterward.

## 5. Generated files

- Run-event logs: normally `%LOCALAPPDATA%\FlowBot\Logs\flowbot_umbrella_*.csv` on Windows, with timestamp/thread/event columns. If the path fails the app attempts a shorter local path and warns.
- Bio-Logic data: `.mpr` data and generated `.mps` settings files in the **Data directory**. Files are only expected during an actual Bio-Logic run, not simulation.
- Experiment metadata: `FlowBot_experiment_metadata.csv` in the Data directory, with job, mixture, enzyme, technique, channel, output and saved file names.
- Queue configurations: optional JSON files saved explicitly from the GUI. Treat real experiments' configuration JSON files as potentially sensitive and do not add them to Git without reviewing.

## 6. What this package does *not* establish

- Actual instrument compatibility for all devices, firmware and Python versions;
- That liquid-delivery calibration, line volume or cross-contamination meet your experimental tolerances;
- That all connected cells receive an equal nitrogen flow;
- That the Arduino firmware is flashed or watchdog-tested;
- That templates match every EC-Lab version or installed Bio-Logic instrument;
- That simulated electrochemical results represent real bioelectrocatalysis data.

The supplied package was verified using source inspection, bytecode compilation, and the nine existing no-hardware Python unit tests. A live lab acceptance test and a saved reference environment are still needed for full reproducibility.
