"""Root invoke tasks file."""

from invoke import Collection

from dev import tasks as dev_tasks

ns = Collection()
ns.add_collection(Collection.from_module(dev_tasks), name="dev")
