from os.path import join

FAAS_ROOT="/lhome/trulsas/faas-profiler"
WORKLOAD_SPECS=join(FAAS_ROOT, "specs", "workloads")
#FAAS_ROOT="/home/truls/uni/phd/faas-profiler"
WSK_PATH = "wsk"
OPENWHISK_PATH = "/lhome/trulsas/openwhisk"

#: Location of output data
DATA_DIR = join(FAAS_ROOT, "..", "profiler_results")
