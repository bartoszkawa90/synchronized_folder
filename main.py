from datetime import datetime
import sys
import os
import time
import shutil


class Logger:
    def __init__(self, logging_file_path: str, clear: bool):
        self.file = logging_file_path
        if clear:
            open(self.file, "w").close()

    def info(self, message: str):
        """Log message with information"""
        with open(self.file, 'a') as f:
            f.write(f'{datetime.now()} INFO: {message}')
            f.close()
        print(f'{datetime.now()} INFO: {message}')

    def debug(self, message: str):
        """Log message with debug information"""
        with open(self.file, 'a') as f:
            f.write(f'{datetime.now()} INFO: {message}')
            f.close()
        print(f'{datetime.now()} DEBUG: {message}')

    def warning(self, message: str):
        """Log message with warning information"""
        with open(self.file, 'a') as f:
            f.write(f'{datetime.now()} INFO: {message}')
            f.close()
        print(f'{datetime.now()} WARNING: {message}')

    def error(self, message: str):
        """Log message with error information"""
        with open(self.file, 'a') as f:
            f.write(f'{datetime.now()} INFO: {message}')
            f.close()
        print(f'{datetime.now()} ERROR: {message}')


class File:
    def __init__(self, name: str, path: str, logger: Logger):
        self.name = name
        self.path = path
        create_time = os.path.getctime(path)
        self.size = os.path.getsize(self.path)
        self.last_mod = datetime.fromtimestamp(create_time)

    def __repr__(self):
        return self.name

    def __str__(self):
        return self.name


class Dir:
    def __init__(self, name: str, path: str, logger: Logger):
        self.name = name
        self.path = path
        create_time = os.path.getctime(path)
        self.last_mod = datetime.fromtimestamp(create_time)
        self.content = []

        content = os.listdir(path)
        for element in content:
            element_path = os.path.join(self.path, element)
            if element == '.DS_Store': # skip .ds_store, only on macos, better not to consider
                continue
            if os.path.isfile(element_path):
                self.content.append(File(element, element_path, logger))
            elif os.path.isdir(element_path):
                self.content.append(Dir(element, element_path, logger))
            else:
                logger.error('Something is wrong, the element is not file or dir')

    def __repr__(self):
        return self.name

    def __str__(self):
        return self.name


class ElementDiff:
    def __init__(self, paths, state: str, element_type: str='file'):
        """
        state:
             - added - new file or dir added to source dir and not in replica dir
             - modified - file or dir was modified
             - deleted - file or dir was deleted from source but is present in replica dir
        """
        if isinstance(paths, tuple):
            self.paths = list(paths)
        else:
            self.paths = paths
        self.state = state
        self.element_type = element_type

    def __repr__(self):
        return f"{self.paths} : {self.state}"

    def __str__(self):
        return f"{self.paths} : {self.state}"


def compare_files(file1: File, file2: File, logger: Logger):
    """Compare files by date of last modification, size and name
        Return path to files of the files are not same"""
    if not os.path.exists(file1.path) or not os.path.exists(file2.path):
        logger.error(f"Something wrong, these path does not correspond to files {file1} {file2}")
    if file1.name != file2.name:
        logger.warning("You must have passed wrong objects because this object are for different files")
    if file1.size != file2.size or (file1.last_mod - file2.last_mod).seconds > 30:
        return file1.path, file2.path
    with open(file1.path, 'r') as f1, open(file2.path, 'r') as f2:
        if f1.read() != f2.read():
            f1.close()
            f2.close()
            return file1.path, file2.path
        f1.close()
        f2.close()
    return None


def compare_dirs(source_dir: Dir, replica_dir: Dir, logger: Logger):
    """Compare dirs by date of last modification and name"""
    changed_files = []
    for element in source_dir.content:
        if isinstance(element, File):
            if element.name not in [elem.name for elem in replica_dir.content]:
                changed_files.append(ElementDiff(element.path, "added"))
            elif element.name in [elem.name for elem in replica_dir.content]:
                    files_compare = compare_files([elem for elem in replica_dir.content
                                   if elem.name == element.name ][0], element, logger)
                    if files_compare is not None:
                        changed_files.append(ElementDiff(files_compare, "modified"))

        elif isinstance(element, Dir):
            # pay attention to deleted and added dirs, modified can be handled by synchronizing files
            if element.name not in [elem.name for elem in replica_dir.content]:
                changed_files.append(ElementDiff(element.path, "added", 'dir'))
            elif element.name in [elem.name for elem in replica_dir.content]:
                dirs_compare = compare_dirs(element, [elem for elem in replica_dir.content
                                                      if elem.name == element.name][0], logger)
                if len(dirs_compare) != 0:
                    changed_files.append(ElementDiff(dirs_compare, "modified", 'dir'))
            else:
                logger.error(f"Element {element} if not File and not Dir object so there had to be something wrong")

    for element in replica_dir.content:
        if element.name not in [elem.name for elem in source_dir.content]:
            a = 1
            if isinstance(element, File):
                changed_files.append(ElementDiff(element.path, "deleted"))
            elif isinstance(element, Dir):
                changed_files.append(ElementDiff(element.path, "deleted", 'dir'))
            else:
                logger.error(f"Element {element} if not File and not Dir object so there had to be something wrong")

    return changed_files


