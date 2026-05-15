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

## Which config to use

- EFT fit (POI set to 0.0): `VBS_2lep_EFT_Ntuples_FT0.config`
- Prefit yield and plots (POI set to 0.0): `Yields_VBS_2lep_EFT_Ntuples_FT0.config`
    The fit values in this config are for plotting only, to see the aQGC signal yield.

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
