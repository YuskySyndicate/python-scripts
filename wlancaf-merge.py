#!/usr/bin/env python
#
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Copyright (C) 2019 Adek Maulana
#
# A simple script to add/update QCACLD or PRIMA into/for your,
# Android kernel source. *only qcacld-3.0 and prima were supported.

from __future__ import print_function

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
        print('An error was detected while running the subprocess:\n'
              'exit code: %d\n'
              'stdout: %s\n'
              'stderr: %s' % (exitCode, talk[0], talk[1]))
        raise CalledProcessError(exitCode, cmd)
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
    else:
        extra_cmd = ''
    return extra_cmd


def parameters():
    global wlan_type, merge_type, tag
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


def repo():
    global repo_url, staging, subdir
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


def check():
    if wlan_type == 'qcacld' and merge_type == 'initial':
        for subdirs in subdir:
            if isdir(join(staging, subdirs)):
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
            print('\n' + 'You might want to use --init initial, '
                  'because those three are exists, '
                  '\nor one of them is exist and not empty.')
            raise OSError
    elif wlan_type == 'qcacld' and merge_type == 'update':
        for subdirs in subdir:
            if isdir(join(staging, subdirs)):
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
            print('\n' + 'You might want to use --init update, '
                  "because those three aren't exists."
                  '\nor exists but one of them has an empty folder.' + '\n')
            raise OSError
    elif wlan_type == 'prima' and merge_type == 'initial':
        if isdir(join(staging, subdir)):
            if listdir(join(staging, subdir)):
                print('\n' + 'You might want to use --init update, '
                      "\nbecause prima is exist and it's not empty." + '\n')
                raise OSError
            else:
                return True
        else:
            return True
    elif wlan_type == 'prima' and merge_type == 'update':
        if isdir(join(staging, subdir)):
            if listdir(join(staging, subdir)):
                return True
            else:
                print("Folder prima exist, but it's just an empty folder.")
                raise OSError
        else:
            print('You might want to use --init initial, '
                  "because prima isn't exist.")
            raise OSError


def merge():
    extra_cmd = git_env()
    if wlan_type == 'qcacld' and merge_type == 'initial':
        for repos in repo_url:
            print("Fetching %s with tag '%s'" % (repos, tag))
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
                        print('Merging %s into kernel source...' % repos)
                    if cmd == cmds[2]:
                        print('Committing changes...')
                        print('\n' + talk[0])
                break
    elif wlan_type == 'qcacld' and merge_type == 'update':
        for repos in repo_url:
            print("Fetching %s with tag '%s'" % (repos, tag))
            cmd = 'git fetch %s %s' % (repo_url[repos], tag)
            talk = subprocess_run(cmd)
            while True:
                print('Merging %s into kernel source and committing changes...'
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
                print("Fetching %s with tag '%s'" % (wlan_type, tag))
            if cmd == cmds[1]:
                print('Merging %s into kernel source...' % wlan_type)
            if cmd == cmds[3]:
                print('Committing changes...')
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
                print("Fetching %s with tag '%s'" % (wlan_type, tag))
            if cmd == cmds[1]:
                print('Merging %s into kernel source and committing changes...'
                      % wlan_type)
        else:
            print('\n' + talk[0])
    return True


def IncludeToKconfig():
    if merge_type == 'initial':
        tempRemove = 'endif # STAGING\n'
        KconfigToInclude = None
        if wlan_type == 'qcacld':
            KconfigToInclude = ('source "drivers/staging/qcacld-3.0/Kconfig"'
                                '\n\nendif # STAGING\n')
            KconfigToCheck = 'source "drivers/staging/qcacld-3.0/Kconfig"'
        elif wlan_type == 'prima':
            KconfigToInclude = ('source "drivers/staging/prima/Kconfig"'
                                '\n\nendif # STAGING\n')
            KconfigToCheck = 'source "drivers/staging/prima/Kconfig"'
        with open('drivers/staging/Kconfig', 'r') as Kconfig:
            ValueKconfig = Kconfig.read()
        if KconfigToCheck not in ValueKconfig:
            print('Including %s into Kconfig...' % wlan_type)
            with open('drivers/staging/Kconfig', 'w') as Kconfig:
                NewKconfig = ValueKconfig.replace(tempRemove, KconfigToInclude)
                Kconfig.write(NewKconfig)
            cmds = ['git add drivers/staging/Kconfig',
                    'git commit -m "%s: include it into Kconfig"' % wlan_type]
            for cmd in cmds:
                try:
                    subprocess_run(cmd)
                except CalledProcessError as err:
                    break
                    raise err
    return


def main():
    repo()
    if not exists('Makefile'):
        print('Run this script inside your root kernel source.')
        raise OSError
    if not exists(staging):
        print("Staging folder can't be found, "
              'are you sure running it inside kernel source?')
        raise OSError
    if check() is True:
        try:
            merge()
        except CalledProcessError as err:
            raise err
        IncludeToKconfig()


if __name__ == '__main__':
    parameters()
    main()
