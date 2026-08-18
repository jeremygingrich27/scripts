#!/usr/bin/env python3
"""
Magnetization Analysis Tool with Enhanced Plot Customization
"""

import re
import sys
import argparse
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
import numpy as np
import matplotlib.pyplot as plt

# Regex patterns
SPECIES_PATTERN = re.compile(r"#\s*([\w\-\+]+)\s*:\s*(\d+)\s*-\s*(\d+)")
DIRECTORY_PATTERN = re.compile(r"Directory:\s+(\S+)")
LATTICE_PATTERN = re.compile(r"Lattice:\s*A=([\d\.]+)\s*B=([\d\.]+)\s*C=([\d\.]+)")

@dataclass
class AtomData:
    atom_index: int
    species: str
    magnetization: float
    ca_ratio: float
    dataset: str

@dataclass
class DatasetInfo:
    label: str
    scales: List[float]
    sp_data: Dict[str, List[float]]
    individual_atoms: List[AtomData]
    file_path: Path

def find_magnetization_files(root_dir: Path) -> List[Path]:
    """Recursively find all magnetization.dat files in subdirectories."""
    return sorted(root_dir.rglob("magnetization.dat"))

def load_c_over_a(path: Path) -> Dict[str, float]:
    """Load c/a ratios from energies.dat file"""
    result = {}
    for line in path.read_text().splitlines():
        if not line.strip() or line.lower().startswith("directory"):
            continue
        parts = line.split()
        if len(parts) >= 4:
            try:
                a, b, c = map(float, parts[1:4])
                result[Path(parts[0]).name] = c / ((a + b) / 2)
            except ValueError:
                continue
    return result

def species_ranges(header: str) -> Dict[str, Tuple[int, int]]:
    """Parse species ranges from file header"""
    ranges = {}
    for line in header.splitlines():
        m = SPECIES_PATTERN.match(line)
        if m:
            sym, start, end = m.groups()
            ranges[sym] = (int(start), int(end))
        if line.startswith("Directory:"):
            break
    if not ranges:
        raise ValueError("No species ranges found.")
    return ranges

def split_blocks(text: str) -> List[str]:
    """Split file content into calculation blocks"""
    blocks = []
    current_block = []
    for line in text.splitlines():
        if line.startswith("Directory:"):
            if current_block:
                blocks.append("\n".join(current_block))
                current_block = []
        current_block.append(line)
    if current_block:
        blocks.append("\n".join(current_block))
    return [b for b in blocks if b.strip().startswith("Directory:")]

def parse_block(block: str, ca_map: Dict[str, float], sp_map: Dict[str, Tuple[int, int]]) -> Tuple[float, Dict[str, float], List[dict]]:
    """Parse a single calculation block"""
    match = DIRECTORY_PATTERN.search(block)
    if not match:
        raise ValueError("Missing 'Directory:'")
    dname = Path(match.group(1)).name
    ca = ca_map.get(dname)
    
    # Try to parse lattice parameters directly from the block
    lattice_match = LATTICE_PATTERN.search(block)
    if lattice_match:
        a = float(lattice_match.group(1))
        b = float(lattice_match.group(2))
        c = float(lattice_match.group(3))
        ca = c / ((a + b) / 2)
    
    lines = block.splitlines()
    mags = []
    start = False
    for line in lines:
        if "----" in line:
            start = True
            continue
        if start:
            if line.strip().startswith("tot") or not line.strip():
                break
            try:
                parts = line.split()
                mags.append(float(parts[-1]))
            except:
                continue

    # Use signed magnetization values
    species_sum = {
        sym: sum(mags[s-1:e]) for sym, (s, e) in sp_map.items()
    }
    
    # Create individual atom data
    individual_atoms = []
    for sym, (start_idx, end_idx) in sp_map.items():
        for i in range(start_idx-1, end_idx):
            if i < len(mags):
                individual_atoms.append({
                    'atom_index': i+1,
                    'species': sym,
                    'magnetization': mags[i],
                    'ca_ratio': ca
                })
    
    return ca, species_sum, individual_atoms

