from datetime import datetime
import sys
import os
from typing import List
import time
import shutil


class Logger:
    @staticmethod
    def info(message: str):
        """Log message with information"""
        print(f'{datetime.now()} INFO: {message}')

    @staticmethod
    def debug(message: str):
        """Log message with debug information"""
        print(f'{datetime.now()} DEBUG: {message}')

    @staticmethod
    def warning(message: str):
        """Log message with warning information"""
        print(f'{datetime.now()} WARNING: {message}')

    @staticmethod
    def error(message: str):
        """Log message with error information"""
        print(f'{datetime.now()} ERROR: {message}')


class File:
    def __init__(self, name: str, path: str, logger: Logger):
        self.name = name
        self.path = path
        create_time = os.path.getctime(path)
        self.size = os.path.getsize(self.path)
        self.last_mod = datetime.fromtimestamp(create_time)

    def __repr__(self):
        ...
        return self.name

    def __str__(self):
        ...
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
            if element == '.DS_Store':
                continue
            if os.path.isfile(element_path):
                self.content.append(File(element, element_path, logger))
            elif os.path.isdir(element_path):
                self.content.append(Dir(element, element_path, logger))
            else:
                logger.error('Something is wrong, the element is not file or dir')

    def __repr__(self):
        ...
        return self.name

    def __str__(self):
        ...
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


def compare_files(file1: File, file2: File, logger: Logger):
    """Compare files by date of last modification, size and name
        Return path to files of the files are not same"""
    if not os.path.exists(file1.path) or not os.path.exists(file2.path):
        logger.error(f"Something wrong, these path does not correspond to files {file1} {file2}")
    if file1.name != file2.name:
        logger.warning("You must have passed wrong objects because this object are for different files")
    if file1.size != file2.size or file1.last_mod != file2.last_mod:
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
        print(f' ----- for element {element} -----')
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
                dirs_compare = compare_dirs([elem for elem in replica_dir.content if elem.name == element.name][0],
                                             element, logger)
                if len(dirs_compare) != 0:
                    changed_files.append(ElementDiff(dirs_compare, "modified", 'dir'))
            else:
                logger.error(f"Element {element} if not File and not Dir object so there had to be something wrong")

    for element in replica_dir.content:
        if element.name not in [elem.name for elem in source_dir.content]:
            if isinstance(element, File):
                changed_files.append(ElementDiff(element.path, "deleted"))
            elif isinstance(element, Dir):
                changed_files.append(ElementDiff(element.path, "deleted"))
            else:
                logger.error(f"Element {element} if not File and not Dir object so there had to be something wrong")

    return changed_files


def synch_files(element: ElementDiff, logger: Logger):
    """ Function to synchronize two elements """
    if element.state == 'added':
        replica_path = element.paths
        #TODO change
        replica_path.replace('source', 'replica')
        logger.info(f"File present in replica dir but not in source, removing file: {replica_path} \nfrom replica dir")
        os.remove(replica_path)

    elif element.state == 'deleted':
        #TODO change
        replica_path = element.paths.replace('source', 'replica')
        logger.info(f"File present in source dir but not in source, file was deleted from replica, copying file:"
                    f"{element.paths} to replica dir")
        shutil.copyfile(element.paths, replica_path)

    elif element.state == 'modified':
        logger.info(f"File {element.paths[1]} modified in the replica dir, updating now")
        shutil.copy2(element.paths[0], element.paths[1])
    else:
        logger.error("Some strange comparison occurred and can not be handled {}".format(element))


def synch_directories(element: ElementDiff, logger: Logger):
    """ Function to synchronize directories """

    for elem in element.paths:
        if elem.element_type == 'dir':
            synch_directories(elem, logger)

        elif elem.element_type == 'file':
            synch_files(elem, logger)

        else:
            logger.error("Some dirs comparison is strange and cant be handled {}".format(elem))


if __name__ == '__main__':
    args = sys.argv[1:]
    logger = Logger()
    logger.info("You are running Python program which keeps two directories synchronized")
    # check if synchronizer can run
    if len(args) < 2 or not os.path.exists(args[0]) or not os.path.exists(args[1]):
        logger.info("There was not enough arguments or wrong arguments passed \n Arguments {}".format(args))

    source, replica, sync_time_interval_s = args[0], args[1], args[2]
    while True:
        logger.info("Creating directories trees")
        source_content = Dir(source, os.path.join(os.getcwd(), source), logger)
        replica_content = Dir(source, os.path.join(os.getcwd(), replica), logger)

        # compare content and synchronize
        directories_comparison = compare_dirs(replica_content, source_content, logger)

        # synchronize
        for element in directories_comparison:
            if element.element_type == 'dir':
                synch_directories(element, logger)

            elif element.element_type == 'file':
                synch_files(element, logger)
