import yaml
import json
import os

import skimmer_processor as sp

def read_file(filename):
    with open(filename) as f:
        content = f.readlines()
    content = [x.strip() for x in content]
    return content


def run():

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
    #exit()

    dataset_runnable, _ = sp.preprocess(
        dataset_dict,
        #{
        #    "dataset1": {
        #        "files": {
        #            #"output_1.root": "Events" for i in range(0, 100) # How ever many 
        #            "output_1.root": "Events" ,
        #        }
        #    },
        #    #"dataset2": {
        #    #    "files": {
        #    #        f"path_to_file_{index}.root": "Events" for i in range(0, 200) # Another data set
        #    #    }
        #    #}
        #},
        align_clusters=False,
        step_size=100_000,  # You may want to set this to something slightly smaller to avoid loading too much in memory
        files_per_batch=1,
        skip_bad_files=True,
        save_form=False,
    )

    sp.analysis_processor(dataset_runnable)

run()