def synch_files(element: ElementDiff, source_dir_name: str, replica_dir_name: str,  logger: Logger):
    """ Function to synchronize two elements """
    if element.state == 'added':
        if isinstance(element.paths, list):
            source = [path for path in element.paths if source_dir_name in path][0]
            replica = [path for path in element.paths if replica_dir_name in path][0]
        else:
            source = element.paths
            replica = element.paths.replace(source_dir_name, replica_dir_name)
        logger.info(f'File {source} added to source, adding to replica')
        shutil.copyfile(source, replica)

    elif element.state == 'deleted':
        replica_path = element.paths.replace(source_dir_name, replica_dir_name)
        logger.info(f"File deleted from source, removing from replica")
        os.remove(replica_path)

    elif element.state == 'modified':
        source = [path for path in element.paths if source_dir_name in path][0]
        replica = [path for path in element.paths if replica_dir_name in path][0]
        logger.info(f"File {source} modified in the replica dir, updating now")
        shutil.copy2(source, replica)
        # update timeof last modification on both files to avoid unnecessary updating, when copying content the
        # modification dates may not be the same
        time_now = datetime.now()
        os.utime(source, (datetime.timestamp(time_now), datetime.timestamp(time_now)))
        os.utime(replica, (datetime.timestamp(time_now), datetime.timestamp(time_now)))

    else:
        logger.error("Some strange comparison occurred and can not be handled {}".format(element))


def synch_directories(element: ElementDiff,  source_dir_name: str, replica_dir_name: str, logger: Logger):
    """ Function to synchronize directories """
    if isinstance(element.paths, str) and element.element_type == 'dir':
        # element must be deleted or added
        if element.state == 'added':
            logger.info(f'Dir {element.paths} added to source, adding it also to replica')
            shutil.copytree(element.paths, element.paths.replace(source_dir_name, replica_dir_name))
        elif element.state == 'deleted':
            logger.info(f'Dir {element.paths} deleted from source, deleting from replica')
            shutil.rmtree(element.paths)
    else:
        for elem in element.paths:
            if elem.element_type == 'dir':
                synch_directories(elem, source_dir_name, replica_dir_name, logger)
            elif elem.element_type == 'file':
                synch_files(elem, source_dir_name, replica_dir_name, logger)
            else:
                logger.error("Some dirs comparison is strange and cant be handled {}".format(elem))


if __name__ == '__main__':
    """
    Arguments:
        source path
        replica path
        synchronization time interval
        path to logging file
        -- clear_log - flag which clears passed logging file
    """
    args = sys.argv[1:]
    # check if synchronizer can run
    if len(args) < 2 or not os.path.exists(args[0]) or not os.path.exists(args[1]):
        print("There was not enough arguments or wrong arguments passed \n Arguments {}".format(args))

    source, replica, sync_time_interval_s, logging_file, clear_log = args[0], args[1], args[2], args[3], args[4]
    logger = Logger(logging_file_path=logging_file, clear=clear_log=='--clear_log')
    logger.info("You are running Python program which keeps two directories synchronized\n")

    while True:
        logger.info("Creating directories trees and verifying difference in source path and replica\n")
        source_content = Dir(source, os.path.join(os.getcwd(), source), logger)
        replica_content = Dir(source, os.path.join(os.getcwd(), replica), logger)

        # compare content and synchronize
        directories_comparison = compare_dirs(source_dir=source_content, replica_dir=replica_content, logger=logger)
        source_dir_name = source.split('/')[-2] if source.endswith('/') else source.split('/')[-1]
        replica_dir_name = replica.split('/')[-2] if replica.endswith('/') else replica.split('/')[-1]

        # synchronize
        for element in directories_comparison:
            if element.element_type == 'dir':
                synch_directories(element, source_dir_name, replica_dir_name, logger)

            elif element.element_type == 'file':
                synch_files(element, source_dir_name, replica_dir_name, logger)

        # wait for next synchronization
        time.sleep(int(sync_time_interval_s))
