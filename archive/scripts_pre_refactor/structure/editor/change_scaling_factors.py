#!/usr/bin/env python3
import sys
import os

def replace_second_line(arg1, arg2, arg3):
    """Replace the second line of POSCAR file with three arguments"""
    
    # Check if POSCAR file exists
    if not os.path.exists('POSCAR'):
        print("Error: POSCAR file not found in current directory")
        sys.exit(1)
    
    try:
        # Read the file
        with open('POSCAR', 'r') as f:
            lines = f.readlines()
        
        # Replace the second line (index 1) with the three arguments
        new_second_line = f"{arg1} {arg2} {arg3}\n"
        lines[1] = new_second_line
        
        # Write back to file
        with open('POSCAR', 'w') as f:
            f.writelines(lines)
        
        print(f"Successfully replaced second line with: {arg1} {arg2} {arg3}")
        
    except IOError as e:
        print(f"Error reading/writing POSCAR file: {e}")
        sys.exit(1)

def main():
    # Check if exactly 3 arguments are provided
    if len(sys.argv) != 4:
        print("Usage: python script.py <arg1> <arg2> <arg3>")
        print("This script replaces the second line of POSCAR with the three provided arguments")
        sys.exit(1)
    
    # Get the three arguments
    arg1 = sys.argv[1]
    arg2 = sys.argv[2] 
    arg3 = sys.argv[3]
    
    # Replace the second line
    replace_second_line(arg1, arg2, arg3)

if __name__ == "__main__":
    main()
