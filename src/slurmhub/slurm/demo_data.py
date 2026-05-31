"""Hand-crafted fixture data for the ``--demo`` flag.

Used by :class:`slurmhub.slurm.ssh.DemoSSHClient` to drive the TUI
without an SSH connection. The data mirrors the wire format the real
Slurm commands emit, so the existing parsers consume it unmodified.
"""

from __future__ import annotations

DEMO_HOST = "demo-cluster.example.org"
DEMO_USERNAME = "demo-user"

# ── squeue / sacct ───────────────────────────────────────────────────
# Format: %i|%j|%T|%M|%Z|%b|%V|%C|%m  (id|name|state|time|workdir|gres|submit|cpus|mem)
SQUEUE_OUTPUT = "\n".join(
    [
        "421578|train_resnet50|RUNNING|1-04:32:11|/home/demo-user/projects/vision-models|gpu:l40s:4|2026-05-21T03:08:11|16|128G",
        "421579|eval_transformer|RUNNING|03:14:22|/home/demo-user/projects/nlp-bench|gpu:a100:2|2026-05-22T04:55:33|8|64G",
        "421580|preprocess_data|RUNNING|00:42:08|/scratch/demo-user/datasets/imagenet|(null)|2026-05-22T08:11:41|32|96G",
        "421612|finetune_llama|PENDING|0:00|/home/demo-user/projects/llama-ft|gpu:a100:8|2026-05-22T08:14:03|32|512G",
        "421613|hyperparam_sweep|PENDING|0:00|/home/demo-user/projects/hpo|gpu:l40s:1|2026-05-22T09:02:45|4|24G",
    ]
)

# squeue --noheader -o "%T" (cluster-wide state counts)
SQUEUE_CLUSTER_STATES = "\n".join(
    ["RUNNING"] * 86 + ["PENDING"] * 23 + ["COMPLETING"] * 4
)

# squeue --me -t PENDING --noheader -o "%i|%r|%Q|%V|%q"
SQUEUE_PENDING_DETAILS = "\n".join(
    [
        "421612|Priority|9842|2026-05-22T08:14:03|gpu-long",
        "421613|Resources|9710|2026-05-22T09:02:45|gpu-short",
    ]
)

# squeue -t PENDING --noheader -o "%Q|%i" --sort=-Q
SQUEUE_QUEUE_RANKS = "\n".join(
    [
        "10402|419988",
        "10211|420331",
        "9999|421044",
        "9842|421612",
        "9710|421613",
        "9501|421701",
        "9322|421888",
    ]
)

# sacct -X --format=JobID,JobName,State,Elapsed,Submit,NCPUS,ReqMem,WorkDir --units=M -n -P
# Pipe-delimited: JobID|JobName|State|Elapsed|Submit|NCPUS|ReqMem|WorkDir
SACCT_OUTPUT = "\n".join(
    [
        "421421|train_resnet50|COMPLETED|06:12:44|2026-05-22T07:01:00|16|128G|/home/demo-user/projects/vision-models",
        "421502|eval_transformer|COMPLETED|01:55:18|2026-05-23T11:20:00|8|64G|/home/demo-user/projects/nlp-bench",
        "421561|cuda_smoke_test|FAILED|00:00:34|2026-05-24T09:15:00|4|24G|/home/demo-user/projects/scratch",
        "421577|preprocess_data|CANCELLED|00:08:11|2026-05-25T14:02:00|32|96G|/scratch/demo-user/datasets/imagenet",
    ]
)

