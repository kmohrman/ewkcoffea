# Example run commands

# Process the copy of the files at UF (not xrd accessible)
#time python run_wwz4l.py ../../input_samples/cfgs/wwz_analysis/mc_sig_bkg_samples_hpg.cfg,../../input_samples/cfgs/wwz_analysis/data_samples_hpg.cfg --hist-list njets -x task_vine

# Process the copy of the files at UCSD (xrd accessible)
time python run_wwz4l.py ../../input_samples/cfgs/wwz_analysis/mc_sig_bkg_samples.cfg,../../input_samples/cfgs/wwz_analysis/data_samples.cfg --hist-list njets -x task_vine
