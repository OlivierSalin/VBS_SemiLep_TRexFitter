# TRExFitter (VBS Semi-Leptonic, 2L)

This folder contains TRExFitter configuration files used to make plots and run EFT fits
for the VBS semi-leptonic 2-lepton channel.

Official documentation (ATLAS access):
https://trexfitter-docs.web.cern.ch/trexfitter-docs/latest/

## Quick start

Clone the repository:
```
git clone https://github.com/OlivierSalin/VBS_SemiLep_TRexFitter.git
```

Set up the ATLAS environment:
```
setupATLAS
asetup StatAnalysis,0.6.3
```

or use 
```
source Setup.sh
```

## Running TRExFitter

Plot-only (stacked histograms):
```
trex-fitter nwd filename.config
```

Run from ntuples:
```
trex-fitter nwdfp VBS_2lep_fit_ntuples.config
```

### Which config to use

- EFT fit (POI set to 0.0): `VBS_2lep_EFT_Ntuples_FT0.config`
- Prefit yield and plots (POI set to 0.0): `Yields_VBS_2lep_EFT_Ntuples_FT0.config`
    The fit values in this config are for plotting only, to see the aQGC signal yield.


## CL95 extraction

The script `CL95_aQGC_limit_yield.py` extracts the 95% CL limits from the NLL scan YAML
and writes a summary text file, yields tables, and a PNG curve with the 95% line and
vertical limits.

### Quick usage (folder mode)

Run from the `VBS_SemiLep_TRexFitter` directory and pass only the folder name that
contains `LHoodPlots/` and `Tables/`, the parameter should be the jobname of the .config file that we want to plot:
```
python3 CL95_aQGC_limit_yield.py --folder VBS_SemiLep_aQGC_FT0
```

The operator (FT0/FS0/FM0) is inferred from the folder name.

### Options

- `--folder <name>`: Folder name (relative to cwd) with `LHoodPlots/NLLscan_<op>.yaml`.
- `--op <FT0|FS0|FM0>`: Explicit operator (use this if you do not use `--folder`).
- `--ops <FT0 FS0 FM0>`: Multiple operators (combined output file).
- `--config <file>`: Read mVV_SR_HP binning from a TRExFitter config file.
- `--binning <csv>`: Comma-separated binning override (takes precedence over config).
- `--out_dir <dir>`: Output directory for results (default: `CL_95`).
- `--x_ticks <float>`: Change the x axis ticks range (tto be updated to avoid too crowded plots)
- `--x_line_CL <bool>`: Whether to draw vertical lines at the 95% CL crossings.
- `--Spe <tag>`: Optional selection tag to organize outputs under `CL_95/<tag>/`.

Example with explicit config and binning override:
```
python3 CL95_aQGC_limit_yield.py --folder VBS_SemiLep_aQGC_FT0 \
    --config VBS_2lep_EFT_Ntuples_FT0.config

python3 CL95_aQGC_limit_yield.py --folder VBS_SemiLep_aQGC_FT0 \
    --binning 0,500,1000,1500,2000,2500,3000,8000
```

### Outputs

By default outputs are written to `CL_95/` (or `CL_95/<Spe>/` if provided):

- `CL95_<op>.txt`: summary with CL95 limits, sources, regions used, and binning.
- `CL95_<op>_yields_prefit.csv`: yields table (prefit).
- `CL95_<op>_yields_prefit.xlsx`: yields table (prefit, if `openpyxl` installed).
- `CL95_<op>_curve.png`: NLL curve with the 95% CL line and vertical limits.
- `CL95_limits.txt`: plain one-line limits (e.g. `FT0:[left,right]`).

The text output includes a `nll_curve_plots` block pointing to the PNG path.



## Understanding the config blocks

### JOB block

- For now we run from ntuples: `VBS_2lep_EFT_Ntuples_FT0.config`
- The MC weight should be `weight_total_NOSYS` (stored in the ntuple). FastFrame already
    includes `lumi * xSection / sumWeights`, so this branch is the full per-event weight.
- Use `NORMSIG` in `PlotOptions` so small signals are visible on the plots.

### Sample block

- For the EFT fit, background samples are: Wjets, Zjets, Top, QCDVV, and EWK VVjj.
- Only the aQGC operator (QUAD term for now) is set to `SIGNAL`.
- Use one operator at a time.

### FIT block

- We fit with ASIMOV data for now.
- `FitBlind: TRUE` fixes all norm factors to 1 during the fit.
- Example likelihood scan settings:
```
doLHscan: mu_FT0
LHscanMin: -0.4
LHscanMax: 0.4
LHscanSteps: 20
```

### REGIONS block

- For histograms: selections are done in FastFrame.
- For ntuples: add SR/CR selections here.
- Set `DataType: ASIMOV` for all regions.
- SR_HP and SR_LP use `m_{VV}` (best for aQGC); binning still needs optimization.
- Control region uses `mjj`.

### NORM FACTORS block

We currently do a signal-strength-like fit for the QUAD aQGC term (mu for FT0 squared).
Example:
```
NormFactor: "FT0"
    Max: 3
    Min: -3
    Nominal: 0.0
    Samples: NONE
    Title: "f_{T0}"

NormFactor: "FT0_QUAD"
    Max: 10
    Min: 0
    Nominal: 0.0
    Samples: aQGC_FT0
    Expression: (FT0*FT0):FT0[0.0,-3,3]
    Title: "f_{T0} QUAD"
```







## Reweighted EFT samples

Template configs are in `configs/EFT`.

### EFT weight database

In `utils`, there are text and JSON versions of the EFT weights. If the text file changes,
regenerate the JSON with:
```
python scripts/extract_mcweights.py
```

### Generate a config for one operator

Use:
```
python scripts/generate_config.py -o FT0 -l 2
```

Check these paths before running:
1. `TEMPLATE_CONFIG` in `scripts/generate_config.py` (lines 15-20)
2. The `NtuplePath` entries (line ~118 and in the templates)
3. The JSON database path (line ~168)
4. Output path (line ~179)

### Generate many configs

Loop over the script for multiple operators or channels.