def process_file(path: Path, label: str) -> DatasetInfo:
    """Process a magnetization.dat file"""
    energy_path = path.parent / "energies.dat"
    ca_map = {}
    if energy_path.exists():
        ca_map = load_c_over_a(energy_path)
    
    content = path.read_text()
    sp_map = species_ranges(content)

    scales, per_species, all_individual_atoms = [], {s: [] for s in sp_map}, []
    for block in split_blocks(content):
        try:
            ca, sums, individual_atoms = parse_block(block, ca_map, sp_map)
            if ca is None:
                continue
            scales.append(ca)
            for s in sp_map:
                per_species[s].append(sums.get(s, 0.0))
            all_individual_atoms.extend(individual_atoms)
        except Exception as e:
            print(f"  Skipped block: {e}")

    # Convert individual atoms to AtomData objects
    atom_data_list = [
        AtomData(
            atom_index=atom['atom_index'],
            species=atom['species'],
            magnetization=atom['magnetization'],
            ca_ratio=atom['ca_ratio'],
            dataset=label
        )
        for atom in all_individual_atoms
    ]

    return DatasetInfo(
        label=label,
        scales=scales,
        sp_data=per_species,
        individual_atoms=atom_data_list,
        file_path=path
    )

def create_plots(datasets: List[DatasetInfo], output_dir: Path):
    """Create all plots for the datasets"""
    # Create combined species plot
    plt.figure(figsize=(10, 6))
    for dataset in datasets:
        for species, values in dataset.sp_data.items():
            plt.plot(dataset.scales, values, 'o-', 
                    alpha=0.7,
                    label=f"{dataset.label} - {species}")
    
    plt.xlabel("c/a ratio")
    plt.ylabel("Magnetization (μB)")
    plt.title("Magnetization vs c/a ratio")
    plt.legend()
    plt.tight_layout()
    plt.savefig(output_dir / "magnetization_summary.png", dpi=300)
    plt.close()
    
    # Create combined individual atom plots in one figure
    all_species = sorted({a.species for d in datasets for a in d.individual_atoms})
    
    # Determine subplot grid size
    n_species = len(all_species)
    n_cols = 1
    n_rows = n_species
    
    # Create figure with subplots
    fig, axs = plt.subplots(n_rows, n_cols, figsize=(10, 4*n_rows))
    axs = axs.ravel() if isinstance(axs, np.ndarray) else [axs]
    
    for i, species in enumerate(all_species):
        ax = axs[i]
        for dataset in datasets:
            species_atoms = [a for a in dataset.individual_atoms if a.species == species]
            if species_atoms:
                x = [a.ca_ratio for a in species_atoms]
                y = [a.magnetization for a in species_atoms]
                ax.scatter(x, y, alpha=0.4,
                         label=f"{dataset.label}")
        
        ax.set_xlabel("c/a ratio")
        ax.set_ylabel(f"{species} Magnetization (μB)")
        ax.set_title(f"Individual {species} Atoms")
        ax.grid(False, alpha=0.3)
        ax.legend()
    
    # Hide unused subplots
    for j in range(i+1, len(axs)):
        axs[j].axis('off')
    
    plt.tight_layout()
    plt.savefig(output_dir / "individual_atoms_combined_magnetization.png", dpi=300)
    plt.close()

def splice_datasets(ds1: DatasetInfo, ds2: DatasetInfo, splice_point: float) -> Tuple[List[float], Dict[str, List[float]]]:
    """Combine two datasets at a specified c/a ratio"""
    spliced_scales = []
    spliced_data = {s: [] for s in ds1.sp_data.keys()}
    
    # Add points from first dataset before splice point
    for i, ca in enumerate(ds1.scales):
        if ca <= splice_point:
            spliced_scales.append(ca)
            for s in ds1.sp_data:
                spliced_data[s].append(ds1.sp_data[s][i])
    
    # Add points from second dataset after splice point
    for i, ca in enumerate(ds2.scales):
        if ca > splice_point:
            spliced_scales.append(ca)
            for s in ds2.sp_data:
                spliced_data[s].append(ds2.sp_data[s][i])
    
    return spliced_scales, spliced_data

