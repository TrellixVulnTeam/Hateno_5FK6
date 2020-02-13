#!/bin/sh

#SBATCH --job-name=$FIRST_GLOBALSETTING_JOB_NAME
#SBATCH --mem=${SUM_GLOBALSETTING_MEMORY}G
#SBATCH --time=$SUMTIME_GLOBALSETTING_TIME
#SBATCH --nodes=$SUM_GLOBALSETTING_NODES
#SBATCH --partition=$JOB_PARTITION
#SBATCH --output=$JOBS_OUTPUT_FILENAME
#SBATCH --mail-type=ALL
#SBATCH --mail-user=$NOTIFICATIONS_EMAIL

cd $SLURM_SUBMIT_DIR

source /etc/profile.d/modules.sh
module load openmpi/gcc/64/1.10.7

mpirun -np $SLURM_NNODES $PARALLEL