# ── scontrol show job ────────────────────────────────────────────────
SCONTROL_JOBS: dict[str, str] = {
    "421578": (
        "JobId=421578 JobName=train_resnet50\n"
        "   UserId=demo-user(1001) GroupId=demo-user(1001) MCS_label=N/A\n"
        "   Priority=10120 Nice=0 Account=ml-research QOS=gpu-long\n"
        "   JobState=RUNNING Reason=None Dependency=(null)\n"
        "   Requeue=1 Restarts=0 BatchFlag=1 Reboot=0 ExitCode=0:0\n"
        "   RunTime=1-04:32:11 TimeLimit=2-00:00:00 TimeMin=N/A\n"
        "   SubmitTime=2026-05-21T03:08:11 EligibleTime=2026-05-21T03:08:11\n"
        "   StartTime=2026-05-21T03:09:42 EndTime=2026-05-23T03:09:42 Deadline=N/A\n"
        "   Partition=gpu NodeList=node-gpu-04\n"
        "   ReqTRES=cpu=16,mem=128G,node=1,billing=16,gres/gpu=4,gres/gpu:l40s=4\n"
        "   AllocTRES=cpu=16,mem=128G,node=1,billing=16,gres/gpu=4,gres/gpu:l40s=4\n"
        "   NumNodes=1 NumCPUs=16 NumTasks=1 CPUs/Task=16 ReqB:S:C:T=0:0:*:*\n"
        "   Command=/home/demo-user/projects/vision-models/scripts/train.sh\n"
        "   WorkDir=/home/demo-user/projects/vision-models\n"
        "   StdErr=/home/demo-user/projects/vision-models/logs/421578.err\n"
        "   StdIn=/dev/null\n"
        "   StdOut=/home/demo-user/projects/vision-models/logs/421578.out\n"
    ),
    "421579": (
        "JobId=421579 JobName=eval_transformer\n"
        "   UserId=demo-user(1001) Priority=10018 Account=ml-research QOS=gpu-short\n"
        "   JobState=RUNNING Reason=None\n"
        "   RunTime=03:14:22 TimeLimit=06:00:00\n"
        "   SubmitTime=2026-05-22T04:55:33 StartTime=2026-05-22T04:56:14\n"
        "   Partition=gpu NodeList=node-gpu-02\n"
        "   ReqTRES=cpu=8,mem=64G,node=1,gres/gpu=2,gres/gpu:a100=2\n"
        "   AllocTRES=cpu=8,mem=64G,node=1,gres/gpu=2,gres/gpu:a100=2\n"
        "   NumNodes=1 NumCPUs=8 NumTasks=1 CPUs/Task=8\n"
        "   Command=/home/demo-user/projects/nlp-bench/eval.sh\n"
        "   WorkDir=/home/demo-user/projects/nlp-bench\n"
        "   StdErr=/home/demo-user/projects/nlp-bench/logs/421579.err\n"
        "   StdOut=/home/demo-user/projects/nlp-bench/logs/421579.out\n"
    ),
    "421580": (
        "JobId=421580 JobName=preprocess_data\n"
        "   UserId=demo-user(1001) Priority=8200 Account=data-eng QOS=cpu-default\n"
        "   JobState=RUNNING Reason=None\n"
        "   RunTime=00:42:08 TimeLimit=04:00:00\n"
        "   SubmitTime=2026-05-22T08:11:41 StartTime=2026-05-22T08:12:02\n"
        "   Partition=cpu NodeList=node-cpu-12\n"
        "   ReqTRES=cpu=32,mem=96G,node=1\n"
        "   AllocTRES=cpu=32,mem=96G,node=1\n"
        "   NumNodes=1 NumCPUs=32 NumTasks=1 CPUs/Task=32\n"
        "   Command=/scratch/demo-user/datasets/imagenet/prep.sh\n"
        "   WorkDir=/scratch/demo-user/datasets/imagenet\n"
        "   StdErr=/scratch/demo-user/datasets/imagenet/prep.err\n"
        "   StdOut=/scratch/demo-user/datasets/imagenet/prep.out\n"
    ),
    "421612": (
        "JobId=421612 JobName=finetune_llama\n"
        "   UserId=demo-user(1001) Priority=9842 Account=ml-research QOS=gpu-long\n"
        "   JobState=PENDING Reason=Priority\n"
        "   RunTime=00:00:00 TimeLimit=1-12:00:00\n"
        "   SubmitTime=2026-05-22T08:14:03\n"
        "   Partition=gpu\n"
        "   ReqTRES=cpu=32,mem=512G,node=1,gres/gpu=8,gres/gpu:a100=8\n"
        "   NumNodes=1 NumCPUs=32 NumTasks=1 CPUs/Task=32\n"
        "   Command=/home/demo-user/projects/llama-ft/ft.sh\n"
        "   WorkDir=/home/demo-user/projects/llama-ft\n"
        "   StdErr=/home/demo-user/projects/llama-ft/logs/421612.err\n"
        "   StdOut=/home/demo-user/projects/llama-ft/logs/421612.out\n"
    ),
    "421613": (
        "JobId=421613 JobName=hyperparam_sweep\n"
        "   UserId=demo-user(1001) Priority=9710 Account=ml-research QOS=gpu-short\n"
        "   JobState=PENDING Reason=Resources\n"
        "   RunTime=00:00:00 TimeLimit=02:00:00\n"
        "   SubmitTime=2026-05-22T09:02:45\n"
        "   Partition=gpu\n"
        "   ReqTRES=cpu=4,mem=24G,node=1,gres/gpu=1,gres/gpu:l40s=1\n"
        "   NumNodes=1 NumCPUs=4 NumTasks=1 CPUs/Task=4\n"
        "   Command=/home/demo-user/projects/hpo/sweep.sh\n"
        "   WorkDir=/home/demo-user/projects/hpo\n"
        "   StdErr=/home/demo-user/projects/hpo/logs/421613.err\n"
        "   StdOut=/home/demo-user/projects/hpo/logs/421613.out\n"
    ),
}

