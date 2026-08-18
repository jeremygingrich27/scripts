#!/usr/bin/env bash

# Default: single point at 1.0
x_vals=("1.0")
y_vals=("1.0")
z_vals=("1.0")

# Coupling flags
xy_coupled=false
xz_coupled=false
yz_coupled=false
xyz_coupled=false

print_help() {
  echo "Usage: $0 [OPTIONS]"
  echo ""
  echo "Options:"
  echo "  -x start:stop:step    X scaling factor range"
  echo "  -y start:stop:step    Y scaling factor range"
  echo "  -z start:stop:step    Z scaling factor range"
  echo "  -xy start:stop:step   X and Y coupled (same values)"
  echo "  -xz start:stop:step   X and Z coupled (same values)"
  echo "  -yz start:stop:step   Y and Z coupled (same values)"
  echo "  -xyz start:stop:step  X, Y, and Z coupled (same values)"
  echo "  -i, --interactive     Run in interactive mode"
  echo "  -h, --help           Show this help"
  echo ""
  echo "All values may be floats. Defaults to 1.0 if not specified."
  echo "Coupled options override individual axis specifications."
  exit 1
}

generate_range() {
  local start="$1"
  local stop="$2"
  local step="$3"
  awk -v start="$start" -v stop="$stop" -v step="$step" 'BEGIN {
    for (x = start; x <= stop + (step/2); x += step) {
      printf "%.10g\n", x
    }
  }'
}

