# Repository Audit

## Overview
This audit summarizes the structure, integration points, build and automation scripts, and documentation coverage of the project. It is intended to give new contributors a quick map of the codebase and highlight opportunities for improvement.

## High-level structure
- **Build system:** Root `CMakeLists.txt` orchestrates a modular CMake build that pulls in helpers from `cmake/`, platform-specific fragments under `src`, and option definitions in `DefineOptions.cmake`.
- **Source code layout:** Core sources live in `src/`, with subdirectories for platform integrations (`osx/`, `win/`, `ppc64le/`), GUI layers (`gui/`, `views/`, `dtgtk/`), CLI tooling (`cli/`, `cltest/`), libraries (`libs/`, `external/`), and application entry point `main.c`.
- **Supporting assets:** Locales reside in `po/`, runtime data and sample inputs in `data/`, while `doc/` contains reference documentation and manpage material.
- **Packaging & tooling:** Deployment scripts sit under `packaging/`, and contributor tooling (IWYU, static analysis support) appears in `tools/`.

## Integration notes
- The generated configuration header `src/config.cmake.h` ties together optional feature toggles emitted by CMake.
- GUI modules depend on shared utilities in `src/common/` and `src/libs/`, and several components are dynamically registered through the module loader infrastructure in `src/control/`.
- External integrations (e.g., OpenCL, Lua, Map providers) are surfaced as optional CMake features defined in `DefineOptions.cmake` and toggled at configure time.

## Build & automation scripts
- `build.sh` provides a convenience wrapper around the CMake workflow, including feature flag management and cleanup helpers.
- Continuous integration and platform-specific build helpers live in `packaging/` and `tools/`, supplementing the canonical `cmake --build` invocations.

### Observed issue
- Fixed a logic typo in `build.sh` where the non-zero exit check for `/sbin/sysctl` used the invalid comparison operator `-neq`, which prevented correct fallback when the command failed.

## Documentation status
- `README.md` documents prerequisites and high-level build instructions, while `CONTRIBUTING.md` covers code style and contribution flow.
- `doc/` hosts topic-specific documentation (e.g., Lua API, module references), but an at-a-glance map of key subsystems was missing prior to this audit.

## Recommendations
1. **Automated validation:** Consider integrating shell linting (e.g., `shellcheck`) into CI for scripts under the project root and `tools/` to avoid regressions similar to the fixed typo.
2. **Subsystem handbooks:** Expand `doc/` with focused guides for critical modules (`src/control`, `src/libs`) to assist new contributors navigating the code paths.
3. **Script discoverability:** Link `build.sh` and other helper scripts from `README.md` or a dedicated developer setup guide to improve visibility for first-time builders.
