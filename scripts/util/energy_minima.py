#!/usr/bin/env python3
import sys
import numpy as np
import pandas as pd
from scipy.signal import argrelmin
from pathlib import Path
import glob

def find_local_minima(pattern):
    """
    Find local minima from energies.dat files in directories matching the pattern.
    
    Args:
        pattern: Glob pattern for directories to search
        
    Returns:
        List of directory names containing local minima
    """
    # Find all directories matching the pattern, excluding .tar.gz files
    all_matches = glob.glob(pattern)
    directories = [d for d in all_matches if Path(d).is_dir() and not d.endswith('.tar.gz')]
    
    if not directories:
        print(f"No valid directories found matching pattern: {pattern}", file=sys.stderr)
        return []
    
    minima_dirs = []
    
    # Process each directory
    for directory in sorted(directories):
        dir_path = Path(directory)
        energy_file = dir_path / "energies.dat"
        
        if not energy_file.exists():
            print(f"Warning: {energy_file} not found, skipping {directory}", file=sys.stderr)
            continue
            
        try:
            # Read the energy data
            df = pd.read_csv(energy_file, delim_whitespace=True, comment="#")
            
            if "Energy(eV)" not in df.columns or "Directory" not in df.columns:
                print(f"Warning: Required columns not found in {energy_file}", file=sys.stderr)
                continue
            
            # Extract energy values as numpy array
            energies = df["Energy(eV)"].to_numpy()
            
            if len(energies) < 3:  # Need at least 3 points to find local minima
                print(f"Warning: Not enough data points in {directory} to find minima", file=sys.stderr)
                # Use global minimum if not enough points for local minima
                global_min_idx = energies.argmin()
                global_min_dir = df.iloc[global_min_idx]["Directory"]
                minima_dirs.append(f"{dir_path.name}/{global_min_dir}")
                print(f"Using global minimum for {dir_path.name}: {global_min_dir}", file=sys.stderr)
                continue
                
            # Find indices of local minima
            minima_indices = argrelmin(energies, order=1)[0]
            
            if len(minima_indices) > 0:
                # Get the directory names for the minima
                minima_in_dir = df.iloc[minima_indices]["Directory"].tolist()
                for minima_subdir in minima_in_dir:
                    minima_dirs.append(f"{dir_path.name}/{minima_subdir}")
                print(f"Found {len(minima_indices)} local minima in {dir_path.name}", file=sys.stderr)
            else:
                # If no local minima found, use global minimum
                global_min_idx = energies.argmin()
                global_min_dir = df.iloc[global_min_idx]["Directory"]
                minima_dirs.append(f"{dir_path.name}/{global_min_dir}")
                print(f"No local minima in {dir_path.name}, using global minimum: {global_min_dir}", file=sys.stderr)
                
        except Exception as e:
            print(f"Error reading {energy_file}: {e}", file=sys.stderr)
            continue
    
    # Print results to stdout for bash script to capture (one per line)
    # Only print the POSCAR directory names, not the full path
    for dirname in minima_dirs:
        # Extract just the POSCAR_z_* part
        poscar_dir = dirname.split('/')[-1]
        print(poscar_dir)
    
    return minima_dirs

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python energy_minima.py 'pattern/to/directories/*'", file=sys.stderr)
        sys.exit(1)
    
    pattern = sys.argv[1]
    minima = find_local_minima(pattern)
    
    if not minima:
        print("No minima found", file=sys.stderr)
        sys.exit(1)
