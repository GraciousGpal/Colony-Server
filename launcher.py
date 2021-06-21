import logging
from multiprocessing import Process
from os import popen
from time import sleep

from lib.client import start

apps = {'colony': start}

if __name__ == '__main__':
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
        processes[name] = (p, item)  # Keep the process and the app to monitor or restart.


    for app in apps:
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
                logging.error(a, 'Process is Unable to Start!')
                start_process(n)
            elif exitcode < 0 or exitcode == 3:
                if exitcode < 0:
                    logging.error("Process Ended with an error restarting!")
                start_process(n)
            elif exitcode == 42:
                logging.info("Process Restart Called: restarting!")
                start_process(n)
            elif exitcode == 43:
                logging.info("Process Update Called: Updating!")
                stream = popen('git pull')
                output = stream.read()
                if output == 'Already up to date.\n':
                    logging.info(output)
                elif 'file changed' in output:
                    logging.info("Server Updated!")
                else:
                    logging.error("Update Failed!")
                start_process(n)
            else:
                print(a, 'Process Completed')
                p.join()  # Allow tidy up.
                del processes[n]  # Removed finished items from the dictionary.

    # When none are left then loop will end.
    print('All Processes are exited.')