# sstat --format=MaxRSS -j <id>.batch (running jobs only)
SSTAT_OUTPUTS: dict[str, str] = {
    "421578": "  94327112K",
    "421579": "  41280088K",
    "421580": "  60113920K",
}

# srun nvidia-smi --query-gpu=index,name,utilization.gpu,memory.used,memory.total
NVIDIA_SMI_OUTPUTS: dict[str, str] = {
    "421578": (
        "0, NVIDIA L40S, 94, 41024, 46068\n"
        "1, NVIDIA L40S, 89, 39870, 46068\n"
        "2, NVIDIA L40S, 91, 40232, 46068\n"
        "3, NVIDIA L40S, 87, 39512, 46068"
    ),
    "421579": (
        "0, NVIDIA A100-SXM4-80GB, 76, 52214, 81920\n"
        "1, NVIDIA A100-SXM4-80GB, 72, 50872, 81920"
    ),
}

# ── sinfo ────────────────────────────────────────────────────────────
# Format: %N|%R|%T|%C|%e|%m|%G|%E  (per node)
SINFO_NODES = "\n".join(
    [
        "node-gpu-01|gpu|allocated|64/0/0/64|24576|524288|gpu:l40s:4|",
        "node-gpu-02|gpu|mixed|56/8/0/64|112400|524288|gpu:a100:4|",
        "node-gpu-03|gpu|idle|0/64/0/64|488000|524288|gpu:a100:8|",
        "node-gpu-04|gpu|allocated|64/0/0/64|18400|524288|gpu:l40s:4|",
        "node-gpu-05|gpu|drain|0/64/0/64|496000|524288|gpu:a100:8|Cooling issue",
        "node-cpu-10|cpu|mixed|72/56/0/128|410000|1048576|(null)|",
        "node-cpu-11|cpu|idle|0/128/0/128|1040000|1048576|(null)|",
        "node-cpu-12|cpu|allocated|128/0/0/128|82000|1048576|(null)|",
        "node-cpu-13|cpu|idle|0/128/0/128|1042000|1048576|(null)|",
        "node-cpu-14|cpu|down|0/0/128/128|0|1048576|(null)|Failed boot",
    ]
)

# Format: %R|%D|%C|%G|%m|%a  (per partition)
SINFO_PARTITIONS = "\n".join(
    [
        "gpu|5|184/136/0/320|gpu:a100:20,gpu:l40s:8|524288|up",
        "cpu|5|200/384/128/640|(null)|1048576|up",
    ]
)

# ── tail logs ────────────────────────────────────────────────────────

