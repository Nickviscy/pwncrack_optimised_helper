# ========================== #
# ====PWNCRACK HELPCRACK==== #
# ========================== #
# === Optimized for high === #
# === efficiency, custom === #
# === wordlists and good === #
# === hardware workload  === #
# ========================== #
# ===  Made by "lonely"  === #
# ========================== #
# ====  Version  1.0.1  ==== #


import requests
import subprocess
import os
import sys
import time
import uuid
import threading
import queue

# === configuration ===
SERVER_URL = "http://pwncrack.org"
HASHCAT_BIN = "hashcat"
WORDLIST = "YOUR_WORDLIST.txt" # set a custom wordlist, must be in same directory (.txt only)
RESULTS_FILE = "found_passwords.txt" # gives you all found passwords in a .txt file
THREAD_COUNT = 3  # number of parallel cracking threads, adjust for your hardware
CRACKER_ID = str(uuid.uuid4())
USERKEY = "SET USER KEY" # important: add your user key 

# === Terminal Colors for readability ===
class TerminalColors:
    RED = '\033[31m'
    GREEN = '\033[32m'
    ORANGE = '\033[33m'
    PURPLE = '\033[35m'
    RESET = '\033[0m'


def log(message, color=TerminalColors.RESET):
    """Print a message with timestamp and color."""
    print(f"{time.strftime('[%H:%M:%S]')} - {color}{message}{TerminalColors.RESET}")


# === Server Communication ===
def get_work():
    """Fetch work from the server."""
    try:
        response = requests.get(f"{SERVER_URL}/get_work", timeout=10)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        log(f"Error fetching work: {e}", TerminalColors.RED)
    return None


def download_file(url, filename):
    """Download a hash file from the server."""
    try:
        response = requests.get(url, timeout=10)
        with open(filename, "wb") as f:
            f.write(response.content)
        return True
    except Exception as e:
        log(f"Download error for {filename}: {e}", TerminalColors.RED)
        return False


def submit_results(file_name, potfile_content):
    """Submit cracked results back to the server."""
    try:
        log(f"Submitting results for {file_name}", TerminalColors.GREEN)
        response = requests.post(f"{SERVER_URL}/put_work", json={
            "file_name": file_name,
            "potfile_content": potfile_content
        }, timeout=10)
        log(f"Response status code: {response.status_code}", TerminalColors.GREEN)
        return response.status_code == 200
    except Exception as e:
        log(f"Error submitting results: {e}", TerminalColors.RED)
        return False


def send_hashrate(file_name, hashrate):
    """Send hashrate updates to server for leaderboard tracking."""
    try:
        response = requests.post(f"{SERVER_URL}/update_hashrate", json={
            "file_name": file_name,
            "hashrate": hashrate,
            "cracker_id": CRACKER_ID,
            "user_key": USERKEY
        }, timeout=10)
        return response.status_code == 200
    except Exception as e:
        log(f"Error sending hashrate: {e}", TerminalColors.RED)
        return False


def parse_hashrate_from_line(line):
    """Parse hashrate from Hashcat output line."""
    hashrate = 0
    try:
        if line.startswith("Speed.#"):
            parts = line.split(':')
            if len(parts) > 1:
                rate_str = parts[1].strip().split(' ')[0]
                unit = parts[1].strip().split(' ')[1] if len(parts[1].strip().split(' ')) > 1 else ''
                try:
                    rate = float(rate_str)
                    if unit == 'kH/s':
                        rate *= 1e3
                    elif unit == 'MH/s':
                        rate *= 1e6
                    elif unit == 'GH/s':
                        rate *= 1e9
                    elif unit == 'TH/s':
                        rate *= 1e12
                    hashrate = rate
                except ValueError:
                    pass
    except Exception:
        pass
    return hashrate


