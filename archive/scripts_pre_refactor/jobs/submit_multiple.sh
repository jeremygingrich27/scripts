#!/usr/bin/env bash

# Print current working directory
current_dir=$(pwd)
echo "Current working directory: $current_dir"
echo ""

# Ask user for confirmation
read -p "Are you in the correct directory? (YES to continue): " user_response

# Check if user responded with exactly "YES"
if [[ "$user_response" != "YES" ]]; then
    echo "Exiting. Please navigate to the correct directory and run the script again."
    exit 0
fi

echo "Proceeding with job submission..."
echo ""

# Initialize counter for jobs found and submitted
jobs_found=0
jobs_submitted=0
jobs_failed=0

# Find all subdirectories containing a file named "jobscript"
while IFS= read -r -d '' jobscript_path; do
    # Get the directory containing the jobscript
    job_dir=$(dirname "$jobscript_path")
    
    ((jobs_found++))
    echo "Found jobscript in: $job_dir"
    
    # Change to the directory and run sbatch
    if cd "$job_dir"; then
        echo "  Submitting job in $job_dir..."
        
        if sbatch jobscript; then
            echo "  ✓ Successfully submitted job"
            ((jobs_submitted++))
        else
            echo "  ✗ Failed to submit job"
            ((jobs_failed++))
        fi
        
        # Return to original directory
        cd "$current_dir"
    else
        echo "  ✗ Failed to change to directory $job_dir"
        ((jobs_failed++))
    fi
    
    echo ""
done < <(find . -name "jobscript" -type f -print0)

# Print summary
echo "Job submission summary:"
echo "  Jobs found: $jobs_found"
echo "  Jobs submitted successfully: $jobs_submitted"
echo "  Jobs failed: $jobs_failed"

if [[ $jobs_found -eq 0 ]]; then
    echo "No jobscript files found in any subdirectories."
elif [[ $jobs_submitted -eq $jobs_found ]]; then
    echo "All jobs submitted successfully!"
else
    echo "Some jobs failed to submit. Check the output above for details."
fi