_LOG_TRAIN = """\
[2026-05-22 11:14:02] Epoch 18/40 | step 12834 | loss=0.4823 | acc=0.7619 | lr=0.00065
[2026-05-22 11:14:18] Epoch 18/40 | step 12848 | loss=0.4791 | acc=0.7644 | lr=0.00065
[2026-05-22 11:14:34] Epoch 18/40 | step 12862 | loss=0.4770 | acc=0.7651 | lr=0.00065
[2026-05-22 11:14:50] Epoch 18/40 | step 12876 | loss=0.4742 | acc=0.7672 | lr=0.00065
[2026-05-22 11:15:06] Epoch 18/40 | step 12890 | loss=0.4718 | acc=0.7689 | lr=0.00065
[2026-05-22 11:15:22] Epoch 18/40 | step 12904 | loss=0.4690 | acc=0.7702 | lr=0.00065
[2026-05-22 11:15:38] Epoch 18/40 | step 12918 | loss=0.4661 | acc=0.7714 | lr=0.00065
[2026-05-22 11:15:54] Epoch 18/40 | step 12932 | loss=0.4633 | acc=0.7726 | lr=0.00065
[2026-05-22 11:16:10] checkpoint saved: ckpts/resnet50_e18_s12932.pt
[2026-05-22 11:16:11] gpu memory: 39.8/46.1 GiB | utilization: 91%
[2026-05-22 11:16:27] Epoch 18/40 | step 12946 | loss=0.4601 | acc=0.7741 | lr=0.00065
[2026-05-22 11:16:43] Epoch 18/40 | step 12960 | loss=0.4577 | acc=0.7755 | lr=0.00065
[2026-05-22 11:16:59] Epoch 18/40 | step 12974 | loss=0.4549 | acc=0.7769 | lr=0.00065
[2026-05-22 11:17:15] Epoch 18/40 | step 12988 | loss=0.4523 | acc=0.7783 | lr=0.00065
[2026-05-22 11:17:31] Epoch 18/40 | step 13002 | loss=0.4501 | acc=0.7793 | lr=0.00065
"""

LOG_OUTPUTS: dict[str, str] = {
    "/home/demo-user/projects/vision-models/logs/421578.out": _LOG_TRAIN,
    "/home/demo-user/projects/vision-models/logs/421578.err": (
        "[2026-05-22 11:16:11] WARN: torch.distributed: skipping rank synchronization step\n"
        "[2026-05-22 11:16:43] WARN: dataloader workers exited: respawning (2/8)\n"
    ),
    "/home/demo-user/projects/nlp-bench/logs/421579.out": (
        "[2026-05-22 11:14:08] benchmark glue/cola batch 142/512\n"
        "[2026-05-22 11:14:24] benchmark glue/cola batch 156/512\n"
        "[2026-05-22 11:14:40] benchmark glue/cola batch 170/512\n"
        "[2026-05-22 11:14:56] benchmark glue/cola batch 184/512 | mcc=0.612\n"
        "[2026-05-22 11:15:12] benchmark glue/cola batch 198/512\n"
        "[2026-05-22 11:15:28] benchmark glue/sst2 batch 12/872\n"
    ),
    "/scratch/demo-user/datasets/imagenet/prep.out": (
        "[2026-05-22 11:15:42] processed 81920/1281167 images\n"
        "[2026-05-22 11:15:58] processed 83968/1281167 images\n"
        "[2026-05-22 11:16:14] processed 86016/1281167 images\n"
        "[2026-05-22 11:16:30] processed 88064/1281167 images\n"
        "[2026-05-22 11:16:46] processed 90112/1281167 images\n"
    ),
}

# ── batch script ─────────────────────────────────────────────────────
BATCH_SCRIPTS: dict[str, str] = {
    "421578": """\
#!/bin/bash
#SBATCH --job-name=train_resnet50
#SBATCH --account=ml-research
#SBATCH --partition=gpu
#SBATCH --gres=gpu:l40s:4
#SBATCH --cpus-per-task=16
#SBATCH --mem=128G
#SBATCH --time=2-00:00:00
#SBATCH --output=logs/%j.out
#SBATCH --error=logs/%j.err

set -euo pipefail
module purge
module load cuda/12.4 pytorch/2.3

srun python -u train.py \\
    --config configs/resnet50.yaml \\
    --epochs 40 \\
    --batch-size 256 \\
    --lr 0.00065 \\
    --checkpoint-dir ckpts/
""",
}

# A small default for any unknown job id
DEFAULT_BATCH_SCRIPT = """\
#!/bin/bash
#SBATCH --job-name=demo-job
#SBATCH --time=01:00:00

echo "demo batch script"
"""


def get_batch_script(job_id: str) -> str:
    return BATCH_SCRIPTS.get(job_id, DEFAULT_BATCH_SCRIPT)


def get_log_content(path: str) -> str:
    """Return canned log content for ``path`` or a generic placeholder."""
    if path in LOG_OUTPUTS:
        return LOG_OUTPUTS[path]
    return (
        f"[demo] no fixture log content registered for {path}\n"
        "[demo] showing placeholder lines so the viewer is non-empty\n"
        "[demo] line 1\n[demo] line 2\n[demo] line 3\n"
    )