interactive_mode() {
  echo "=== Interactive VASP Structure Scaling ==="
  echo ""
  
  # Ask about coupling
  echo "Do you want to couple scaling factors?"
  echo "1) No coupling (set x, y, z independently)"
  echo "2) Couple x and y (xy)"
  echo "3) Couple x and z (xz)"
  echo "4) Couple y and z (yz)"
  echo "5) Couple all three (xyz)"
  read -p "Choose option (1-5): " coupling_choice
  
  case "$coupling_choice" in
    1)
      # Independent scaling
      read -p "Enter X range (start:stop:step) or single value [default: 1.0]: " x_input
      read -p "Enter Y range (start:stop:step) or single value [default: 1.0]: " y_input
      read -p "Enter Z range (start:stop:step) or single value [default: 1.0]: " z_input
      
      if [[ -n "$x_input" ]]; then
        if [[ "$x_input" == *":"* ]]; then
          IFS=':' read -r x_start x_stop x_step <<< "$x_input"
          mapfile -t x_vals < <(generate_range "$x_start" "$x_stop" "$x_step")
        else
          x_vals=("$x_input")
        fi
      fi
      
      if [[ -n "$y_input" ]]; then
        if [[ "$y_input" == *":"* ]]; then
          IFS=':' read -r y_start y_stop y_step <<< "$y_input"
          mapfile -t y_vals < <(generate_range "$y_start" "$y_stop" "$y_step")
        else
          y_vals=("$y_input")
        fi
      fi
      
      if [[ -n "$z_input" ]]; then
        if [[ "$z_input" == *":"* ]]; then
          IFS=':' read -r z_start z_stop z_step <<< "$z_input"
          mapfile -t z_vals < <(generate_range "$z_start" "$z_stop" "$z_step")
        else
          z_vals=("$z_input")
        fi
      fi
      ;;
    2)
      xy_coupled=true
      read -p "Enter XY range (start:stop:step) or single value [default: 1.0]: " xy_input
      read -p "Enter Z range (start:stop:step) or single value [default: 1.0]: " z_input
      
      if [[ -n "$xy_input" ]]; then
        if [[ "$xy_input" == *":"* ]]; then
          IFS=':' read -r xy_start xy_stop xy_step <<< "$xy_input"
          mapfile -t x_vals < <(generate_range "$xy_start" "$xy_stop" "$xy_step")
        else
          x_vals=("$xy_input")
        fi
      fi
      
      if [[ -n "$z_input" ]]; then
        if [[ "$z_input" == *":"* ]]; then
          IFS=':' read -r z_start z_stop z_step <<< "$z_input"
          mapfile -t z_vals < <(generate_range "$z_start" "$z_stop" "$z_step")
        else
          z_vals=("$z_input")
        fi
      fi
      ;;
    3)
      xz_coupled=true
      read -p "Enter XZ range (start:stop:step) or single value [default: 1.0]: " xz_input
      read -p "Enter Y range (start:stop:step) or single value [default: 1.0]: " y_input
      
      if [[ -n "$xz_input" ]]; then
        if [[ "$xz_input" == *":"* ]]; then
          IFS=':' read -r xz_start xz_stop xz_step <<< "$xz_input"
          mapfile -t x_vals < <(generate_range "$xz_start" "$xz_stop" "$xz_step")
        else
          x_vals=("$xz_input")
        fi
      fi
      
      if [[ -n "$y_input" ]]; then
        if [[ "$y_input" == *":"* ]]; then
          IFS=':' read -r y_start y_stop y_step <<< "$y_input"
          mapfile -t y_vals < <(generate_range "$y_start" "$y_stop" "$y_step")
        else
          y_vals=("$y_input")
        fi
      fi
      ;;
    4)
      yz_coupled=true
      read -p "Enter YZ range (start:stop:step) or single value [default: 1.0]: " yz_input
      read -p "Enter X range (start:stop:step) or single value [default: 1.0]: " x_input
      
      if [[ -n "$yz_input" ]]; then
        if [[ "$yz_input" == *":"* ]]; then
          IFS=':' read -r yz_start yz_stop yz_step <<< "$yz_input"
          mapfile -t y_vals < <(generate_range "$yz_start" "$yz_stop" "$yz_step")
        else
          y_vals=("$yz_input")
        fi
      fi
      
      if [[ -n "$x_input" ]]; then
        if [[ "$x_input" == *":"* ]]; then
          IFS=':' read -r x_start x_stop x_step <<< "$x_input"
          mapfile -t x_vals < <(generate_range "$x_start" "$x_stop" "$x_step")
        else
          x_vals=("$x_input")
        fi
      fi
      ;;
    5)
      xyz_coupled=true
      read -p "Enter XYZ range (start:stop:step) or single value [default: 1.0]: " xyz_input
      
      if [[ -n "$xyz_input" ]]; then
        if [[ "$xyz_input" == *":"* ]]; then
          IFS=':' read -r xyz_start xyz_stop xyz_step <<< "$xyz_input"
          mapfile -t x_vals < <(generate_range "$xyz_start" "$xyz_stop" "$xyz_step")
        else
          x_vals=("$xyz_input")
        fi
      fi
      ;;
    *)
      echo "Invalid choice. Using defaults."
      ;;
  esac
  
  # Show summary
  echo ""
  echo "=== Configuration Summary ==="
  echo "X values: ${x_vals[*]}"
  echo "Y values: ${y_vals[*]}"
  echo "Z values: ${z_vals[*]}"
  echo "Total calculations: $((${#x_vals[@]} * ${#y_vals[@]} * ${#z_vals[@]}))"
  echo ""
  read -p "Proceed with these settings? (y/N): " confirm
  if [[ "$confirm" != [Yy]* ]]; then
    echo "Aborted."
    exit 0
  fi
}

