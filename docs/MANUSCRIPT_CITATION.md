# Referencing FlowBot in a manuscript

These statements can be adapted once the hardware methods, author list, paper citations, repository location and release version have been verified. **Do not present the simulated example as experimental data.**

## Example software/methods paragraph

> Automated solution preparation and electrochemical measurements were performed using an in-house FlowBot screening platform. A programmable syringe pump and 12-port valve delivered defined mixtures of stock solutions to three electrochemical cells. Following solution preparation and an optional common nitrogen-purge step, electrochemical measurements were initiated concurrently on three channels of a Bio-Logic potentiostat. The platform managed the experimental queue, electrochemical settings, and time-stamped run records. The fluidics-control approach was adapted from the eLab API [eLab citation], and earlier Bio-Logic automation development drew on Easy-Biologic [Easy-Biologic citation]. In the deposited software release, Bio-Logic control was implemented using the biologic-com EC-Lab/OLECOM interface [biologic-com citation]. The FlowBot implementation and release used for data collection are available at [GitHub URL, version/DOI].

If the manuscript's experiments **always** purged the cells, replace "optional common nitrogen-purge step" with the verified protocol, and specify the real purge duration and number of replicates as appropriate. Avoid conflating the order of experiments with the scheduling algorithm: fluidic preparation is sequential, while assigned electrochemical channels are started concurrently.

## Example software availability statement

> The Python source code for the FlowBot bioelectrocatalysis screening platform, including the graphical interface, experimental scheduler, fluidics-control integration, Bio-Logic measurement controller, simulated workflow, and documentation, is available at [repository URL]. The software version used in this study is [release tag or commit hash]; archived version [DOI, if assigned]. Instrument-specific software and firmware are required for physical operation and are not redistributed in this repository.

## What to cite

1. **FlowBot** — this repository, version/commit and eventual archive DOI. GitHub's "Cite this repository" panel is generated from `CITATION.cff`.
2. **eLab API** — https://github.com/jrlLAB/elabAPI; cite the original authors and, if available, a formal publication relevant to the specific implementation you used.
3. **Easy-Biologic** — https://github.com/bicarlsen/easy-biologic; credit Brian Carlsen and the original repository as part of the development provenance. The source package presently does not import it.
4. **biologic-com** — https://github.com/jdhuang-csm/biologic-com; the repository providing the imported `biocom` OLECOM interface.
5. **Instrument and firmware versions** — include Bio-Logic model, EC-Lab version, Python/interpreter version, pump/valve and solenoid implementation, and appropriate device control details in Supporting Information where possible. The uploaded controller sets `EC_LAB_VERSION = "11.50"`, which is a software constant rather than independent proof of the laboratory's installed EC-Lab version.

**Citation checklist:** update the title and full author list as required, record the date/release and GitHub URL, verify the original publication citations, and avoid asserting validation or copyright status that has not been documented.
