#!/bin/bash -l
# Author: Xuan Binh
#SBATCH --job-name=abaqusArray
#SBATCH --output=%j.out
#SBATCH --error=%j.err
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=40
#SBATCH --mem-per-cpu=5000
#SBATCH --time=01:00:00
#SBATCH --partition=gpu
#SBATCH --gres=gpu:v100:1
#SBATCH --account=project_2007935
#SBATCH --mail-type=ALL
#SBATCH --mail-user=binh.nguyen@aalto.fi

export OMP_NUM_THREADS=$SLURM_CPUS_PER_TASK
unset SLURM_GTIDS
module purge
module load abaqus/2022	

### Change to the work directory
fullpath=$(sed -n ${SLURM_ARRAY_TASK_ID}p linux_slurm/array_initial_file.txt) 
cd ${fullpath}

CPUS_TOTAL=$(( $SLURM_NTASKS*$SLURM_CPUS_PER_TASK ))

mkdir tmp_$SLURM_JOB_ID_${SLURM_ARRAY_TASK_ID}

abq2022 job=geometry.inp cpus=$CPUS_TOTAL gpus=1 scratch=tmp_$SLURM_JOB_ID_${SLURM_ARRAY_TASK_ID} interactive

   