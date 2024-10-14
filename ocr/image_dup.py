import os
import send2trash
from PIL import Image
import imagehash
from pathlib import Path
import concurrent.futures
from itertools import combinations
import time
import logging

def are_images_similar(img1_path, img2_path, threshold=1):
    try:
        hash1 = imagehash.average_hash(Image.open(img1_path))
        hash2 = imagehash.average_hash(Image.open(img2_path))
        return hash1 - hash2 < threshold
    except FileNotFoundError:
        logging.info(f"Warning: One of the files not found: {img1_path} or {img2_path}")
        return False
    except Exception as e:
        logging.info(f"Error comparing images: {e}")
        return False

def compare_pair(pair, iteration):
    if len(pair) == 1:
        logging.info(f"Iteration {iteration}: Skipping single file {pair[0].name}")
        return None
    file1, file2 = pair
    logging.info(f"Iteration {iteration}: Comparing {file1.name} and {file2.name}")
    if are_images_similar(file1, file2):
        return file2  # Return the second file to be deleted
    return None

def process_file(file, kept_files):
    if not file.exists():
        logging.info(f"Warning: File not found: {file}")
        return

    should_keep = True
    if kept_files:
        most_recent_kept = kept_files[-1]
        if are_images_similar(file, most_recent_kept):
            should_keep = False
    
    if should_keep:
        kept_files.append(file)
        logging.info(f"Kept: {file.name}")
    else:
        try:
            send2trash.send2trash(str(file))
            logging.info(f"Moved to trash: {file.name}")
        except Exception as e:
            logging.info(f"Error moving file to trash: {e}")

def process_images(folder="", debug=False, workers=4):
    downloads_folder = Path.home() / "Downloads"

    if folder:
        # Process only the specified folder
        folder_to_process = downloads_folder / folder.strip("\"'")
        if not folder_to_process.exists() or not folder_to_process.is_dir():
            logging.info(f"Error: The specified folder does not exist: {folder_to_process}")
            return
        folders_to_process = [folder_to_process]
        logging.info(f"Processing specified folder: {folder_to_process}")
    else:
        # Get all subfolders in the Downloads folder
        folders_to_process = [f for f in downloads_folder.iterdir() if f.is_dir()]
        
        # Sort subfolders by creation time, newest first
        folders_to_process.sort(key=lambda x: x.stat().st_ctime, reverse=True)
        logging.info(f"Found {len(folders_to_process)} subfolders in Downloads")

    # Filter out folders containing "tm_daily_ingest"
    folders_to_process = [f for f in folders_to_process if "tm_daily_ingest" not in f.name]
    logging.info(f"Processing {len(folders_to_process)} folders after filtering")

    logging.info("Press Ctrl+C to stop the program.")

    def process_folder(folder):
        logging.info(f"Processing folder: {folder}")
        iteration_number = 0

        while True:
            screenshot_files = sorted(
                [f for f in folder.glob("screenshot_*.png") if not f.name.startswith("p_")],
                key=lambda x: x.name,
                reverse=True
            )
            
            if len(screenshot_files) < 2:
                logging.info(f"Not enough files to compare in {folder}. Moving to next folder.")
                break

            files_to_process = set()
            
            # Generate pairs based on neighboring positions
            pairs = list(zip(screenshot_files[::2], screenshot_files[1::2]))
            
            # Handle the case of odd number of files
            if len(screenshot_files) % 2 != 0:
                pairs.append((screenshot_files[-1],))

            with concurrent.futures.ThreadPoolExecutor() as executor:
                results = executor.map(lambda p: compare_pair(p, iteration_number), pairs)
                
                for result in results:
                    if result:
                        files_to_process.add(result)
            
            for file in files_to_process:
                try:
                    if debug:
                        new_name = file.with_name(f"p_{file.name}")
                        file.rename(new_name)
                        logging.info(f"Debug mode: Renamed {file.name} to {new_name.name}")
                    else:
                        send2trash.send2trash(str(file))
                        logging.info(f"Moved to trash: {file.name}")
                except Exception as e:
                    logging.info(f"Error processing file: {e}")
            
            if files_to_process:
                action = "Renamed" if debug else "Deleted"
                logging.info(f"Iteration {iteration_number}: {action} {len(files_to_process)} files.")
                iteration_number += 1
                logging.info(f"Completed iteration {iteration_number}. Moving on to the next round!")
            else:
                logging.info(f"Iteration {iteration_number}: No duplicates found.")
                logging.info("Switching to sequential comparison logic.")

                # Sequential comparison logic
                for i in range(len(screenshot_files) - 1):
                    file1 = screenshot_files[i]
                    file2 = screenshot_files[i + 1]
                    logging.info(f"Sequential comparison: Comparing {file1.name} and {file2.name}")
                    if are_images_similar(file1, file2):
                        try:
                            if debug:
                                new_name = file2.with_name(f"p_{file2.name}")
                                file2.rename(new_name)
                                logging.info(f"Debug mode: Renamed {file2.name} to {new_name.name}")
                            else:
                                send2trash.send2trash(str(file2))
                                logging.info(f"Moved to trash: {file2.name}")
                        except Exception as e:
                            logging.info(f"Error processing file: {e}")

                logging.info("All iterations complete. Moving to next folder.")
                break  # Exit the while loop to move to the next folder

            time.sleep(1)  # Wait for 1 second before the next iteration

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            executor.map(process_folder, folders_to_process)
    except KeyboardInterrupt:
        logging.info("\nProgram stopped by user.")

    logging.info("All folders processed. Exiting program.")

# This function can be called from another script
def run_image_deduplication(folder="", debug=False, workers=4):
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    process_images(folder, debug, workers)

# If you want to run this script directly, you can use this:
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Process and deduplicate screenshot images in real-time.")
    parser.add_argument("--folder", default="", help="Subfolder name in Downloads to process")
    parser.add_argument("--debug", action="store_true", help="Run in debug mode: rename duplicates instead of deleting")
    parser.add_argument("--workers", type=int, default=4, help="Number of concurrent workers")
    args = parser.parse_args()
    
    run_image_deduplication(args.folder, args.debug, args.workers)
