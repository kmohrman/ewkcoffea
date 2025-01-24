import yaml
import json
import os

import uproot
from coffea.nanoevents import NanoAODSchema
from coffea.dataset_tools import preprocess, apply_to_fileset

import skimmer_processor as sp

def read_file(filename):
    with open(filename) as f:
        content = f.readlines()
    content = [x.strip() for x in content]
    return content


if __name__ == '__main__':

    ###### Get info from the input jsons ######

    # Get the prefix and json names from the cfg file
    prefix = ""
    json_lst = []
    lines = read_file("samples.cfg")
    for line in lines:
        if line == "": continue
        elif line.startswith("prefix:"):
            prefix = line.split()[1]
        else:
            json_lst.append(line)

    # Build a sample dict with all info in the jsons
    samples_dict = {}
    for json_name in json_lst:
        with open(json_name) as jf:
            samples_dict[json_name] = json.load(jf)

    # Make the dataset object the processor wants
    #print(samples_dict)
    dataset_dict = {}
    for json_path in samples_dict.keys():
        tag = json_path.split("/")[-1][:-5]
        dataset_dict[tag] = {}
        dataset_dict[tag]["files"] = {}
        for filename in samples_dict[json_path]["files"]:
            fullpath = prefix+filename
            dataset_dict[tag]["files"][fullpath] = "Events"
    print(dataset_dict)


    ###### Run ######

    # Run preprocess
    print("Running preprocessing")  # To obtain file splitting
    dataset_runnable, _ = preprocess(
        dataset_dict,
        align_clusters=False,
        step_size=100_000,  # You may want to set this to something slightly smaller to avoid loading too much in memory
        files_per_batch=1,
        skip_bad_files=True,
        save_form=False,
    )


    # Run apply_to_fileset
    print("Computing dask task graph")
    skimmed_dict = apply_to_fileset(
        sp.make_skimmed_events, dataset_runnable, schemaclass=NanoAODSchema
    )


    # Executing task graph and saving
    print("Executing task graph and saving")
    for dataset, skimmed in skimmed_dict.items():
        skimmed = sp.uproot_writeable(skimmed)
        skimmed = skimmed.repartition(
            n_to_one=1_000
        )  # Reparititioning so that output file contains ~100_000 eventspartition
        uproot.dask_write(
            skimmed,
            destination="skimtest/",
            prefix=f"{dataset}/skimmed",
        )


