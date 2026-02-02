"""Root invoke tasks file."""

from invoke import Collection

from contributing import tasks as contrib

ns = Collection()
ns.add_collection(Collection.from_module(contrib), name="contrib")
