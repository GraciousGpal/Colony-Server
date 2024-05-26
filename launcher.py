from loguru import logger as log
from multiprocessing import Process
from os import popen
from time import sleep

from lib.client import start, launch_discord

apps = {"colony": start, "discord": launch_discord}

if __name__ == "__main__":
    processes = {}

    def start_process(name: str):
        """
        Starts a process if the name given is in the process list.
        :param name:
        :return:
        """
        item = apps[name]
        p = Process(target=item)
        p.start()
        processes[name] = (
            p,
            item,
        )  # Keep the process and the app to monitor or restart.

    for app in apps:
        log.info(f"Starting : {app}")
        start_process(app)

    while len(processes) > 0:
        for n in processes.copy():
            (p, a) = processes[n]
            sleep(1)
            alive = p.is_alive()
            exitcode = p.exitcode
            if alive:
                continue
            elif exitcode is None and not alive:  # Not finished and not running.
                # Do your error handling and restarting here assigning the new process to processes[n]
                log.error(a, "Process is Unable to Start!")
                start_process(n)
            elif exitcode < 0 or exitcode == 3:
                if exitcode < 0:
                    log.error("Process Ended with an error restarting!")
                start_process(n)
            elif exitcode == 42:
                log.info("Process Restart Called: restarting!")
                start_process(n)
            elif exitcode == 43:
                log.info("Process Update Called: Updating!")
                stream = popen("git pull")
                output = stream.read()
                if output == "Already up to date.\n":
                    log.info(output)
                elif "file changed" in output:
                    log.info("Server Updated!")
                else:
                    log.error("Update Failed!")
                start_process(n)
            else:
                print(a, "Process Completed")
                p.join()  # Allow tidy up.
                del processes[n]  # Removed finished items from the dictionary.

    # When none are left then loop will end.
    print("All Processes are exited.")
