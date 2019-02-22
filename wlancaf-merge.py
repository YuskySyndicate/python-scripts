# SPDX-License-Identifier: GPL-3.0-or-later
#
# Copyright (C) 2019 Adek Maulana
#
# A simple script to add/update QCACLD or PRIMA into/for your,
# Android kernel source. *only qcacld-3.0 and prima were supported.

from __future__ import print_function

import sys
import psutil
import signal
from argparse import ArgumentParser
from os import listdir
from os.path import isdir, exists, join
from subprocess import PIPE, Popen, CalledProcessError


def subprocess_run(cmd):
    subproc = Popen(cmd, stdout=PIPE, stderr=PIPE,
                    shell=True, universal_newlines=True)
    subproc.wait()
    talk = subproc.communicate()
    exitCode = subproc.returncode
    if exitCode != 0:
        raise CalledProcessError(
            'An error was detected while running the subprocess:\n'
            'exit code: %d\n'
            'stdout: %s\n'
            'stderr: %s' % (exitCode, talk[0], talk[1]))
    return talk


def kill_subprocess(parent_pid, sig=signal.SIGTERM):
    try:
        parent = psutil.Process(parent_pid)
    except psutil.NoSuchProcess:
        return
    children = parent.children(recursive=True)
    for process in children:
        process.send_signal(sig)


def git_env():
    cmd = 'git --version | cut -d " " -f3 | head -n1 | tr -d "\n"'
    talk = subprocess_run(cmd)
    version = talk[0].strip().split('.')
    major_version = int(version[0])
    sub_version = int(version[1])
    if major_version >= 2 and sub_version >= 9:
        extra_cmd = '--allow-unrelated-histories'
    return extra_cmd


def err(message):
    print('\n' + message)
    sys.exit(1)


def parameters():
    param = ArgumentParser(description='Wlan CAF driver updater/initial'
                                       'merging into Android kernel source', )
    param.add_argument('-W', '--wlan', choices=['qcacld', 'prima'],
                       help='Your WLAN driver type either qcacld/prima.',
                       required=True)
    param.add_argument('-I', '--init', choices=['update', 'initial'],
                       help='Choose wether to update or initial merging.',
                       required=True)
    param.add_argument('-T', '--tag', help='Your CAF tag you want to merge.',
                       required=True)
    params = vars(param.parse_args())
    wlan_type = params['wlan']
    merge_type = params['init']
    tag = params['tag']
    return wlan_type, merge_type, tag


def repo():
    wlan_type, merge_type, tag = parameters()
    staging = 'drivers/staging'
    if wlan_type == 'qcacld':
        repo_url = {
            'fw-api': ('https://source.codeaurora.org/'
                       'quic/la/platform/vendor/qcom-opensource/wlan/fw-api/'),
            'qca-wifi-host-cmn': ('https://source.codeaurora.org/'
                                  'quic/la/platform/vendor/qcom-opensource/'
                                  'wlan/qca-wifi-host-cmn/'),
            'qcacld-3.0': ('https://source.codeaurora.org/'
                           'quic/la/platform/vendor/qcom-opensource/wlan/'
                           'qcacld-3.0')
        }
        subdir = ['fw-api', 'qca-wifi-host-cmn', 'qcacld-3.0']
    elif wlan_type == 'prima':
        repo_url = ('https://source.codeaurora.org/'
                    'quic/la/platform/vendor/qcom-opensource/wlan/prima/')
        subdir = 'prima'
    return repo_url, staging, subdir


def check():
    wlan_type, merge_type, tag = parameters()
    repo_url, staging, subdir = repo()
    if wlan_type == 'qcacld' and merge_type == 'initial':
        for subdirs in subdir:
            if exists(join(staging, subdirs)
                      ) and isdir(join(staging, subdirs)):
                if listdir(join(staging, subdirs)):
                    print('%s exist and not empty' % subdirs)
                    continue
                else:
                    if subdirs == 'qcacld-3.0' and not listdir(
                        join(staging, 'fw-api')
                             ) and not listdir(
                        join(staging, 'qca-wifi-host-cmn')
                             ) and not listdir(join(staging, 'qcacld-3.0')):
                        return True
            else:
                return True
        else:
            err('you might want to use --init initial, '
                'because those 3 are exists, '
                '\nor one of them is exist and not empty.')
    elif wlan_type == 'qcacld' and merge_type == 'update':
        for subdirs in subdir:
            if exists(join(staging, subdirs)
                      ) and isdir(join(staging, subdirs)):
                if not listdir(join(staging, subdirs)):
                    print('%s exist and empty' % subdirs)
                    continue
                else:
                    if subdirs == 'qcacld-3.0' and listdir(
                        join(staging, 'fw-api')
                             ) and listdir(
                        join(staging, 'qca-wifi-host-cmn')
                             ) and listdir(join(staging, 'qcacld-3.0')):
                        return True
            else:
                continue
        else:
            err('you might want to use --init update, '
                'because those 3 are not exists.'
                '\nor exists but one of them has an empty folder.')
    elif wlan_type == 'prima' and merge_type == 'initial':
        if exists(join(staging, subdir)) and isdir(join(staging, subdir)):
            if listdir(join(staging, subdir)):
                err('you might want to use --init update, '
                    '\nbecause prima is exist and it is not empty.')
            else:
                return True
        else:
            return True
    elif wlan_type == 'prima' and merge_type == 'update':
        if exists(join(staging, subdir)) and isdir(join(staging, subdir)):
            if listdir(join(staging, subdir)):
                return True
            else:
                err('folder prima exist, but it is just an empty folder.')
        else:
            err('you might want to use --init initial, '
                'because prima is not exist.')


