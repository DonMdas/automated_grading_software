import os
import srsly
from pathlib import Path
import json
import re
import subprocess
import webbrowser
import sys


def invoke_prodigy_command(file_path):
    """
    Invoke Prodigy command to view annotations and open in browser.
    
    Args:
        file_path: Path to the JSONL file to view
        
    Returns:
        str: URL if successful, None if failed
    """
    import time
    import threading
    from queue import Queue, Empty
    
    try:
        print(f"🚀 Starting Prodigy annotation viewer for: {file_path}")
        
        # Start prodigy process
        process = subprocess.Popen(
            ['prodigy', 'spans.manual', str(file_path), 'blank:en', str(file_path), '--label', 'PLACEHOLDER'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        print(f"📡 Prodigy process started (PID: {process.pid})")
        print(f"⏳ Reading initial output to find URL...")
        
        # Function to read output in a separate thread
        def read_output(pipe, queue):
            try:
                for line in iter(pipe.readline, ''):
                    queue.put(line)
                    if not line:
                        break
            except:
                pass
            finally:
                pipe.close()
        
        # Create queues for stdout and stderr
        stdout_queue = Queue()
        stderr_queue = Queue()
        
        # Start threads to read output
        stdout_thread = threading.Thread(target=read_output, args=(process.stdout, stdout_queue))
        stderr_thread = threading.Thread(target=read_output, args=(process.stderr, stderr_queue))
        
        stdout_thread.daemon = True
        stderr_thread.daemon = True
        stdout_thread.start()
        stderr_thread.start()
        
        # Collect output for URL extraction
        collected_output = []
        url = None
        timeout = 15  # Wait up to 15 seconds for URL
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            # Check if process terminated early
            if process.poll() is not None:
                print(f"❌ Error: Prodigy process terminated unexpectedly")
                print(f"   Exit code: {process.returncode}")
                
                # Collect any remaining output
                while True:
                    try:
                        line = stderr_queue.get_nowait()
                        print(f"   Error: {line.strip()}")
                    except Empty:
                        break
                return None
            
            # Read available output
            try:
                while True:
                    line = stdout_queue.get_nowait()
                    collected_output.append(line)
                    print(f"   📄 {line.strip()}")
                    
                    # Look for URL in this line
                    url_match = re.search(r'http://localhost:\d+(?:/\w+)?', line)
                    if url_match:
                        url = url_match.group(0)
                        print(f"✅ Found Prodigy URL: {url}")
                        break
                        
            except Empty:
                pass
            
            # If we found the URL, break out
            if url:
                break
                
            time.sleep(0.5)
        
        if url:
            print(f"🌐 Opening browser at: {url}")
            open_browser(url)
            
            print(f"📝 Prodigy is now running. Press Ctrl+C to stop the server when done.")
            print(f"   You can also manually visit: {url}")
            
            # Keep the process running and wait for user interrupt
            try:
                process.wait()
            except KeyboardInterrupt:
                print(f"\n🛑 Stopping Prodigy server...")
                process.terminate()
                try:
                    process.wait(timeout=5)
                    print(f"✅ Prodigy server stopped gracefully")
                except subprocess.TimeoutExpired:
                    print(f"⚠️  Force killing Prodigy process...")
                    process.kill()
                    process.wait()
                    print(f"✅ Prodigy server force stopped")
            
            return url
        else:
            print(f"⚠️  Warning: Could not extract URL from Prodigy output within {timeout} seconds")
            print(f"   Collected output:")
            for line in collected_output:
                print(f"     {line.strip()}")
            print(f"   Please check manually at: http://localhost:8080")
            
            # Still keep process running
            print(f"📝 Prodigy may still be starting. Press Ctrl+C to stop when done.")
            try:
                process.wait()
            except KeyboardInterrupt:
                print(f"\n🛑 Stopping Prodigy server...")
                process.terminate()
                process.wait()
                print(f"✅ Prodigy server stopped")
            
            return None
            
    except FileNotFoundError:
        print(f"❌ Error: Prodigy is not installed or not found in PATH")
        print(f"   Please install Prodigy: pip install prodigy")
        return None
    except Exception as e:
        print(f"❌ Unexpected error starting Prodigy: {str(e)}")
        return None


def open_browser(url):
    """Open URL in default web browser with error handling."""
    try:
        webbrowser.open(url)
        print(f"🎯 Browser opened successfully")
    except Exception as e:
        print(f"⚠️  Warning: Could not open browser automatically: {str(e)}")
        print(f"   Please manually open: {url}")


def show_annotations(data_folder):
    """
    Main function to show annotations with interactive menu.
    
    Args:
        data_folder: Path to the folder containing annotation data
    """
    # Validate data folder
    data_path = Path(data_folder)
    if not data_path.exists():
        print(f"❌ Error: Data folder '{data_folder}' does not exist")
        print(f"   Please check the path and try again")
        return
    
    if not data_path.is_dir():
        print(f"❌ Error: '{data_folder}' is not a directory")
        return
    
    print(f"📁 Using data folder: {data_path.absolute()}")
    print(f"=" * 60)
    
    # Main interaction loop
    while True: 
        print(f"\n📋 Annotation Viewer Menu:")
        print(f"   1. answer_key     - View answer key annotations")
        print(f"   2. student_answers - View student answer annotations")
        print(f"   3. exit           - Exit the program")
        
        choice = input("\n➤ Enter your choice: ").strip().lower()
        
        if choice in ["exit", "3"]:
            print(f"👋 Exiting annotation viewer. Goodbye!")
            break
        
        if choice not in ["answer_key", "student_answers", "1", "2"]:
            print(f"❌ Invalid choice: '{choice}'")
            print(f"   Please enter 'answer_key', 'student_answers', or 'exit'")
            continue
        
        # Handle answer key viewing
        if choice in ["answer_key", "1"]:
            answer_key_file = data_path / "answer_key_prodigy.jsonl"
            
            if not answer_key_file.exists():
                print(f"❌ Error: Answer key file not found")
                print(f"   Expected location: {answer_key_file}")
                print(f"   Please ensure the file exists and try again")
                continue
            
            if answer_key_file.stat().st_size == 0:
                print(f"⚠️  Warning: Answer key file is empty")
                print(f"   File: {answer_key_file}")
                continue
            
            print(f"\n📖 Loading answer key annotations...")
            invoke_prodigy_command(answer_key_file)
            
        # Handle student answers viewing
        else:
            prodigy_data_folder = data_path / "prodigy_data"
            
            if not prodigy_data_folder.exists():
                print(f"❌ Error: Student data folder not found")
                print(f"   Expected location: {prodigy_data_folder}")
                print(f"   Please ensure the folder exists and try again")
                continue
            
            # Find JSONL files
            jsonl_files = list(prodigy_data_folder.glob("*.jsonl"))
            
            if not jsonl_files:
                print(f"❌ Error: No JSONL files found in student data folder")
                print(f"   Searched in: {prodigy_data_folder}")
                print(f"   Please add JSONL files and try again")
                continue
            
            # Display file selection menu
            print(f"\n📚 Available student answer files ({len(jsonl_files)} found):")
            for idx, file in enumerate(jsonl_files, start=1):
                file_size = file.stat().st_size
                size_str = f"({file_size:,} bytes)" if file_size > 0 else "(empty)"
                print(f"   {idx}. {file.name} {size_str}")
            
            # Get user file selection
            file_choice = input(f"\n➤ Enter file number (1-{len(jsonl_files)}) or 'back': ").strip().lower()
            
            if file_choice in ["back", "exit"]:
                continue
            
            try:
                file_index = int(file_choice) - 1
                if file_index < 0 or file_index >= len(jsonl_files):
                    print(f"❌ Error: Invalid file number '{file_choice}'")
                    print(f"   Please enter a number between 1 and {len(jsonl_files)}")
                    continue
                
                selected_file = jsonl_files[file_index]
                
                # Check if file is empty
                if selected_file.stat().st_size == 0:
                    print(f"⚠️  Warning: Selected file is empty")
                    print(f"   File: {selected_file.name}")
                    continue
                
                print(f"\n📖 Loading student annotations from: {selected_file.name}")
                invoke_prodigy_command(selected_file)
                
            except ValueError:
                print(f"❌ Error: Invalid input '{file_choice}'")
                print(f"   Please enter a valid number or 'back'")
                continue
            except Exception as e:
                print(f"❌ Unexpected error selecting file: {str(e)}")
                continue


if __name__ == "__main__":
    print(f"🎯 Prodigy Annotation Viewer")
    print(f"=" * 60)
    
    # Command line argument validation
    if len(sys.argv) < 2:
        print(f"❌ Error: Missing required argument")
        print(f"   Usage: python {sys.argv[0]} <data_folder_path>")
        print(f"   Example: python {sys.argv[0]} ./exam_data")
        sys.exit(1)
    
    data_folder = sys.argv[1]
    
    # Validate and start the viewer
    if not os.path.exists(data_folder):
        print(f"❌ Error: Data folder '{data_folder}' does not exist")
        print(f"   Please create the folder and add the necessary files")
        print(f"   Expected structure:")
        print(f"     {data_folder}/")
        print(f"     ├── answer_key_prodigy.jsonl")
        print(f"     └── prodigy_data/")
        print(f"         └── *.jsonl files")
        sys.exit(1)
    else:
        show_annotations(data_folder)