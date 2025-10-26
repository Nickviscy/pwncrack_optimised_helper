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


# === Terminal Colors for Readability ===
class TerminalColors:
    RED = '\033[31m'
    GREEN = '\033[32m'
    ORANGE = '\033[33m'
    PURPLE = '\033[35m'
    RESET = '\033[0m'


def log(message, color=TerminalColors.RESET):
    """Print message with timestamp and color."""
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
        response = requests.post(f"{SERVER_URL}/put_work", json={
            "file_name": file_name,
            "potfile_content": potfile_content
        }, timeout=10)
        return response.status_code == 200
    except Exception as e:
        log(f"Error submitting results: {e}", TerminalColors.RED)
        return False


# === Hashcat Execution ===
def crack_file(file_name):
    """
    Run Hashcat on a given file using only a single custom wordlist.
    Returns cracked content if found.
    """
    output_file = f"{file_name}.potfile"

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

        # Real-time Hashcat output monitor
        for line in iter(process.stdout.readline, ''):
            line = line.strip()
            if "Speed.#" in line:
                log(line, TerminalColors.ORANGE)
            elif "Recovered" in line or "Cracked" in line:
                log(line, TerminalColors.GREEN)

        process.wait()

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
    """Processes a file from the work queue in a separate thread. this allows a better usage of ressources"""
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
                log("No new work available - retrying in 30s...", TerminalColors.RED)
                time.sleep(30)
    except KeyboardInterrupt:
        log("Keyboard interrupt received. Shutting down threads...", TerminalColors.RED)
    finally:
        for _ in range(THREAD_COUNT):
            task_queue.put(None)
        task_queue.join()
        log("All threads finished and PwnCrack stopped gracefully.", TerminalColors.ORANGE)


if __name__ == "__main__":
    main()
