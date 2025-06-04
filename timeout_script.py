import subprocess
import sys

try:
    # Run the main.py script with a 10-second timeout
    process = subprocess.run(['python', 'main.py'], 
                            timeout=10, 
                            capture_output=True, 
                            text=True)
    # Print the output
    print("STDOUT:")
    print(process.stdout)
    print("STDERR:")
    print(process.stderr)
except subprocess.TimeoutExpired as e:
    print("Process timed out after 10 seconds")
    if e.stdout:
        print("STDOUT before timeout:")
        print(e.stdout.decode('utf-8'))
    if e.stderr:
        print("STDERR before timeout:")
        print(e.stderr.decode('utf-8'))