# Check if no arguments provided - default to interactive mode
if [[ $# -eq 0 ]]; then
  interactive_mode
else
  # Parse command line options
  while [[ $# -gt 0 ]]; do
    case "$1" in
      -x)
        if [[ "$xy_coupled" == true ]] || [[ "$xz_coupled" == true ]] || [[ "$xyz_coupled" == true ]]; then
          echo "Error: Cannot specify -x when using coupled options"
          exit 1
        fi
        IFS=':' read -r x_start x_stop x_step <<< "$2"
        mapfile -t x_vals < <(generate_range "$x_start" "$x_stop" "$x_step")
        shift 2
        ;;
      -y)
        if [[ "$xy_coupled" == true ]] || [[ "$yz_coupled" == true ]] || [[ "$xyz_coupled" == true ]]; then
          echo "Error: Cannot specify -y when using coupled options"
          exit 1
        fi
        IFS=':' read -r y_start y_stop y_step <<< "$2"
        mapfile -t y_vals < <(generate_range "$y_start" "$y_stop" "$y_step")
        shift 2
        ;;
      -z)
        if [[ "$xz_coupled" == true ]] || [[ "$yz_coupled" == true ]] || [[ "$xyz_coupled" == true ]]; then
          echo "Error: Cannot specify -z when using coupled options"
          exit 1
        fi
        IFS=':' read -r z_start z_stop z_step <<< "$2"
        mapfile -t z_vals < <(generate_range "$z_start" "$z_stop" "$z_step")
        shift 2
        ;;
      -xy)
        xy_coupled=true
        IFS=':' read -r xy_start xy_stop xy_step <<< "$2"
        mapfile -t x_vals < <(generate_range "$xy_start" "$xy_stop" "$xy_step")
        shift 2
        ;;
      -xz)
        xz_coupled=true
        IFS=':' read -r xz_start xz_stop xz_step <<< "$2"
        mapfile -t x_vals < <(generate_range "$xz_start" "$xz_stop" "$xz_step")
        shift 2
        ;;
      -yz)
        yz_coupled=true
        IFS=':' read -r yz_start yz_stop yz_step <<< "$2"
        mapfile -t y_vals < <(generate_range "$yz_start" "$yz_stop" "$yz_step")
        shift 2
        ;;
      -xyz)
        xyz_coupled=true
        IFS=':' read -r xyz_start xyz_stop xyz_step <<< "$2"
        mapfile -t x_vals < <(generate_range "$xyz_start" "$xyz_stop" "$xyz_step")
        shift 2
        ;;
      -i|--interactive)
        interactive_mode
        shift
        ;;
      -h|--help)
        print_help
        ;;
      *)
        echo "Unknown option: $1"
        print_help
        ;;
    esac
  done
fi

parent_dir=$(pwd)

# Main loop - handle coupled vs uncoupled cases
run_calculation() {
  local x="$1"
  local y="$2" 
  local z="$3"
  
  echo "Running for x=$x, y=$y, z=$z"
  
  new_dir="${parent_dir}/scale_${x}/POSCAR_z_${z}"
  mkdir -p "$new_dir"
  cd "$new_dir" || exit 1
  
  cp "$parent_dir/POSCAR" ./POSCAR
  cp "$parent_dir/POTCAR" ./POTCAR
  python3 ~/scripts/structure/editor/change_scaling_factors.py "$x" "$y" "$z"
  echo -e "102\n2\n0.03" | vaspkit > /dev/null 2>&1
  cp "$parent_dir/INCAR" ./INCAR
  
  cd "$parent_dir" || exit 1
}

if [[ "$xyz_coupled" == true ]]; then
  # All three coupled - iterate through the coupled values
  for x in "${x_vals[@]}"; do
    run_calculation "$x" "$x" "$x"
  done
elif [[ "$xy_coupled" == true ]]; then
  # XY coupled, Z independent - cartesian product of xy_vals with z_vals
  for xy_val in "${x_vals[@]}"; do
    for z in "${z_vals[@]}"; do
      run_calculation "$xy_val" "$xy_val" "$z"
    done
  done
elif [[ "$xz_coupled" == true ]]; then
  # XZ coupled, Y independent - cartesian product of xz_vals with y_vals
  for xz_val in "${x_vals[@]}"; do
    for y in "${y_vals[@]}"; do
      run_calculation "$xz_val" "$y" "$xz_val"
    done
  done
elif [[ "$yz_coupled" == true ]]; then
  # YZ coupled, X independent - cartesian product of x_vals with yz_vals
  for x in "${x_vals[@]}"; do
    for yz_val in "${y_vals[@]}"; do
      run_calculation "$x" "$yz_val" "$yz_val"
    done
  done
else
  # Original uncoupled behavior - full cartesian product
  for x in "${x_vals[@]}"; do
    for y in "${y_vals[@]}"; do
      for z in "${z_vals[@]}"; do
        run_calculation "$x" "$y" "$z"
      done
    done
  done
fi

echo "Initial subdirectory setup completed!"
