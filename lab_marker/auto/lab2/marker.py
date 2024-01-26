import os
import time
from tqdm import tqdm

from config import bcolors, ExecStatus
from lab_marker.utils import print_and_get_selection
from lab_marker.auto.StreamHandler import StreamHandler
from lab_marker.auto.ProcessHandler import ProcessHandler


def find_file(search_folder, file_name):
    """
    Recursively checks through folders to identify the location of the file with the name "file_name". Will only search
    for files with the extensions .py, .java, and .c. If no file with a matching file name is found, the function will
    return None, else the path to the file will be returned.

    :param search_folder: Path of the top directory to be searched in
    :param file_name: Name of the file to be searched, without the extension
    :return: Path of the file if found
    """

    current_files = os.listdir(search_folder)
    lang_map = {
        ".py": "Python",
        ".java": "Java",
        ".c": "C"
    }
    directories = []

    for directory in current_files:
        current_file_name, current_file_ext = os.path.splitext(directory)
        if current_file_name == file_name:
            if current_file_ext in [".py", ".c", ".java"]:
                return {"folder_path": search_folder, "ext": current_file_ext, "language": lang_map[current_file_ext]}
        else:
            temp_path = os.path.join(search_folder, directory)
            if os.path.isdir(temp_path):
                directories.append(temp_path)

    for directory in directories:
        return find_file(directory, file_name)

    return None


def run_lab_2_code(code_file_dir, code_lang, out_stream: StreamHandler, port_num=12000) -> ExecStatus:
    """
    Runs a code file from its directory and writes all the outputs generated by the code to an output stream.

    :param code_file_dir: The directory the code file is located
    :param code_lang: The language the code is written in
    :param out_stream: A StreamHandler class object to write the output to
    :param port_num: The port PingServer is running on
    :return: Exit code of the program
    """

    process_commands = {
        "Python": f"python PingClient.py localhost {port_num}",
        "C": f"./PingClient localhost {port_num}",
        "Java": f"java PingClient localhost {port_num}"
    }

    exec_start_time = time.time()

    if code_lang == "Python":
        client = ProcessHandler(process_commands["Python"], out_stream=out_stream, cwd=code_file_dir)

    elif code_lang == "Java":
        os.system(f"javac {os.path.join(code_file_dir, 'PingClient.java')}")
        client = ProcessHandler(process_commands["Java"], out_stream=out_stream, cwd=code_file_dir)

    else:
        print(f"{bcolors.WARNING}There is no current implementation for C files, skipping evaluation{bcolors.ENDC}")
        out_stream.write_message("Code implemented in C, Please check manually!")
        return ExecStatus.OK

    # If the client exists before 0.1 seconds, there is an issue with the executed code
    client.get_output(timeout=0.1)
    if not client.is_alive:
        return ExecStatus.EXECUTION_FAILED

    try:
        count = 0
        while True:
            client.get_output(timeout=0.1)
            count += 1

            # Do not wait indefinitely for the client output, after a maximum of 30 seconds, the process will be
            # terminated by force.
            if count > 150:
                client.kill_process()
                return ExecStatus.TIMEOUT

    except ChildProcessError:
        # If the client process terminates before 2 seconds have passed, it probably ran into an error during execution
        if time.time() - exec_start_time < 2:
            return ExecStatus.UNEXPECTED_TERMINATION

        return ExecStatus.OK


def run_individual_submission(submission_path, out_stream: StreamHandler) -> ExecStatus:
    """
    Checks if a file with the name 'PingClient' exists in the given directory or any of the subdirectories. If not
    present, will return an exit code of -2. Else, based on the execution of the code, the relevant exit code will be
    returned.

    :param submission_path: Directory to search for the code file
    :param out_stream: Where the output should be written to
    :return: Exit code of the program
    """

    code_file = find_file(submission_path, "PingClient")

    if code_file is None:
        out_stream.write_message("File not found", no_print=True)
        return ExecStatus.FILE_NOT_FOUND

    return run_lab_2_code(code_file["folder_path"], code_file["language"], out_stream)


