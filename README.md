# trex-fitter

## Getting started

https://trexfitter-docs.web.cern.ch/trexfitter-docs/latest/  (if ATLAS access)

git clone  https://github.com/OlivierSalin/VBS_SemiLep_TRexFitter.git

Run command to setup the environment:
```
setupATLAS
asetup StatAnalysis,0.7.3
```
## Run Plot only:
`trex-fitter nwd filename.config`


## Important settings at this stage of the analysis:

Run from ntuples: `trex-fitter nwdfp VBS_2lep_fit_ntuples.config`

### Different jobs
- For EFT Fit (POI set to 0.0): VBS_2lep_EFT_Ntuples_FT0.config
- For prefit yield with FT0=1.0e-12, and plots (POI set to 0.0): VBS_2lep_EFT_Ntuples_FT0_Yield.config (Values for fit are meaningless in this config only plot)

### JOB block
For now only NTuples: `VBS_2lep_EFT_Ntuples_FT0.config`, histos: `VBS_2lep_fit_histos.config`

1. Notice the definition of `MCweight`: the histograms produced by fastframe already considered `lumi * xSection / sumWeights`, therefore only the normal MC weight is needed here; for ntuples, `normal MC weights * lumi * xSection / sumWeights` is calculated together in fastframe (=[`weight_total_NOSYS`](https://gitlab.cern.ch/atlas-amglab/fastframes/-/blob/main/Root/MainFrame.cc?ref_type=heads#L372)) -- save this branch to the tree and use it as the `MCweight` in this block.

2. Use NORMSIGin the `PlotOptions` to get the tiny signals scaled to a visible line


### Sample block

- For EFT fit we are setting Wjets, Zjets, Top, QCDVV and EWK VVjj signal type to BACKGROUND
Only aQGC operator (QUAD only for now) type is set to SIGNAL. One operatator at a time

### FIT block
For now we are fitting with ASIMOV data
- `FitBlind: TRUE` (all norm factor are fixed to 1)
- Likelihood scan parameters to be set:

  doLHscan: mu_FT0
  LHscanMin: -0.4
  LHscanMax: 0.4
  LHscanSteps: 20


### REGIONS block
For histograms: all selections are done at the fastframe step; for ntuples, the common selections are done there, SR-CR definitions need to be added to this block

- For all regions set DataType: ASIMOV
- For SR_HP and SR_LP, we are fitting on m_{VV} variables (best for aQGC) --> binning to be optimised
- For Control region, using mjj variables 

### NORM FACTORS block
For now we are doing a signal strength like fit for QUAD aQGC operator --> µ(FT0^{2})
- We define an expression for f_{T0} in the Norm Factor to have the fit and likelihood scan 
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





## For reweighted EFT samples

The template configs are in `configs/EFT`. 

### Database for the EFT weight index
In `utils`, we have the txt and json versions of the EFT weights. In case anything in the text file is changed, we need to regenerate the json file with `scripts/extract_mcweights.py`

### Apply the weights in the TRexFitter config
To generate a single config for a specific operator, we can use `scripts/generate_config.py`. The flag `-o` indicates the operator (e.g., FT0), and the flag `-l` is for the lepton channel (choose from 0, 1, 2 and 012).

Before generating the config, make sure all the file paths are set correctly, including:
1. the `TEMPLATE_CONFIG` dictionary in L15-20 of the `generate_config.py`, make sure they point to the real location of your templates

2. L118 of `generate_config.py`, as well as all lines in the template configs that point to a "NtuplePath".

3. L168 of `generate_config.py`. This line should point to the json database generated in the last step.

4. L179 of `generate_config.py`. Select a good place to save the output config.

This script now generate the likelihood scan config for a single operator (QUAD term). We will make some modifications when we want to use it for other terms, mainly by changing the templates.

### Massive generation of the config
Simply loop over the python script.
