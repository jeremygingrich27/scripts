#!/bin/bash

# Script to sum up VASP calculation times from OUTCAR files in * directories

total_time=0
count=0
failed_count=0
output_file="vasp_timing_summary.txt"

# Function to output to both terminal and file
output() {
    echo "$1"
    echo "$1" >> "$output_file"
}

# Clear the output file
> "$output_file"

output "Scanning for OUTCAR files in * directories..."
output "============================================================"

# Find all OUTCAR files in * directories
for outcar in */OUTCAR; do
    if [[ -f "$outcar" ]]; then
        dir=$(dirname "$outcar")
        
        # Extract elapsed time from the OUTCAR file
        elapsed_time=$(grep "Elapsed time (sec):" "$outcar" | tail -1 | awk '{print $4}')
        
        if [[ -n "$elapsed_time" && "$elapsed_time" != "N/A" ]]; then
            # Add to total (using bc for floating point arithmetic)
            total_time=$(echo "$total_time + $elapsed_time" | bc -l)
            count=$((count + 1))
            output "$(printf "%-20s: %10.3f seconds" "$dir" "$elapsed_time")"
        else
            output "Warning: Could not extract elapsed time from $outcar"
            failed_count=$((failed_count + 1))
        fi
    fi
done

output "============================================================"
output "Summary:"
output "  Successfully processed: $count calculations"
if [[ $failed_count -gt 0 ]]; then
    output "  Failed to process: $failed_count calculations"
fi

if [[ $count -gt 0 ]]; then
    output "  Total elapsed time: $(printf "%.3f" $total_time) seconds"
    
    # Convert to more readable format
    hours=$(echo "$total_time / 3600" | bc -l)
    minutes=$(echo "($total_time % 3600) / 60" | bc -l)
    seconds=$(echo "$total_time % 60" | bc -l)
    
    output "$(printf "  Total elapsed time: %02.0f:%02.0f:%06.3f (HH:MM:SS.sss)" "$hours" "$minutes" "$seconds")"
    
    # If more than 1 hour, also show days
    if (( $(echo "$total_time > 3600" | bc -l) )); then
        days=$(echo "$total_time / 86400" | bc -l)
        output "$(printf "  Total elapsed time: %.2f days" "$days")"
    fi
else
    output "  No valid timing data found!"
fi

echo ""
echo "Results saved to: $output_file"
