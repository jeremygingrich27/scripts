#!/usr/bin/env bash
# chain_vasp_launcher.sh
# Run inside a CALC directory that contains many POSCAR_scaled_* subfolders.
# The script interactively builds and submits a SLURM job that executes VASP
# in each POSCAR_scaled_* directory in sequence, copying selected files forward.

set -euo pipefail

ROOT=$PWD                 # Absolute path to current CALC directory
JOBSCRIPT="chain_vasp_jobscript.sh"

###############################################################################
# 1. Discover POSCAR_scaled_* directories
###############################################################################
mapfile -t ALL_DIRS < <(find . -maxdepth 1 -type d -name "POSCAR_scaled_*" | sort)

if [[ ${#ALL_DIRS[@]} -eq 0 ]]; then
  echo "No POSCAR_scaled_* directories found in $ROOT"
  exit 1
fi

echo "Found POSCAR_scaled_* directories:"
for i in "${!ALL_DIRS[@]}"; do
  d="${ALL_DIRS[i]#./}"
  echo "  [$i] $d"
done
echo

###############################################################################
# 2. Let user choose which directories to chain
###############################################################################
echo "Choose input method:"
echo "1) Choose individual indices (e.g. 0 2 4)"
echo "2) Choose range (start..end)"
read -rp "Select input method (1 or 2): " method
indices=()

if [[ "$method" == "1" ]]; then
  read -rp "Enter the indices of directories to chain, in order (space‑separated): " -a indices
elif [[ "$method" == "2" ]]; then
  read -rp "Enter start index: " start_idx
  read -rp "Enter end index:   " end_idx
  if ! [[ "$start_idx" =~ ^[0-9]+$ && "$end_idx" =~ ^[0-9]+$ ]]; then
    echo "Start and end must be integers."
    exit 1
  fi
  if (( start_idx < 0 || start_idx >= ${#ALL_DIRS[@]} || end_idx < 0 || end_idx >= ${#ALL_DIRS[@]} )); then
    echo "Indices out of range."
    exit 1
  fi
  if (( start_idx <= end_idx )); then
    for ((i=start_idx; i<=end_idx; i++)); do indices+=("$i"); done
  else
    for ((i=start_idx; i>=end_idx; i--)); do indices+=("$i"); done
  fi
else
  echo "Invalid input method."
  exit 1
fi

for idx in "${indices[@]}"; do
  if ! [[ "$idx" =~ ^[0-9]+$ ]] || (( idx < 0 || idx >= ${#ALL_DIRS[@]} )); then
    echo "Invalid index: $idx"
    exit 1
  fi
done

###############################################################################
# 3. SLURM resource prompts
###############################################################################
read -rp "Enter number of nodes     (e.g. 1):        " NODES
read -rp "Enter number of cores     (e.g. 128):      " CORES
read -rp "Enter queue/partition     (e.g. normal):   " QUEUE
read -rp "Enter walltime HH:MM:SS   (e.g. 48:00:00): " TIME
echo

###############################################################################
# 4. Build list of target directories
###############################################################################
DIRS=()
for idx in "${indices[@]}"; do
  d="${ALL_DIRS[idx]#./}"
  if [[ ! -d "$d" ]]; then
    echo "Directory does not exist: $d"
    exit 1
  fi
  DIRS+=("$d")
done

echo "Chaining over the following directories (in order):"
printf '  %s\n' "${DIRS[@]}"
echo

###############################################################################
# 5. Ask which files to copy forward
###############################################################################
FILES_TO_COPY=()

read -rp "Copy CHGCAR between steps? [y/N]: " ans
[[ "$ans" =~ ^[Yy]$ ]] && FILES_TO_COPY+=("CHGCAR")

read -rp "Copy WAVECAR between steps? [y/N]: " ans
[[ "$ans" =~ ^[Yy]$ ]] && FILES_TO_COPY+=("WAVECAR")

read -rp "Copy any additional files? (space-separated, leave blank for none): " -a extra_files
FILES_TO_COPY+=("${extra_files[@]}")

echo
echo "✅ Files that will be copied forward: ${FILES_TO_COPY[*]:-(none)}"
echo

# Prepare literal array expansions for jobscript
FILES_TO_COPY_LITERAL=$(printf '"%s" ' "${FILES_TO_COPY[@]}")
DIRS_LITERAL=$(printf '"%s" ' "${DIRS[@]}")

###############################################################################
# 6. Parse data 
###############################################################################

#RELAX="no"
#CP_VASPRUN="no"

#read -rp "Are these systems being relaxed? [y/N]: " ans
#[[ "$ans" =~ ^[Yy]$ ]] && $RELAX="yes"

#read -rp "Copy vasprun.xml?" ans
#[[ "$ans" =~ ^[Yy]$ ]] && $CP_VASPRUN="yes"

#echo
#echo "✅ Files that will be copied forward: ${FILES_TO_COPY[*]:-(none)}"
#echo


###############################################################################
# 7. Construct the SLURM jobscript
###############################################################################
cat > "$JOBSCRIPT" << EOF
#!/usr/bin/env bash
#SBATCH -J chain_vasp
#SBATCH -o chain_vasp.%j.out
#SBATCH -e chain_vasp.%j.err
#SBATCH -N $NODES
#SBATCH -n $CORES
#SBATCH -p $QUEUE
#SBATCH -t $TIME
#SBATCH -A PHY24018

module purge
module load intel/19.1.1  impi/19.0.9
module load vasp/6.3.0 
export OMP_NUM_THREADS=1

ROOT="\$PWD"
DIRS=($DIRS_LITERAL)
FILES_TO_COPY=($FILES_TO_COPY_LITERAL)

for ((i=0; i<\${#DIRS[@]}; i++)); do
  CUR="\${DIRS[i]}"
  echo "▶ Running step \$((i+1)) / \${#DIRS[@]} : \$CUR"
  cd "\$CUR"

  if (( i > 0 && \${#FILES_TO_COPY[@]} > 0 )); then
    echo "↪ Copying forward files from previous directory: \${DIRS[i-1]}"
    for file in "\${FILES_TO_COPY[@]}"; do
      cp -f "\$ROOT/\${DIRS[i-1]}/\$file" "\$file"
    done
  fi

  ibrun vasp_std
  rc=\$?
  if (( rc != 0 )); then
    echo "❌ VASP failed with code \$rc in \$CUR"
    exit \$rc
  fi
  touch COMPLETED
  cd "\$ROOT"
done

echo "🎉 All calculations finished successfully."

bash ~/scripts/util/parse_data.sh
EOF

###############################################################################
# 7. Submit
###############################################################################
echo "Jobscript '$JOBSCRIPT' created."
echo "Submitting with sbatch..."
sbatch "$JOBSCRIPT"

