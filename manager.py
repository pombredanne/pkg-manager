import apt
cache = apt.Cache()

for mypkg in apt.Cache():
    if cache[mypkg.name].is_installed:
        print mypkg.name