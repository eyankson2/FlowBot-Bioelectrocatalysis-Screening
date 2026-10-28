# Software provenance, acknowledgements and licensing

## Origins and dependencies

The FlowBot screening software was developed using and modifying ideas and tools from the following open-source projects. **Acknowledgement does not imply the upstream authors developed this complete FlowBot system or endorse it.**

| Project | Upstream credit | Role in this release | Source/license information |
| --- | --- | --- | --- |
| [eLab API](https://github.com/jrlLAB/elabAPI) | Michael Pence, Gavin Hazen, Joaquín Rodríguez-López | `fluidics.py` imports `elab` and expects an `elab.SY01B` pump/valve controller. The lab-compatible `elab` implementation is **not bundled** here. | [eLab source](https://github.com/jrlLAB/elabAPI), [GPLv3 license](https://github.com/jrlLAB/elabAPI/blob/main/LICENSE) |
| [Easy-Biologic](https://github.com/bicarlsen/easy-biologic) | Brian Carlsen | Historical/technical foundation for Bio-Logic automation, as reported by the FlowBot developer. **No `easy_biologic` import** appears in the uploaded runnable files. | [Easy-Biologic repository](https://github.com/bicarlsen/easy-biologic) (repository contains MIT and Apache-2.0 license files; check the specific upstream revision) |
| [biologic-com](https://github.com/jdhuang-csm/biologic-com) | Its upstream developers/contributors | The `biocom` module is the *actual* dependency used to create `.mps` files and drive EC-Lab through OLECOM. | [biologic-com repository](https://github.com/jdhuang-csm/biologic-com) (review current upstream license/requirements) |
| Bio-Logic EC-Lab | Bio-Logic | Licensed vendor software, OLECOM server, instrument firmware, and native `.mps/.mpr` data handling | Vendor licensing applies; not supplied in this repository |

The distinction between *prior adaptation* and *current import* matters. Do not describe this release as communicating directly through Easy-Biologic's DLL API; `biologic_runner.py` actually imports `biocom.com.server` and uses the OLECOM connection to EC-Lab.

## Original development in FlowBot

The uploaded version implements integrated job scheduling for automated mediator/substrate solution preparation, three-output assignment and parallel electrochemical techniques, Arduino-solenoid purging, independently configurable simulation modes, configuration persistence, file/metadata logging, and safety-related STOP/cleanup behavior. These integrated application features should be attributed to the FlowBot development work, subject to identifying earlier code owners and collaborators.

## License status: check before public release

The upstream **eLab API is GPLv3**. The package therefore includes the **GPLv3 license text** as a conservative starting point for an open-source derivative distribution; it does not supersede upstream copyrights or grant licenses to vendor software. Verify the precise provenance and ownership of all modified eLab code and any copied source. The upstream Easy-Biologic repository advertises MIT and Apache-2.0 license texts; the actual set of obligations depends on any copied code and its version. This repository **does not contain vendored `elab`, `easy_biologic`, or `biocom` packages**.

Before changing the repository from private to public:

1. Confirm institutional/laboratory ownership and permission to distribute the FlowBot adaptation, especially if developed under sponsored research or institutional employment.
2. Establish which files or lines are copied or modified from each external project and preserve original copyright and license notices where needed.
3. Verify that the GPLv3 distribution choice is appropriate for **all** source files and any copied third-party modules; obtain legal/institutional guidance if unclear.
4. Confirm `.mps` templates may be publicly shared under your instrument/software terms and do not include proprietary or unpublished protocol parameters.
5. Remove or anonymize private results, unpublished protocols, restricted configurations, serial identifiers, credentials, and collaborator information before any new commit.
6. Ensure that paper coauthors and data/software owners agree to public disclosure and the citation/credit statements.

Do not assume that crediting a source in the README replaces license compliance. The project includes no vendor DLLs, no Arduino sketch, no lab-specific eLab fork, and no measured experiment datasets.
