#!/usr/bin/bash

# Ensure correct number of arguments
if [ "$#" -ne 5 ]; then
    echo "Usage: $0 <SYSTEM> <PSEUDO> <KPR> <KSCHEME> <DIRNAME>"
    exit 1
fi

# User-defined variables
SYSTEM="$1"
PSEUDO="$2"
KPR="$3"
KSCHEME="$4"
DIR="$5"

# Setup directory architecture for future calculations
if ! mkdir -p "$DIR"; then
    echo "Error: Failed to create directory $DIR."
    exit 1
fi
cd "$DIR" || { echo "Error: Failed to enter directory $DIR."; exit 1; }

# Copy initial POSCAR
if ! cp ~/POSCARs/"$SYSTEM" POSCAR; then
    echo "Error: Failed to copy POSCAR for $SYSTEM."
    exit 1
fi

sed "s/PSEUDO/$PSEUDO/" ~/.vaspkitbase > ~/.vaspkit

# Run vaspkit to initialize and append summary to README
if ! echo -e "01\n103" | vaspkit | awk '/Summary/,EOF' >> README; then
    echo "Error: Failed to generate VASPkit summary."
    exit 1
fi

# Run vaspkit to analyzed unrelaxed structure
if ! echo -e "06\n601" | vaspkit | awk '/Summary/,EOF' >> unrelaxedSymmetry; then
    echo "Error: Failed to generate VASPkit symmetry analysis."
    exit 1
fi

mv POSCAR unrelaxedPOSCAR

# Setup subdirectories for different calculation types
for CALC in electrons elastic phonons relax; do
    if ! mkdir -p "$CALC"; then
        echo "Error: Failed to create directory $CALC."
        exit 1
    fi
    if ! cp POTCAR "$CALC/"; then
        echo "Error: Failed to copy POTCAR file to $CALC."
        exit 1
    fi
done

# Copy/create input files in relax subdirectory
if ! cp unrelaxedPOSCAR relax/POSCAR; then
    echo "Error: Failed to copy POSCAR file to relax directory."
    exit 1
fi

cd relax || { echo "Error: Failed to enter relax directory."; exit 1; }

# Run vaspkit for K-space generation
if ! echo -e "102\n$KSCHEME\n$KPR" | vaspkit | awk '/Summary/,/+---------------------------------------------------------------+/' >> README; then
    echo "Error: Failed to generate K-space using vaspkit."
    exit 1
fi
