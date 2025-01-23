from coffea.nanoevents import NanoAODSchema
from coffea.dataset_tools import preprocess, apply_to_fileset
import awkward as ak
import dask_awkward as dak 
import dask
import uproot

def is_rootcompat(a):
    """Is it a flat or 1-d jagged array?"""
    t = dak.type(a)
    if isinstance(t, ak.types.NumpyType):
        return True
    if isinstance(t, ak.types.ListType) and isinstance(t.content, ak.types.NumpyType):
        return True

    return False


def uproot_writeable(events):
    """Restrict to columns that uproot can write compactly"""
    out_event = events[list(x for x in events.fields if not events[x].fields)]
    for bname in events.fields:
        if events[bname].fields:
            out_event[bname] = ak.zip(
                {
                    n: ak.without_parameters(events[bname][n])
                    for n in events[bname].fields
                    if is_rootcompat(events[bname][n])
                }
            )
    return out_event

def make_skimmed_events(events):

    ele = events.Electron
    muo = events.Muon
    nlep = ak.num(ele) + ak.num(muo)
    mask = nlep >= 4
    print("e+m",nlep.compute())

    return events[mask]

    ## Place your selection logic here
    #skimmed = events[<Your Skimming selection here>]
    ## Add your custom fields here
    #skimmed["my_new_field"] = 137*9.8
    #
    ## ak.without_field is not yet implemented in dask
    ## skimmed = ak.without_field(skimmed, ["DropField1", "DropField2"]) https://github.com/dask-contrib/dask-awkward/pull/508/files
    #skimmed_dropped = skimmed[
    #    list(
    #        set(
    #            x
    #            for x in skimmed.fields
    #            if x not in ["DropField1", "DropField2"]
    #        )
    #    )
    #]

    ## Returning the skimmed events
    #return skimmed_dropped


def analysis_processor(dataset_runnable):

    print("Running preprocessing")  # To obtain file splitting
    print("Computing dask task graph")
    skimmed_dict = apply_to_fileset(
        make_skimmed_events, dataset_runnable, schemaclass=NanoAODSchema
    )


    print("Executing task graph and saving")
    for dataset, skimmed in skimmed_dict.items():
        skimmed = uproot_writeable(skimmed)
        skimmed = skimmed.repartition(
            n_to_one=1_000
        )  # Reparititioning so that output file contains ~100_000 eventspartition
        uproot.dask_write(
            skimmed,
            destination="skimtest/",
            prefix=f"{dataset}/skimmed",
        )