def create_spliced_plot(datasets: List[DatasetInfo], splice_info: Tuple[str, str, float], output_dir: Path):
    """Create a plot showing spliced data"""
    ds1_label, ds2_label, splice_point = splice_info
    ds1 = next(d for d in datasets if d.label == ds1_label)
    ds2 = next(d for d in datasets if d.label == ds2_label)
    
    spliced_scales, spliced_data = splice_datasets(ds1, ds2, splice_point)
    
    plt.figure(figsize=(10, 6))
    for species in ds1.sp_data:
        plt.plot(spliced_scales, spliced_data[species], 'o-', alpha=0.7,
                label=f"Spliced {species}")
    
    plt.axvline(x=splice_point, color='r', linestyle='--', alpha=0.5,
               label=f"Splice at c/a={splice_point:.2f}")
    plt.xlabel("c/a ratio")
    plt.ylabel("Magnetization (μB)")
    plt.title(f"Spliced Magnetization: {ds1_label} + {ds2_label}")
    plt.legend()
    plt.grid(False, alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_dir / f"spliced_{ds1_label}_{ds2_label}_magnetization.png", dpi=300)
    plt.close()

def get_display_name(path: Path) -> str:
    """Create a descriptive name showing the full path from root."""
    parts = path.parts
    relevant_parts = []
    for part in parts:
        if part not in ['.', '..', 'magnetization.dat']:
            relevant_parts.append(part)
    
    if relevant_parts and relevant_parts[-1] == 'magnetization.dat':
        relevant_parts = relevant_parts[:-1]
    
    if len(relevant_parts) >= 2:
        return '/'.join(relevant_parts[-2:])
    elif len(relevant_parts) == 1:
        return relevant_parts[0]
    else:
        return path.parent.name

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", nargs="?", default=".", 
                      help="Directory to search for magnetization.dat files")
    args = parser.parse_args()

    root_dir = Path(args.directory).expanduser().resolve()
    magnetization_files = find_magnetization_files(root_dir)
    
    if not magnetization_files:
        print(f"No magnetization.dat files found in {root_dir}")
        return
    
    # Display found files
    print(f"\n{'='*60}")
    print(f"FOUND {len(magnetization_files)} MAGNETIZATION.DAT FILES")
    print(f"{'='*60}")
    for i, path in enumerate(magnetization_files):
        display_name = get_display_name(path)
        print(f"  [{i}] {display_name}")

    # Process all files first
    print(f"\n{'='*60}")
    print("PROCESSING DATASETS")
    print(f"{'='*60}")
    
    raw_datasets = {}
    for path in magnetization_files:
        display_name = get_display_name(path)
        try:
            dataset = process_file(path, display_name)
            raw_datasets[display_name] = dataset
            print(f"  ✅ Processed {display_name}")
        except Exception as e:
            print(f"  ❌ Failed to process {display_name}: {e}")

    if not raw_datasets:
        print("No datasets processed.")
        return

    # Dataset selection and grouping
    print(f"\n{'='*60}")
    print("DATASET SELECTION AND GROUPING")
    print(f"{'='*60}")
    print("How to specify datasets:")
    print("  • Single dataset: just the index (e.g., '0')")
    print("  • Splice two datasets: two indices separated by space (e.g., '0 1')")
    print("  • Multiple groups: separate with semicolons (e.g., '0; 1 2; 3')")
    print("")
    
    dataset_names = list(raw_datasets.keys())
    groups_input = input("Enter dataset groups: ").strip()
    if not groups_input:
        print("No groups specified.")
        return

    # Parse groups
    groups = []
    for group_str in groups_input.split(';'):
        group_str = group_str.strip()
        try:
            indices = list(map(int, group_str.split()))
            if len(indices) == 1:
                groups.append(('single', indices[0]))
            elif len(indices) == 2:
                groups.append(('splice', indices[0], indices[1]))
            else:
                print(f"❌ Invalid group '{group_str}' - only 1 or 2 datasets per group supported")
                continue
        except ValueError:
            print(f"❌ Invalid group '{group_str}' - must be integers")
            continue

    # Process groups to create final datasets
    print(f"\n{'='*60}")
    print("DATASET LABELING")
    print(f"{'='*60}")
    
    datasets = []
    for group_num, group in enumerate(groups, 1):
        print(f"\nGroup {group_num}:")
        
        if group[0] == 'single':
            idx = group[1]
            if 0 <= idx < len(dataset_names):
                original_name = dataset_names[idx]
                dataset = raw_datasets[original_name]
                
                print(f"  Dataset: {original_name}")
                print(f"  Data points: {len(dataset.scales)}, c/a range: {min(dataset.scales):.3f} to {max(dataset.scales):.3f}")
                
                # Ask user for custom label
                label = input(f"  Enter label for this dataset [{original_name}]: ").strip()
                if not label:
                    label = original_name
                
                # Create new dataset with custom label
                new_dataset = DatasetInfo(
                    label=label,
                    scales=dataset.scales,
                    sp_data=dataset.sp_data,
                    individual_atoms=dataset.individual_atoms,
                    file_path=dataset.file_path
                )
                datasets.append(new_dataset)
                print(f"  ✅ Added as: {label}")
            else:
                print(f"  ❌ Invalid index {idx}")
                
        elif group[0] == 'splice':
            idx1, idx2 = group[1], group[2]
            if 0 <= idx1 < len(dataset_names) and 0 <= idx2 < len(dataset_names):
                name1, name2 = dataset_names[idx1], dataset_names[idx2]
                ds1 = raw_datasets[name1]
                ds2 = raw_datasets[name2]
                
                print(f"  Splicing two datasets:")
                print(f"    Dataset 1: {name1} (c/a: {min(ds1.scales):.3f}-{max(ds1.scales):.3f}, {len(ds1.scales)} points)")
                print(f"    Dataset 2: {name2} (c/a: {min(ds2.scales):.3f}-{max(ds2.scales):.3f}, {len(ds2.scales)} points)")
                
                # Get label first
                default_label = f"{name1}+{name2}"
                label = input(f"  Enter label for spliced dataset [{default_label}]: ").strip()
                if not label:
                    label = default_label
                
                # Then get splice point
                try:
                    print(f"  Enter c/a value where datasets should be joined:")
                    print(f"    (Dataset 1 will be used for c/a ≤ splice point)")
                    print(f"    (Dataset 2 will be used for c/a > splice point)")
                    splice_point = float(input(f"  Splice point: "))
                    
                    spliced_scales, spliced_data = splice_datasets(ds1, ds2, splice_point)
                    
                    # Create a new DatasetInfo for the spliced data
                    # For individual atoms, we'll combine both datasets
                    combined_atoms = ds1.individual_atoms + ds2.individual_atoms
                    
                    spliced_dataset = DatasetInfo(
                        label=label,
                        scales=spliced_scales,
                        sp_data=spliced_data,
                        individual_atoms=combined_atoms,
                        file_path=ds1.file_path  # Just use one of the paths
                    )
                    datasets.append(spliced_dataset)
                    print(f"  ✅ Spliced at c/a = {splice_point}, added as: {label}")
                    
                except ValueError:
                    print(f"  ❌ Invalid splice point")
            else:
                print(f"  ❌ Invalid indices {idx1}, {idx2}")

    if not datasets:
        print("No datasets selected for plotting.")
        return

    # Create plots
    create_plots(datasets, root_dir)
    print(f"\n{'='*60}")
    print("PLOTS GENERATED")
    print(f"{'='*60}")
    print(f"  {root_dir}/magnetization_summary.png")
    print(f"  {root_dir}/individual_atoms_combined_magnetization.png")

    # Check if we have any spliced datasets
    spliced_datasets = [d for d in datasets if '+' in d.label]
    if spliced_datasets:
        print("\nSpliced datasets detected. Additional plots:")
        for dataset in spliced_datasets:
            if '+' in dataset.label:
                ds1_label, ds2_label = dataset.label.split('+')[:2]
                # Find the splice point (approximate)
                splice_point = max([ca for ca in raw_datasets[ds1_label].scales])
                print(f"  {root_dir}/spliced_{ds1_label}_{ds2_label}_magnetization.png")

    print(f"\n{'='*60}")
    print("PROCESSING COMPLETE")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
