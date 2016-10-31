from subprocess import check_output, CalledProcessError
from copy import deepcopy
import re
import sys

TYPE_PRE_DEPEND = "_pre_install"
TYPE_NORMAL = "_normal"
TYPE_BUILD_DEP = "_to_build"
TYPE_BUILD_DEP_INDEP = "_to_build_all"
TYPE_FLUSH = "_flush_"


def read_file(filename):
    with open(filename) as f:
        return f.read().splitlines()


def write_file(filename, _buf):
    with open(filename, 'w') as f:
        for item in _buf:
            f.write("{}\n".format(item))


def merge_dict(source, destination):
    """
    Dict merger, thanks to vincent
    http://stackoverflow.com/questions/20656135/python-deep-merge-dictionary-data

    >>> a = { 'first' : { 'all_rows' : { 'pass' : 'dog', 'number' : '1' } } }
    >>> b = { 'first' : { 'all_rows' : { 'fail' : 'cat', 'number' : '5' } } }
    >>> merge(b, a) == { 'first' : { 'all_rows' : { 'pass' : 'dog', 'fail' : 'cat', 'number' : '5' } } }
    True
    """
    for key, value in source.items():
        if isinstance(value, dict):
            # get node or create one
            node = destination.setdefault(key, {})
            merge_dict(value, node)
        else:
            destination[key] = value

    return destination