# === Hashcat Execution ===
def crack_file(file_name):
    """
    Run Hashcat on a given file using only a single custom wordlist.
    Returns cracked content if found.
    """
    output_file = f"{file_name}.potfile"
    start_time = time.time()

    # Optimized Hashcat command
    command = [
        HASHCAT_BIN,
        "-m", "22000",
        "-a", "0",
        "-o", output_file,
        "--outfile-format", "1,2",
        "--potfile-disable",
        "--restore-disable",
        "-O",
        "-w", "4",
        file_name,
        WORDLIST
    ]

    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        found_passwords = set()
        last_hashrate_update = time.time()

        # Real-time Hashcat output monitor
        for line in iter(process.stdout.readline, ''):
            line = line.strip()
            if "Speed.#" in line:
                log(line, TerminalColors.ORANGE)
                # Send hashrate updates every 5 seconds
                current_time = time.time()
                if current_time - last_hashrate_update >= 5:
                    hashrate = parse_hashrate_from_line(line)
                    if hashrate > 0:
                        send_hashrate(file_name, hashrate)
                        last_hashrate_update = current_time
            elif "Recovered" in line or "Cracked" in line:
                log(line, TerminalColors.GREEN)

        process.wait()
        end_time = time.time()
        processing_time = end_time - start_time
        log(f"Processing time for {file_name}: {processing_time:.2f} seconds", TerminalColors.PURPLE)

        # Check for results
        if os.path.exists(output_file):
            with open(output_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
                for line in lines:
                    if ":" in line:
                        pw = line.split(":", 1)[1].strip()
                        if pw not in found_passwords:
                            found_passwords.add(pw)
                            print(f"{TerminalColors.GREEN}Password found: {pw}{TerminalColors.RESET}")
                if found_passwords:
                    with open(RESULTS_FILE, "a", encoding="utf-8") as out:
                        for pw in found_passwords:
                            out.write(pw + "\n")
                    return "".join(lines)
        return None
    except Exception as e:
        log(f"Hashcat execution error: {e}", TerminalColors.RED)
    finally:
        # Clean up temporary files
        for f in [file_name, output_file]:
            try:
                if os.path.exists(f):
                    os.remove(f)
            except:
                pass
    return None


# === Worker Thread Function ===
def worker(task_queue):
    """Processes a file from the work queue in a separate thread."""
    while True:
        work = task_queue.get()
        if work is None:
            break  # Stop signal
        file_name = work["file_name"]
        download_url = work["download_url"]

        if download_file(download_url, file_name):
            result = crack_file(file_name)
            if result:
                if submit_results(file_name, result):
                    log(f"Result uploaded for {file_name}", TerminalColors.PURPLE)
                else:
                    log(f"Failed to submit results for {file_name}", TerminalColors.RED)
            else:
                log(f"No results found for {file_name}", TerminalColors.RED)
        else:
            log(f"Failed to download {file_name}", TerminalColors.RED)
        task_queue.task_done()


# === Main Control Loop ===
def main():
    log("Starting PwnCrack Multi-threaded Version...", TerminalColors.ORANGE)
    task_queue = queue.Queue()

    # Launch worker threads
    for _ in range(THREAD_COUNT):
        t = threading.Thread(target=worker, args=(task_queue,), daemon=True)
        t.start()

    try:
        while True:
            work = get_work()
            if work:
                task_queue.put(work)
                log(f"New job queued: {work['file_name']}", TerminalColors.GREEN)
            else:
                log("No new work available - retrying in 60s...", TerminalColors.RED)
                time.sleep(60)
    except KeyboardInterrupt:
        log("Keyboard interrupt received. Shutting down threads...", TerminalColors.RED)
    finally:
        for _ in range(THREAD_COUNT):
            task_queue.put(None)
        task_queue.join()
        log("All threads finished and PwnCrack stopped gracefully.", TerminalColors.ORANGE)
        print("\nThank you for using and contributing to PwnCrack!")


if __name__ == "__main__":
    main()