def merge():
    wlan_type, merge_type, tag = parameters()
    repo_url, staging, subdir = repo()
    extra_cmd = git_env()
    if wlan_type == 'qcacld' and merge_type == 'initial':
        for repos in repo_url:
            print("fetching %s with tag '%s'" % (repos, tag))
            cmd = 'git fetch %s %s' % (repo_url[repos], tag)
            talk = subprocess_run(cmd)
            while True:
                cmds = [
                    'git merge -s ours --no-commit %s FETCH_HEAD' % extra_cmd,
                    ('git read-tree --prefix=drivers/staging/%s '
                     '-u FETCH_HEAD' % repos),
                    ('git commit -m "%s: Merge init tag \'%s\' into '
                     '`git rev-parse --abbrev-ref HEAD`"' % (repos, tag))
                ]
                for cmd in cmds:
                    talk = subprocess_run(cmd)
                    if cmd == cmds[0]:
                        print('merging %s into kernel source...' % repos)
                    if cmd == cmds[2]:
                        print('committing changes...')
                        print('\n' + talk[0])
                break
    elif wlan_type == 'qcacld' and merge_type == 'update':
        for repos in repo_url:
            print("fetching %s with tag '%s'" % (repos, tag))
            cmd = 'git fetch %s %s' % (repo_url[repos], tag)
            talk = subprocess_run(cmd)
            while True:
                print('merging %s into kernel source and committing changes...'
                      % repos)
                cmd = ('git merge -X subtree=drivers/staging/%s '
                       '--edit -m "%s: Merge tag \'%s\' into '
                       '`git rev-parse --abbrev-ref HEAD`" '
                       'FETCH_HEAD --no-edit'
                       % (repos, repos, tag))
                talk = subprocess_run(cmd)
                print('\n' + talk[0])
                break
    elif wlan_type == 'prima' and merge_type == 'initial':
        cmds = [
            'git fetch %s %s' % (repo_url, tag),
            'git merge -s ours --no-commit %s FETCH_HEAD' % extra_cmd,
            ('git read-tree --prefix=drivers/staging/%s '
             '-u FETCH_HEAD' % wlan_type),
            ('git commit -m "%s: Merge init tag \'%s\' into '
             '`git rev-parse --abbrev-ref HEAD`"' % (wlan_type, tag))
        ]
        for cmd in cmds:
            talk = subprocess_run(cmd)
            if cmd == cmds[0]:
                print("fetching %s with tag '%s'" % (wlan_type, tag))
            if cmd == cmds[1]:
                print('merging %s into kernel source...' % wlan_type)
            if cmd == cmds[3]:
                print('committing changes...')
        else:
            print('\n' + talk[0])
    elif wlan_type == 'prima' and merge_type == 'update':
        cmds = [
            'git fetch %s %s' % (repo_url, tag),
            ('git merge -X subtree=drivers/staging/%s '
             '--edit -m "%s: Merge tag \'%s\' into '
             '`git rev-parse --abbrev-ref HEAD`" FETCH_HEAD --no-edit'
             % (wlan_type, wlan_type, tag))
        ]
        for cmd in cmds:
            talk = subprocess_run(cmd)
            if cmd == cmds[0]:
                print("fetching %s with tag '%s'" % (wlan_type, tag))
            if cmd == cmds[1]:
                print('merging %s into kernel source and committing changes...'
                      % wlan_type)
        else:
            print('\n' + talk[0])
    return True


def main():
    wlan_type, merge_type, tag = parameters()
    repo_url, staging, subdir = repo()
    if not exists('drivers/staging') and not exists('Makefile'):
        err('Please, run this script inside your root kernel source.')
    if check() is True:
        merge()


parameters()
main()
