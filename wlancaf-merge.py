from __future__ import print_function

import sys
from argparse import ArgumentParser
from os import path, listdir
from shutil import rmtree
from multiprocessing import Process
from subprocess import PIPE, Popen


def subprocess_run(cmd):
    subproc = Popen(cmd, stdout=PIPE, stderr=PIPE,
                    shell=True, universal_newlines=True)
    subproc.wait()
    talk = subproc.communicate()
    exitCode = subproc.returncode
    if exitCode != 0:
        print("An error was detected while running the subprocess:\n"
              "exit code: %d\n"
              "stdout: %s\n"
              "stderr: %s" % (exitCode, talk[0], talk[1]))
        sys.exit(exitCode)
    return talk


def get_git_version():
    cmd = "git --version | cut -d ' ' -f3 | head -n1 | tr -d '\n'"
    talk = subprocess_run(cmd)
    version = talk[0].strip().split(".")
    major_version = int(version[0])
    sub_version = int(version[1])
    return major_version, sub_version


def extra_git_cmd():
    major_version, sub_version = get_git_version()
    if major_version >= 2 and sub_version >= 9:
        extra = "--allow-unrelated-histories"
    return extra


def err(message):
    print(message)
    sys.exit(1)


def parameters():
    param = ArgumentParser(description="Wlan CAF driver updater/initial merging into Android kernel source", )
    param.add_argument("-W", "--wlan", choices=['qcacld', 'prima'], help="Your WLAN driver type either qcacld/prima.", required=True)
    param.add_argument("-I", "--init", choices=['update', 'initial'], help="Choose wether to update or initial merging.", required=True)
    param.add_argument("-T", "--tag", help="Your CAF tag you want to merge.", required=True)
    params = vars(param.parse_args())
    wlan_type = params["wlan"]
    merge_type = params["init"]
    tag = params["tag"]
    return wlan_type, merge_type, tag


def repo():
    wlan_type, merge_type, tag = parameters()
    if wlan_type == "qcacld":
        repo_url = {
            "qcacld-3.0": "https://source.codeaurora.org/quic/la/platform/vendor/qcom-opensource/wlan/qcacld-3.0",
            "fw-api": "https://source.codeaurora.org/quic/la/platform/vendor/qcom-opensource/wlan/fw-api/",
            "qca-wifi-host-cmn": "https://source.codeaurora.org/quic/la/platform/vendor/qcom-opensource/wlan/qca-wifi-host-cmn/"
        }
    elif wlan_type == "prima":
        repo_url = "https://source.codeaurora.org/quic/la/platform/vendor/qcom-opensource/wlan/prima/"
    return repo_url


def merging():
    wlan_type, merge_type, tag = parameters()
    major_version, sub_version = get_git_version()
    repo_url = repo()
    extra = extra_git_cmd()
    if wlan_type == "qcacld" and merge_type == "initial":
        for repos in repo_url:
            print("fetching %s with tag '%s'" % (repos, tag))
            cmd = "git fetch %s %s" % (repo_url[repos], tag)
            talk = subprocess_run(cmd)
            while True:
                print("merging %s into kernel source..." % repos)
                cmd = "git merge -s ours --no-commit %s FETCH_HEAD" % extra
                talk = subprocess_run(cmd)
                break
            while True:
                print("committing changes...")
                cmd = "git read-tree --prefix=drivers/staging/%s \
                       -u FETCH_HEAD" % repos
                talk = subprocess_run(cmd)
                break
            while True:
                cmd = 'git commit -m "%s: Merge init tag \'%s\' into `git rev-parse --abbrev-ref HEAD`"' \
                       % (repos, tag)
                talk = subprocess_run(cmd)
                break
    elif wlan_type == "qcacld" and merge_type == "update":
        for repos in repo_url:
            print("fetching %s with tag '%s'" % (repos, tag))
            cmd = "git fetch %s %s" % (repo_url[repos], tag)
            talk = subprocess_run(cmd)
            while True:
                print("merging %s into kernel source and committing changes..." % repos)
                cmd = 'git merge -X subtree=drivers/staging/%s \
                       --edit -m "%s: Merge tag \'%s\' into `git rev-parse --abbrev-ref HEAD`" FETCH_HEAD --no-edit' \
                       % (repos, repos, tag)
                talk = subprocess_run(cmd)
                break
    elif wlan_type == "prima" and merge_type == "initial":
        print("fetching %s with tag '%s'" % (wlan_type, tag))
        cmd = "git fetch %s %s" % (repo_url, tag)
        talk = subprocess_run(cmd)
        print("merging %s into kernel source..." % wlan_type)
        cmd = "git merge -s ours --no-commit %s FETCH_HEAD" % extra
        talk = subprocess_run(cmd)
        cmd = "git read-tree --prefix=drivers/staging/%s \
               -u FETCH_HEAD" % wlan_type
        talk = subprocess_run(cmd)
        print("committing changes...")
        cmd = 'git commit -m "%s: Merge init tag \'%s\' into `git rev-parse --abbrev-ref HEAD`"' \
              % (wlan_type, tag)
        talk = subprocess_run(cmd)
    elif wlan_type == "prima" and merge_type == "update":
        print("fetching %s with tag '%s'" % (wlan_type, tag))
        cmd = "git fetch %s %s" % (repo_url, tag)
        talk = subprocess_run(cmd)
        print("merging %s into kernel source and committing changes..." % wlan_type)
        cmd = 'git merge -X subtree=drivers/staging/%s \
               --edit -m "%s: Merge tag \'%s\' into `git rev-parse --abbrev-ref HEAD`" FETCH_HEAD --no-edit' \
               % (wlan_type, wlan_type, tag)
        talk = subprocess_run(cmd)


def main():
    wlan_type, merge_type, tag = parameters()
    major_version, sub_version = get_git_version()
    if not path.exists("drivers/staging") and not path.isfile("Makefile"):
        err("Please, run this script inside your root kernel source.")
    merging()


parameters()
main()