def mark_submissions_manually(class_path, output_destination):
    """
    User can select which submission they want to mark and mark them individually.

    :param class_path: Path of the folder containing all submissions for a single class
    :param output_destination: Directory where the outputs for each program should be written to
    :return: None
    """

    print(f"{bcolors.OKGREEN}Evaluating labs manually, Please select lab to continue{bcolors.ENDC}\n")
    class_submissions = os.listdir(class_path)

    while True:
        lab_num = print_and_get_selection(class_submissions)
        submission_path = os.path.join(class_path, class_submissions[lab_num])
        code_output_stream = StreamHandler(file_name=f'{output_destination}/{class_submissions[lab_num]}_output.txt',
                                           terminal_out=True)

        print(f"{bcolors.OKGREEN}Running code for submission {class_submissions[lab_num]}....{bcolors.ENDC}")

        status = run_individual_submission(submission_path, code_output_stream)
        if status.value != 0:
            print(f"{bcolors.FAIL}{ExecStatus.get_description(status.value)}{bcolors.ENDC}")
        else:
            print(f"{bcolors.OKGREEN}Done{bcolors.ENDC}\n")

        code_output_stream.close()


def retry_marking(submission_path, retry_dict, output_destination):
    """

    :param submission_path:
    :param retry_dict:
    :param output_destination:
    :return:
    """

    retry_submissions = [x for x in retry_dict.keys()]

    while len(retry_submissions) > 0:
        print(f"\n{bcolors.WARNING}Remaining submissions for remarking")
        print(f"{bcolors.OKBLUE}zID \t\t Reason")

        for key in retry_submissions:
            print(f"{bcolors.OKBLUE}{key} \t {bcolors.FAIL}{retry_dict[key]}")
        print(bcolors.ENDC)

        print(f"{bcolors.OKGREEN}Please select lab to continue{bcolors.ENDC}\n")
        selected_submission = print_and_get_selection(retry_submissions)
        submission = retry_submissions[selected_submission]

        code_output_stream = StreamHandler(file_name=f'{output_destination}/{submission}_output.txt', terminal_out=True)
        status = run_individual_submission(os.path.join(submission_path, submission), out_stream=code_output_stream)
        code_output_stream.close()

        if status.value == 0:
            print(f"{bcolors.OKGREEN}Detected successful execution, removing submission from retry list{bcolors.ENDC}")
            retry_submissions.remove(submission)

        else:
            decision = input("[R]emove, [C]ontinue").lower()
            if decision == "r":
                retry_submissions.remove(submission)


def mark_submissions_auto(class_path, output_destination):
    """

    :param class_path:
    :param output_destination:
    :return:
    """

    class_submissions = os.listdir(class_path)
    failed_processes = {}

    for submission in tqdm(class_submissions):
        if not submission.startswith("."):
            submission_path = os.path.join(class_path, submission)
            code_output_stream = StreamHandler(file_name=f'{output_destination}/{submission}_output.txt')
            status = run_individual_submission(submission_path, code_output_stream)

            if status.value != 0:
                failed_processes[submission] = ExecStatus.get_description(status.value)

            code_output_stream.close()

    print(f"\n{bcolors.WARNING}The following submissions did not execute properly. "
          f"Would you like to manually mark them?")
    print(f"{bcolors.OKBLUE}zID \t\t Reason")

    for key, value in failed_processes.items():
        print(f"{bcolors.OKBLUE}{key} \t {bcolors.FAIL}{value}")
    print(bcolors.ENDC)

    while True:
        decision = input("[y]es/[n]o:")
        if decision == "n":
            break
        if decision == "y":
            retry_marking(class_path, failed_processes, output_destination)
            break


def mark_lab_2(class_path, output_destination, manual_mode=False):
    """
    Iterates through all the directories inside class_path and tries to automatically detect and run the PingClient
    implementation. If manual mode is enabled, the user can manually select which submissions to be run. The output of
    the programs run are automatically saved in a separate file for each user inside the output_destination directory.

    :param class_path: Path of the folder containing all submissions for a single class
    :param output_destination: Directory where the outputs for each program should be written to
    :param manual_mode: If Ture, user can select which submission to be run, else iterates through all in the directory
    :return: None
    """

    if not os.path.exists(output_destination):
        os.makedirs(output_destination)

    if not manual_mode:
        mark_submissions_auto(class_path=class_path, output_destination=output_destination)

    else:
        mark_submissions_manually(class_path=class_path, output_destination=output_destination)
