import apt
import sys

cache = None
_listed_names = {}


def get_dependencies(pkg_name):
    global cache
    return cache[pkg_name].candidate.dependencies


def print_dependencies(package, level):
    global _listed_names
    global cache
    local_level = level + 1

    if package.name in _listed_names:
        if _listed_names[package.name] < level:
            return

    _deps = get_dependencies(package.name)

    for list_dependency in _deps:
        for dependency in list_dependency:
            print("{}{}{}{}".format(
                '   ' * local_level,
                dependency.name,
                dependency.relation,
                dependency.version
            ))
            if dependency.name not in _listed_names:
                _listed_names[dependency.name] = local_level
            if not dependency.pre_depend:
                print_dependencies(cache[dependency.name], local_level)


def main():
    global cache

    if sys.argv.__len__() < 2:
        print "Supply package name as a parameter"
        exit(1)
    else:
        _level = 1

        # apt_pkg.init_config()
        # apt_pkg.init_system()

        cache = apt.Cache()

        _pkg_name = sys.argv[1]

        if _pkg_name in cache:
            print_dependencies(cache[sys.argv[1]], _level)

            # for mypkg in apt.Cache():
            #     if mypkg.name == sys.argv[1]:
            #         print mypkg.name
            #         print_dependencies(mypkg, _level)

            exit(0)
        else:
            print("Package '{}' not found in cache.".format(_pkg_name))

if __name__ == "__main__":
    main()
