from os.path import join

FAAS_ROOT="/lhome/trulsas/faas-profiler"
WORKLOAD_SPECS=join(FAAS_ROOT, "specs", "workloads")
#FAAS_ROOT="/home/truls/uni/phd/faas-profiler"
WSK_PATH = "wsk"
OPENWHISK_PATH = "/lhome/trulsas/openwhisk"

#: Location of output data
DATA_DIR = join(FAAS_ROOT, "..", "profiler_results")

SYSTEM_CPU_SET = "0,2,4,6,8,10,12,14,16,18,20,22,24,26,28,30"
