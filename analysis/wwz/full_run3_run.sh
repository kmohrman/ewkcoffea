# Some example run commands for R3 configs

# Run at scale (with futures) DO NOT RUN THIS ON LOGIN NODE AT UF!
#time python run_wwz4l.py ../../input_samples/cfgs/wwz_analysis/mc_sig_bkg_samples_run3.cfg,../../input_samples/cfgs/wwz_analysis/data_samples_run3.cfg -o wwz_run3_histos_nosyst -x futures -n 200

# Run at scale (with futures) locally on UAF -> WILL NOT WORK ON HPG!
time python run_wwz4l.py ../../input_samples/cfgs/wwz_analysis/mc_sig_bkg_samples_run3_uaf.cfg,../../input_samples/cfgs/wwz_analysis/data_samples_run3_uaf.cfg -o wwz_run3_histos_nosyst -x futures -n 200

# Run with the siphon on DO NOT RUN THIS ON LOGIN NODE AT UF!
#time python run_wwz4l.py ../../input_samples/cfgs/wwz_analysis/mc_sig_bkg_samples_run3.cfg -o wwz_run3_histos_siphon -x futures -n 200 --siphon

# Run at scale (with wq)
#time python run_wwz4l.py ../../input_samples/cfgs/wwz_analysis/mc_sig_bkg_samples_run3.cfg,../../input_samples/cfgs/wwz_analysis/data_samples_run3.cfg -o wwz_run3_histos --hist-list few
