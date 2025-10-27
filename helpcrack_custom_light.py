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


class TerminalColors:
    RED = '\033[31m'
    GREEN = '\033[32m'
    ORANGE = '\033[33m'
    PURPLE = '\033[35m'
    RESET = '\033[0m'


def log(message, color=TerminalColors.RESET):
    print(f"{time.strftime('[%H:%M:%S]')} - {color}{message}{TerminalColors.RESET}")


def get_work():
    try:
        response = requests.get(f"{SERVER_URL}/get_work", timeout=10)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        log(f"Error fetching work: {e}", TerminalColors.RED)
    return None


def download_file(url, filename):
    try:
        response = requests.get(url, timeout=10)
        with open(filename, "wb") as f:
            f.write(response.content)
        return True
    except Exception as e:
        log(f"Download error for {filename}: {e}", TerminalColors.RED)
        return False


def submit_results(file_name, potfile_content):
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


def crack_file(file_name):
    """
    Run Hashcat on a single file using only a custom wordlist in lightweight settings.
    """
    output_file = f"{file_name}.potfile"
    start_time = time.time()

    # Lightweight Hashcat settings: lowest workload (-w 1), no kernel optimization
    command = [
        HASHCAT_BIN,
        "-m", "22000",
        "-a", "0",
        "-o", output_file,
        "--outfile-format", "1,2",
        "--potfile-disable",
        "--restore-disable",
        "-w", "1",  # minimal workload
        file_name,
        WORDLIST
    ]

    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        found_passwords = set()
        last_hashrate_update = time.time()

        for line in iter(process.stdout.readline, ''):
            line = line.strip()
            if "Speed.#" in line:
                log(line, TerminalColors.ORANGE)
                current_time = time.time()
                if current_time - last_hashrate_update >= 10:
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
        for f in [file_name, output_file]:
            try:
                if os.path.exists(f):
                    os.remove(f)
            except:
                pass
    return None


def main():
    log("Starting lightweight PwnCrack worker...", TerminalColors.ORANGE)
    try:
        while True:
            work = get_work()
            if not work:
                log("No new work available - retrying in 60s...", TerminalColors.RED)
                time.sleep(60)
                continue
            file_name = work.get("file_name")
            download_url = work.get("download_url")
            if not file_name or not download_url:
                log("Invalid work structure received from server.", TerminalColors.RED)
                time.sleep(30)
                continue
            if download_file(download_url, file_name):
                res = crack_file(file_name)
                if res:
                    submit_results(file_name, res)
                else:
                    log(f"No results found for {file_name}", TerminalColors.RED)
            else:
                log(f"Failed to download {file_name}", TerminalColors.RED)
    except KeyboardInterrupt:
        log("Keyboard interrupt received. Exiting...", TerminalColors.RED)
        print("\nThank you for contributing to PwnCrack!")

if __name__ == "__main__":
    main()