class CollectDependencies(object):
    _normal = "Depends"
    _pre_install = "PreDepends"
    _to_build = "Build-Depends"
    _to_build_all = "Build-Depends-Indep"

    _all_types = {
        TYPE_PRE_DEPEND: "PreDepends",
        TYPE_NORMAL: "Depends",
        TYPE_BUILD_DEP: "Build-Depends",
        TYPE_BUILD_DEP_INDEP: "Build-Depends-Indep"
    }

    _ignore_list = [
        'debconf',
        'perl-base',
        '',
    ]

    _trees = {}
    _tree_to_print = []

    def __init__(self, package_list):
        self.pkg_list = package_list
        self.pkg_list_names = []

        self._collect()

    @staticmethod
    def get_raw_dependencies(package_name):
        cmd = "apt-rdepends"
        # cmd = "cat"
        args = package_name

        try:
            print("...running: '{} {}'".format(cmd, args))
            return check_output([cmd, args]).splitlines()
        except CalledProcessError as ex:
            print('Error: {}'.format(ex))
            return None
        except OSError as ex:
            print('Error: {}'.format(ex))
            return None

    @staticmethod
    def _extract_relation(line):
        _relation_sign = ""
        _version = ""

        if line.find(': ') > -1:
            _pkg = line.split(': ')[1][:]
        else:
            _pkg = line

        _partition = _pkg.split(' ')
        _name = _partition[0]
        if _partition.__len__() > 1:
            if _partition.__len__() < 3:
                _version = _partition[1:-1]
            else:
                _relation_sign = _partition[1][1:]
                _version = _partition[2][:-1]

        return _name, _relation_sign, _version

    def _extract_pkg_data(self, line):
        _type = ""
        _name, _relation, _version = self._extract_relation(line)

        if re.match(
                r'[\s]*\b{}\b:'.format(self._all_types[TYPE_BUILD_DEP]),
                line
        ):
            _type = TYPE_BUILD_DEP
        elif re.match(
                r'[\s]*\b{}\b:'.format(self._all_types[TYPE_BUILD_DEP_INDEP]),
                line
        ):
            _type = TYPE_BUILD_DEP_INDEP
        elif re.match(
                r'[\s]*\b{}\b:'.format(self._all_types[TYPE_PRE_DEPEND]),
                line
        ):
            _type = TYPE_PRE_DEPEND
        elif re.match(
                r'[\s]*\b{}\b:'.format(self._all_types[TYPE_NORMAL]),
                line
        ):
            _type = TYPE_NORMAL
        elif not re.match(r'[\s]+', line):
            _type = TYPE_FLUSH

        return _type, _name, _relation, _version

    def parse_raw_dependencies(self, lines):
        print("...loaded {} lines".format(lines.__len__()))

        _pkg_dep_leaf = {
            '_full_name': "",
            TYPE_PRE_DEPEND: {},
            TYPE_NORMAL: {},
            TYPE_BUILD_DEP: {},
            TYPE_BUILD_DEP_INDEP: {},
            '_version': "",
            '_relation': ""
        }

        _key = ""
        _leaf = {}

        # Parse it into tree
        for line in lines:
            # if there is no whitespace - it is a key

            _dependency_type, _name, _relation, _version = \
                self._extract_pkg_data(line)

            if _dependency_type == TYPE_FLUSH:
                if _key not in _leaf:
                    if _key.__len__() > 0:
                        _leaf[_key] = deepcopy(_sub_leaf)
                    else:
                        _sub_leaf = deepcopy(_pkg_dep_leaf)
                        _key = _name
                        continue

                _sub_leaf = deepcopy(_pkg_dep_leaf)
                _key = _name

            if re.match(r'[\s]+', line):
                # create leaf
                if _name not in _sub_leaf[_dependency_type]:
                    _sub_leaf[_dependency_type][_name] = [_relation, _version]
                else:
                    _sub_leaf[_dependency_type][_name].append([
                        _relation,
                        _version
                    ])
            else:
                if _dependency_type != TYPE_FLUSH:
                    print("Incorrect log line detected (ignore): {}".format(line))
                else:
                    pass
                #     if _name not in _leaf[_dependency_type]:
                #         _leaf[_dependency_type][_name] = [_relation, _version]
                #     else:
                #         _leaf[_dependency_type][_name].append([
                #             _relation,
                #             _version
                #         ])

        _leaf[_key] = _sub_leaf
        return _leaf

    def _collect(self):
        _inventory = {}

        for pkg_name in self.pkg_list:

            lines = self.get_raw_dependencies(pkg_name)
            if lines is None:
                print("...error while reading dependencies, skipping")
                continue
            else:
                parsed_dict = self.parse_raw_dependencies(lines)
                if lines[0] not in self.pkg_list_names:
                    self.pkg_list_names.append(lines[0])
                merge_dict(parsed_dict, _inventory)

        # _inventory.pop('_full_name')
        # _inventory.pop('_relation')
        # _inventory.pop('_version')
        self._inventory = _inventory

    def print_package(self, _level, _dep, _name, _relation, do_print=False):
        _string = "{}: {} ({})".format(
            _dep,
            _name,
            _relation
        )

        if do_print:
            print("{}{}".format(
                "   " * _level,
                _string
            ))

        self._tree_to_print.append((_level, _string))

    def _tree_iterator(self, _pkg_name, _level):
        # iterate currect tree branch
        local_level = _level + 1

        if _level == 0:
            pass
        # print all deps
        for _type_key, _type_string in self._all_types.iteritems():
            _keys = self._inventory[_pkg_name][_type_key].keys()
            _keys.sort()

            for _key in _keys:
                if _key not in self._listed_pkgs:
                    # this pkg is first time seen, save it on this level
                    self._listed_pkgs[_key] = local_level
                    self.print_package(
                        local_level,
                        _type_string,
                        _key,
                        self._inventory[_pkg_name][_type_key][_key]
                    )
                    # Check if we are to ignore this package
                    if _key not in self._ignore_list:
                        self._tree_iterator(_key, local_level)
                elif self._listed_pkgs[_key] >= local_level:
                    # seen on deeper level, remove it
                    # self._listed_pkgs.pop(_key)
                    # ...and print
                    self.print_package(
                        local_level,
                        _type_string,
                        _key,
                        self._inventory[_pkg_name][_type_key][_key]
                    )
                    pass
                elif self._listed_pkgs[_key] < local_level:
                    # do not print it again on deeper level
                    pass

    def build_tree(self):
        # start from first item and build dependencies
        _level = 0
        # flush listed packages set
        self._listed_pkgs = {}
        self._tree_to_print = []

        _keys = self.pkg_list_names
        _keys.sort()

        for _key in _keys:

            # flush listed packages set
            self._listed_pkgs = {}
            self._tree_to_print = []

            self.print_package(_level,"",_key,"")

            self._tree_iterator(_key, _level)

            # at this point we have a resolved tree for single package
            # save it and flush tmp tree
            self._trees[_key] = self._tree_to_print

    def resolve_tree(self, save_to_files=False):
        self.resolved = []

        print("...removing duplicate records")
        for _pkg_name in self.pkg_list_names:
            _list = self._trees[_pkg_name]
            _sorted = sorted(_list, key=lambda _list: _list[0])
            _sorted.reverse()

            _resolved_list = [_sorted[0][1]]
            for idx in range(1, _list.__len__(), 1):

                # if _list[idx-1][1] != _list[idx][1]:
                #     _resolved_list.append(_list[idx][1])
                if _sorted[idx][1] not in _resolved_list:
                    _resolved_list.append(_sorted[idx][1])

            if save_to_files:
                write_file(_pkg_name+".resolved", _resolved_list)

            self.resolved += _resolved_list

        return self.resolved


def main():
    if sys.argv.__len__() < 2:
        print "Supply file with packages as a parameter: " \
              "dep_resolver.py pkg.list"
        exit(1)
    else:
        _list = read_file(sys.argv[1])

        pkg_dependencies = CollectDependencies(_list)
        print ("\nTotal packages in inventory: {}".format(
            pkg_dependencies._inventory.__len__()
        ))

        print("...building package tree")
        pkg_dependencies.build_tree()

        print("...resolving build order")
        resolved_list = pkg_dependencies.resolve_tree(save_to_files=True)

        filename = '_res.tree'
        print("Writing to file: '{}'".format(filename))
        write_file(filename, resolved_list)

        exit(0)


if __name__ == "__main__":
    main()
