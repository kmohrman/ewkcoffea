#!/usr/bin/env python

import argparse
import json
import time
import cloudpickle
import gzip
import os
import dask
from distributed import Client

from coffea.dataset_tools import preprocess
from coffea.dataset_tools import apply_to_fileset
from coffea.dataset_tools import filter_files

from ndcctools.taskvine import DaskVine

import wwz4l

LST_OF_KNOWN_EXECUTORS = ["local","task_vine"]

if __name__ == '__main__':

    parser = argparse.ArgumentParser(description='You can customize your run')
    parser.add_argument('jsonFiles'        , nargs='?', default='', help = 'Json file(s) containing files and metadata')
    parser.add_argument('--executor','-x'  , default='dask', help = 'Which executor to use', choices=LST_OF_KNOWN_EXECUTORS)
    parser.add_argument('--prefix', '-r'   , nargs='?', default='', help = 'Prefix or redirector to look for the files')
    parser.add_argument('--test','-t'       , action='store_true'  , help = 'To perform a test, run over a few events in a couple of chunks')
    parser.add_argument('--pretend'        , action='store_true', help = 'Read json files but, not execute the analysis')
    parser.add_argument('--nworkers','-n'   , default=8  , help = 'Number of workers')
    parser.add_argument('--chunksize','-s' , default=100000, help = 'Number of events per chunk')
    parser.add_argument('--nchunks','-c'   , default=None, help = 'You can choose to run only a number of chunks')
    parser.add_argument('--outname','-o'   , default='plotsTopEFT', help = 'Name of the output file with histograms')
    parser.add_argument('--outpath','-p'   , default='histos', help = 'Name of the output directory')
    parser.add_argument('--treename'       , default='Events', help = 'Name of the tree inside the files')
    parser.add_argument('--do-errors'      , action='store_true', help = 'Save the w**2 coefficients')
    parser.add_argument('--do-systs', action='store_true', help = 'Compute systematic variations')
    parser.add_argument('--split-lep-flavor', action='store_true', help = 'Split up categories by lepton flavor')
    parser.add_argument('--skip-sr', action='store_true', help = 'Skip all signal region categories')
    parser.add_argument('--skip-cr', action='store_true', help = 'Skip all control region categories')
    parser.add_argument('--do-np'  , action='store_true', help = 'Perform nonprompt estimation on the output hist, and save a new hist with the np contribution included. Note that signal, background and data samples should all be processed together in order for this option to make sense.')
    parser.add_argument('--wc-list', action='extend', nargs='+', help = 'Specify a list of Wilson coefficients to use in filling histograms.')
    parser.add_argument('--hist-list', action='extend', nargs='+', help = 'Specify a list of histograms to fill.')
    parser.add_argument('--ecut', default=None  , help = 'Energy cut threshold i.e. throw out events above this (GeV)')
    parser.add_argument('--port', default='9123-9130', help = 'Specify the Work Queue port. An integer PORT or an integer range PORT_MIN-PORT_MAX.')


    args = parser.parse_args()
    jsonFiles  = args.jsonFiles
    prefix     = args.prefix
    executor   = args.executor
    dotest     = args.test
    nworkers   = int(args.nworkers)
    chunksize  = int(args.chunksize)
    nchunks    = int(args.nchunks) if not args.nchunks is None else args.nchunks
    outname    = args.outname
    outpath    = args.outpath
    pretend    = args.pretend
    treename   = args.treename
    do_errors  = args.do_errors
    do_systs   = args.do_systs
    split_lep_flavor = args.split_lep_flavor
    skip_sr    = args.skip_sr
    skip_cr    = args.skip_cr
    wc_lst = args.wc_list if args.wc_list is not None else []

    # Check if we have valid options
    if dotest:
        if executor == "futures":
            nchunks = 2
            chunksize = 10000
            nworkers = 1
            print('Running a fast test with %i workers, %i chunks of %i events'%(nworkers, nchunks, chunksize))
        else:
            raise Exception(f"The \"test\" option is not set up to work with the {executor} executor. Exiting.")


    # Set the threshold for the ecut (if not applying a cut, should be None)
    ecut_threshold = args.ecut
    if ecut_threshold is not None: ecut_threshold = float(args.ecut)

    if executor == "work_queue":
        # construct wq port range
        port = list(map(int, args.port.split('-')))
        if len(port) < 1:
            raise ValueError("At least one port value should be specified.")
        if len(port) > 2:
            raise ValueError("More than one port range was specified.")
        if len(port) == 1:
            # convert single values into a range of one element
            port.append(port[0])

    # Figure out which hists to include
    if args.hist_list == ["few"]:
        # Here we hardcode a reduced list of a few hists
        hist_lst = ["j0pt", "njets", "nbtagsl", "nleps", "met", "l0pt"]
    elif args.hist_list == ["cr"]:
        # Here we hardcode a list of hists used for the CRs
        hist_lst = ["lj0pt", "ptz", "met", "ljptsum", "l0pt", "l0eta", "l1pt", "l1eta", "j0pt", "j0eta", "njets", "nbtagsl", "invmass"]
    else:
        # We want to specify a custom list
        # If we don't specify this argument, it will be None, and the processor will fill all hists
        hist_lst = args.hist_list


    ### Load samples from json
    samplesdict = {}
    allInputFiles = []

    def LoadJsonToSampleName(jsonFile, prefix):
        sampleName = jsonFile if not '/' in jsonFile else jsonFile[jsonFile.rfind('/')+1:]
        if sampleName.endswith('.json'): sampleName = sampleName[:-5]
        with open(jsonFile) as jf:
            samplesdict[sampleName] = json.load(jf)
            samplesdict[sampleName]['redirector'] = prefix

    if isinstance(jsonFiles, str) and ',' in jsonFiles:
        jsonFiles = jsonFiles.replace(' ', '').split(',')
    elif isinstance(jsonFiles, str):
        jsonFiles = [jsonFiles]
    for jsonFile in jsonFiles:
        if os.path.isdir(jsonFile):
            if not jsonFile.endswith('/'): jsonFile+='/'
            for f in os.path.listdir(jsonFile):
                if f.endswith('.json'): allInputFiles.append(jsonFile+f)
        else:
            allInputFiles.append(jsonFile)

    # Read from cfg files
    for f in allInputFiles:
        if not os.path.isfile(f):
            raise Exception(f'[ERROR] Input file {f} not found!')
        # This input file is a json file, not a cfg
        if f.endswith('.json'):
            LoadJsonToSampleName(f, prefix)
        # Open cfg files
        else:
            with open(f) as fin:
                print(' >> Reading json from cfg file...')
                lines = fin.readlines()
                for l in lines:
                    if '#' in l:
                        l=l[:l.find('#')]
                    l = l.replace(' ', '').replace('\n', '')
                    if l == '': continue
                    if ',' in l:
                        l = l.split(',')
                        for nl in l:
                            if not os.path.isfile(l):
                                prefix = nl
                            else:
                                LoadJsonToSampleName(nl, prefix)
                    else:
                        if not os.path.isfile(l):
                            prefix = l
                        else:
                            LoadJsonToSampleName(l, prefix)

    fdict = {}
    nevts_total = 0
    for sname in samplesdict.keys():
        redirector = samplesdict[sname]['redirector']
        fdict[sname] = [(redirector+f) for f in samplesdict[sname]['files']]
        samplesdict[sname]['year'] = samplesdict[sname]['year']
        samplesdict[sname]['xsec'] = float(samplesdict[sname]['xsec'])
        samplesdict[sname]['nEvents'] = int(samplesdict[sname]['nEvents'])
        nevts_total += samplesdict[sname]['nEvents']
        samplesdict[sname]['nGenEvents'] = int(samplesdict[sname]['nGenEvents'])
        samplesdict[sname]['nSumOfWeights'] = float(samplesdict[sname]['nSumOfWeights'])
        if not samplesdict[sname]["isData"]:
            # Check that MC samples have all needed weight sums (only needed if doing systs)
            if do_systs:
                if ("nSumOfLheWeights" not in samplesdict[sname]):
                    raise Exception(f"Sample is missing scale variations: {sname}")
        # Print file info
        print('>> '+sname)
        print('   - isData?      : %s'   %('YES' if samplesdict[sname]['isData'] else 'NO'))
        print('   - year         : %s'   %samplesdict[sname]['year'])
        print('   - xsec         : %f'   %samplesdict[sname]['xsec'])
        print('   - histAxisName : %s'   %samplesdict[sname]['histAxisName'])
        print('   - options      : %s'   %samplesdict[sname]['options'])
        print('   - tree         : %s'   %samplesdict[sname]['treeName'])
        print('   - nEvents      : %i'   %samplesdict[sname]['nEvents'])
        print('   - nGenEvents   : %i'   %samplesdict[sname]['nGenEvents'])
        print('   - SumWeights   : %i'   %samplesdict[sname]['nSumOfWeights'])
        if not samplesdict[sname]["isData"]:
            if "nSumOfLheWeights" in samplesdict[sname]:
                print(f'   - nSumOfLheWeights : {samplesdict[sname]["nSumOfLheWeights"]}')
        print('   - Prefix       : %s'   %samplesdict[sname]['redirector'])
        print('   - nFiles       : %i'   %len(samplesdict[sname]['files']))
        for fname in samplesdict[sname]['files']: print('     %s'%fname)

    if pretend:
        print('pretending...')
        exit()


    processor_instance = wwz4l.AnalysisProcessor(samplesdict,wc_lst,hist_lst,ecut_threshold,do_errors,do_systs,split_lep_flavor,skip_sr,skip_cr)


    # Run the processor and get the output
    t_start = time.time()


    ####################################3
    ### coffea2023 ###

    #fdict = {"UL17_WWZJetsTo4L2Nu_forCI": ["/home/k.mohrman/coffea_dir/migrate_to_coffea2023_repo/ewkcoffea/analysis/wwz/output_1.root"]}

    # Get fileset
    fileset = {}
    for name, fpaths in fdict.items():
        fileset[name] = {}
        fileset[name]["files"] = {}
        for fpath in fpaths:
            fileset[name]["files"][fpath] = {"object_path": "Events"}
            fileset[name]["metadata"] = {"dataset": name}
    print(fileset)
    print("Number of datasets:",len(fdict))

    #### Run preprocess, build task graphs, compute ####

    t_before_with_Client_as_client = time.time()
    #with Client(n_workers=8, threads_per_worker=1) as client:
    with Client() as client:

        # Run preprocess
        print("\nRunning preprocess...")
        t_before_preprocess = time.time()
        dataset_runnable, dataset_updated = preprocess(
            fileset,
            step_size=50_000,
            align_clusters=False,
            files_per_batch=1,
            save_form=False,
        )
        dataset_runnable = filter_files(dataset_runnable)


        # Dump to a json
        #with gzip.open("dataset_runnable_test.json.gz", "wt") as fout:
        #    json.dump(dataset_runnable, fout)
        #exit()
        # Or load a json
        #with gzip.open("dataset_runnable_test_mar16_full.json.gz", "r") as f:
        #    dataset_runnable = json.load(f)


        t_before_applytofileset = time.time()
        # Run apply_to_fileset
        print("\nRunning apply_to_fileset...")
        histos_to_compute, reports = apply_to_fileset(
            processor_instance,
            dataset_runnable,
            uproot_options={"allow_read_errors_with_report": True},
            #parallelize_with_dask=True,
        )

        # Does not work
        #with gzip.open("histos_to_compute_full_mar25.json.gz", "wb") as fout:
        #    cloudpickle.dump(histos_to_compute, fout)

        # Check columns to be read
        #import dask_awkward as dak
        #print("\nRunning necessary_columns...")
        #columns_read = dak.necessary_columns(histos_to_compute[list(histos_to_compute.keys())[0]])
        #print(columns_read)

        # Compute
        t_before_compute = time.time()
        print("\nRunning compute...")

        if executor == "task_vine":
            print("Running with Task vine")
            m = DaskVine([9123,9128], name=f"coffea-vine-{os.environ['USER']}")
            proxy = m.declare_file(f"/tmp/x509up_u{os.getuid()}", cache=True)
            coutputs, reports = dask.compute(
                histos_to_compute,
                reports,
                scheduler=m.get,
                resources={"cores": 1},
                resources_mode=None,
                lazy_transfers=True,
                extra_files={proxy: "proxy.pem"},
                env_vars={"X509_USER_PROXY": "proxy.pem"},
            )

        else:
            coutputs, creports = dask.compute(histos_to_compute, reports)





    # Print timing info
    t_end = time.time()
    dt = t_end - t_start
    time_for_with_Client_as_client = t_before_preprocess - t_before_with_Client_as_client
    time_for_preprocess = t_before_applytofileset - t_before_preprocess
    time_for_applytofset = t_before_compute - t_before_applytofileset
    time_for_compute = t_end - t_before_compute
    print("\nTiming info:")
    print(f"\tTime for with Client() as client: {round(time_for_with_Client_as_client,3)}s , ({round(time_for_with_Client_as_client/60,3)}m)")
    print(f"\tTime for preprocess             : {round(time_for_preprocess,3)}s , ({round(time_for_preprocess/60,3)}m)")
    print(f"\tTime for apply to fileset       : {round(time_for_applytofset,3)}s , ({round(time_for_applytofset/60,3)}m)")
    print(f"\tTime for compute                : {round(time_for_compute,3)}s , ({round(time_for_compute/60,3)}m)")
    #print(f"\tSanity check, these should equal: {round(dt,3)} , {round(time_for_with_Client_as_client+time_for_preprocess+time_for_applytofset+time_for_compute,3)}")

    # Save the output
    if not os.path.isdir(outpath): os.system("mkdir -p %s"%outpath)
    out_pkl_file = os.path.join(outpath,outname+".pkl.gz")
    print(f"\nSaving output in {out_pkl_file}...")
    with gzip.open(out_pkl_file, "wb") as fout:
        cloudpickle.dump(coutputs, fout)
    print("Done!")
